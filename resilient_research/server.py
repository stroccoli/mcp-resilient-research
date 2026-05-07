"""
Resilient Research MCP Server.

Exposes:
  Tools:
    start_autonomous_research  — kick off a background research session
    get_research_status        — poll progress for a session
    get_discarded_logs         — inspect rejected sources

  Resources:
    research://knowledge-graph/{session_id} — curated JSON knowledge graph
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from .database.connection import close_connection
from .database.schema import init_db
from .resources.knowledge_graph import get_knowledge_graph
from .tools.get_discarded import get_discarded_logs
from .tools.get_status import get_research_status
from .tools.start_research import start_autonomous_research

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:
    await init_db()
    try:
        yield
    finally:
        await close_connection()


mcp = FastMCP(
    "resilient-research",
    instructions=(
        "Autonomous web research server powered by a LangGraph pipeline with LLM-based evaluation. "
        "Given a topic and a research goal, it searches the web across multiple providers "
        "(Brave Search, SerpAPI, DuckDuckGo), scrapes candidate pages, and evaluates each source "
        "for authority (High/Medium/Low), topical relevance (0–1 score), and metadata "
        "(author, organisation, country, publication date). Only sources that pass all evaluation "
        "gates are persisted to the knowledge graph.\n\n"
        "Workflow:\n"
        "  1. Call start_autonomous_research with a topic, research_goal, and optional constraints. "
        "     Returns a session_id immediately — the pipeline runs in the background.\n"
        "  2. Poll get_research_status(session_id) until status is 'completed' or 'failed'.\n"
        "  3. Read research://knowledge-graph/{session_id} for the curated results, including "
        "     key findings, confidence scores, and provenance metadata for every accepted source.\n\n"
        "Optional constraints (passed to start_autonomous_research):\n"
        "  - min_authority: 'High' | 'Medium' | 'Low' (default 'Low')\n"
        "  - allowed_countries: ISO-2 country list, e.g. ['US', 'GB'] (soft constraint)\n"
        "  - max_sources: integer up to 100 (default 15)\n"
        "  - max_queries: integer up to 20 (default 5)\n\n"
        "Use get_discarded_logs(session_id) to inspect rejected sources and the reason "
        "each one was filtered out."
    ),
    lifespan=lifespan,
)


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def start_autonomous_research_tool(
    topic: str,
    research_goal: str,
    constraints: dict | None = None,
) -> dict:
    """
    Start an autonomous research session and return a session_id immediately.

    The research pipeline runs in the background:
      Search → Scrape → Metadata Extraction → Authority Scoring
      → Relevance Assessment → Constraint Filtering → Persist

    constraints (optional dict):
      - min_authority:      "High" | "Medium" | "Low"  (default "Low")
      - allowed_countries:  ["FR", "DE", ...]  ISO-2 list; empty = no filter
                            NOTE: soft constraint — sources with unknown
                            country are never filtered out.
      - max_sources:        int (default 15, max 100)
      - max_queries:        int (default 5, max 20)

    Returns: {"session_id": str, "status": "started"}
    """
    return await start_autonomous_research(topic, research_goal, constraints)


@mcp.tool()
async def get_research_status_tool(session_id: str) -> dict:
    """
    Get the current status and progress of a research session.

    Returns:
      status            — pending | processing | completed | failed
      sources_found     — total URLs discovered
      sources_validated — artifacts that passed all evaluation gates
      sources_discarded — sources that were filtered out
      errors            — list of the 10 most recent error entries
    """
    return await get_research_status(session_id)


@mcp.tool()
async def get_discarded_logs_tool(session_id: str) -> dict:
    """
    Inspect all rejected sources for a session, including the reason and
    pipeline stage at which they were discarded.

    Useful for auditing evaluation quality and tuning constraints.
    """
    return await get_discarded_logs(session_id)


# ── Resources ─────────────────────────────────────────────────────────────────

@mcp.resource("research://knowledge-graph/{session_id}")
async def knowledge_graph_resource(session_id: str) -> str:
    """
    The curated knowledge graph for a research session.

    Returns a JSON document containing only sources that passed all evaluation
    thresholds.  Each entry includes:
      source_url, author, organization, country, publication_date,
      authority_level, confidence_score, key_findings, provenance_metadata.

    Also includes a summary with authority distribution and average confidence.
    """
    return await get_knowledge_graph(session_id)

# ── Prompts ───────────────────────────────────────────────────────────────────

@mcp.prompt(
    description=(
        "Research the root causes and long-term consequences of a major "
        "historical event."
    )
)
def research_historical_event(event: str, time_period: str) -> list[dict]:
    """
    Generate a research prompt for a major historical event.

    Args:
        event: The historical event to investigate (e.g. 'French Revolution').
        time_period: Approximate date range (e.g. '1789–1799').
    """
    return [
        {
            "role": "user",
            "content": (
                f"I want to deeply understand the historical event known as the "
                f"'{event}' ({time_period}).\n\n"
                "Please use start_autonomous_research with the following parameters:\n"
                f"  topic: \"{event} ({time_period})\"\n"
                f"  research_goal: \"Identify and analyse the root causes, key actors, "
                f"major turning points, and long-term consequences of the {event}. "
                "Favour peer-reviewed academic sources, established encyclopaedias, "
                "and reputable historical archives.\"\n\n"
                "Once the session completes, summarise the findings in three sections: "
                "Background & Causes, Key Developments, and Legacy & Impact."
            ),
        }
    ]


@mcp.prompt(
    description=(
        "Compare two historical civilisations across politics, culture, "
        "economy, and military power."
    )
)
def compare_civilisations(civilisation_a: str, civilisation_b: str) -> list[dict]:
    """
    Generate a comparative research prompt for two historical civilisations.

    Args:
        civilisation_a: First civilisation (e.g. 'Ancient Rome').
        civilisation_b: Second civilisation (e.g. 'Han Dynasty China').
    """
    return [
        {
            "role": "user",
            "content": (
                f"I want a rigorous comparison of '{civilisation_a}' and "
                f"'{civilisation_b}'.\n\n"
                "Please use start_autonomous_research with:\n"
                f"  topic: \"{civilisation_a} vs {civilisation_b}\"\n"
                f"  research_goal: \"Compare {civilisation_a} and {civilisation_b} "
                "across the following dimensions: political structure and governance, "
                "economic systems and trade, cultural and scientific achievements, "
                "military organisation and conflicts, and reasons for decline or "
                "transformation. Use academic and primary sources where possible.\"\n\n"
                "Present the results as a structured comparison table followed by a "
                "narrative synthesis highlighting similarities and key differences."
            ),
        }
    ]


@mcp.prompt(
    description="Trace the biography and historical legacy of a notable historical figure."
)
def research_historical_figure(name: str, era: str) -> list[dict]:
    """
    Generate a research prompt for a historical figure.

    Args:
        name: Full name of the person (e.g. 'Napoleon Bonaparte').
        era: Historical era or century (e.g. 'early 19th century Europe').
    """
    return [
        {
            "role": "user",
            "content": (
                f"I want to learn about '{name}', a historical figure from "
                f"the {era}.\n\n"
                "Please use start_autonomous_research with:\n"
                f"  topic: \"{name} – historical biography and legacy\"\n"
                f"  research_goal: \"Compile a comprehensive profile of {name}: "
                "early life and formative influences, rise to prominence, major "
                "decisions and their consequences, controversies, and lasting "
                "legacy in politics, culture, or science. Prioritise biographies, "
                "peer-reviewed articles, and primary historical documents.\"\n\n"
                "Structure the output as: Early Life → Rise & Achievements → "
                "Key Decisions & Controversies → Death & Legacy."
            ),
        }
    ]


@mcp.prompt(
    description=(
        "Investigate how a specific technology or invention evolved throughout history "
        "and shaped society."
    )
)
def trace_technology_history(technology: str) -> list[dict]:
    """
    Generate a research prompt tracing the history of a technology.

    Args:
        technology: The technology or invention to investigate
                    (e.g. 'the printing press').
    """
    return [
        {
            "role": "user",
            "content": (
                f"I want to trace the full historical arc of '{technology}'.\n\n"
                "Please use start_autonomous_research with:\n"
                f"  topic: \"History of {technology}\"\n"
                f"  research_goal: \"Document the origins, key inventors or "
                f"innovators, incremental improvements, and societal impact of "
                f"{technology} from its earliest known form to the modern era. "
                "Cover economic, cultural, and geopolitical consequences. "
                "Use technical histories, academic journals, and reputable "
                "encyclopaedias.\"\n\n"
                "Organise findings chronologically with a final section on "
                "present-day relevance."
            ),
        }
    ]


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    # stateless_http=True removes the MCP session handshake requirement.
    # Each HTTP request is handled independently — no need to call `initialize`
    # first and pass Mcp-Session-Id on every subsequent request.
    # This is correct here because all state lives in SQLite, not in the MCP session.
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000, stateless_http=True)


if __name__ == "__main__":
    main()
