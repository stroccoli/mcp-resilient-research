"""Node 1: generate_queries — build search query variations from topic + goal.

Query generation can run in two modes, controlled by the
QUERY_GENERATION_MODE environment variable:

  deterministic (default) — uses hand-crafted templates; no LLM call.
  llm                     — asks the configured LLM to produce the query set.
"""

import logging

from ...config import settings
from ...database import repository as repo
from ..state import ResearchState

logger = logging.getLogger(__name__)

# ── Deterministic templates ───────────────────────────────────────────────────

_QUERY_TEMPLATES = [
    "{topic}",
    "{topic} overview analysis",
    '"{topic}" scholarly sources',
    "{topic} {goal}",
    "{topic} academic study",
    "{topic} primary sources",
    "{topic} research findings",
]


def _build_deterministic_queries(topic: str, goal: str, max_queries: int) -> list[str]:
    return [t.format(topic=topic, goal=goal) for t in _QUERY_TEMPLATES][:max_queries]


# ── LLM-based generation ──────────────────────────────────────────────────────

_LLM_QUERY_PROMPT = """\
You are a research assistant.

Generate {max_queries} distinct web search queries to research the following topic.
The queries should cover different angles: general overview, academic sources, primary
sources, and specific aspects of the research goal.

TOPIC:          {topic}
RESEARCH GOAL:  {goal}

Respond with ONLY a valid JSON array of strings — no explanation, no markdown fences:
["query 1", "query 2", ...]"""


async def _build_llm_queries(topic: str, goal: str, max_queries: int) -> list[str]:
    import json

    import litellm

    prompt = _LLM_QUERY_PROMPT.format(topic=topic, goal=goal, max_queries=max_queries)

    kwargs: dict = {"model": settings.litellm_model, "temperature": 0.3}
    if settings.litellm_api_base:
        kwargs["api_base"] = settings.litellm_api_base

    response = await litellm.acompletion(
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    raw: str = response.choices[0].message.content.strip()

    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]

    queries = json.loads(raw.strip())
    if not isinstance(queries, list):
        raise ValueError("LLM did not return a JSON array for query generation.")
    return [str(q) for q in queries[:max_queries]]


# ── Node ──────────────────────────────────────────────────────────────────────

async def node_generate_queries(state: ResearchState) -> dict:
    """Build a list of search query variations from topic + research_goal."""
    topic = state["topic"]
    goal = state["research_goal"]
    max_queries = state["constraints"].get("max_queries", 5)

    mode = settings.query_generation_mode

    if mode == "llm":
        try:
            queries = await _build_llm_queries(topic, goal, max_queries)
            logger.info(
                "[%s] LLM generated %d search queries.", state["session_id"], len(queries)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[%s] LLM query generation failed (%s); falling back to templates.",
                state["session_id"],
                exc,
            )
            queries = _build_deterministic_queries(topic, goal, max_queries)
    else:
        queries = _build_deterministic_queries(topic, goal, max_queries)
        logger.info(
            "[%s] Generated %d search queries (deterministic).",
            state["session_id"],
            len(queries),
        )

    await repo.update_session_status(state["session_id"], "processing")

    return {
        "queries": queries,
        "query_index": 0,
        "current_stage": "search",
    }
