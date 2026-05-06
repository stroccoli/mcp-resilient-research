"""
Tool: start_autonomous_research

Validates input, creates the session record, then fires a background
LangGraph task and returns the session_id immediately.
"""

import asyncio
import logging
from typing import Any

from pydantic import BaseModel, Field, field_validator

from ..database import repository as repo
from ..graph.builder import run_research_graph
from ..graph.state import ResearchState

logger = logging.getLogger(__name__)

_VALID_AUTHORITY = {"High", "Medium", "Low"}


class ResearchConstraintsModel(BaseModel):
    min_authority: str = Field(default="Low")
    allowed_countries: list[str] = Field(default_factory=list)
    max_sources: int = Field(default=15, ge=1, le=100)
    max_queries: int = Field(default=5, ge=1, le=20)

    @field_validator("min_authority")
    @classmethod
    def _validate_authority(cls, v: str) -> str:
        if v not in _VALID_AUTHORITY:
            raise ValueError(f"min_authority must be one of {_VALID_AUTHORITY}")
        return v

    @field_validator("allowed_countries")
    @classmethod
    def _validate_countries(cls, v: list[str]) -> list[str]:
        return [c.upper() for c in v]


async def start_autonomous_research(
    topic: str,
    research_goal: str,
    constraints: dict[str, Any] | None = None,
) -> dict:
    """
    Kick off a background research session.

    Args:
        topic:         Short subject label (e.g. "French Revolution").
        research_goal: Detailed objective for the research.
        constraints:   Optional filtering dict with keys:
                         min_authority   — "High" | "Medium" | "Low"
                         allowed_countries — list of ISO-2 codes (soft constraint)
                         max_sources     — max validated artifacts to collect
                         max_queries     — max search query variations

    Returns:
        {"session_id": str, "status": "started"}
    """
    parsed = ResearchConstraintsModel(**(constraints or {}))
    constraints_dict = parsed.model_dump()

    session_id = await repo.create_session(
        topic=topic,
        research_goal=research_goal,
        constraints=constraints_dict,
    )

    initial_state: ResearchState = {
        "session_id": session_id,
        "topic": topic,
        "research_goal": research_goal,
        "constraints": constraints_dict,  # type: ignore[typeddict-item]
        "pending_urls": [],
        "processed_urls": [],
        "current_url": None,
        "scraped_content": None,
        "content_hash": None,
        "extracted_metadata": None,
        "authority_level": None,
        "authority_score": None,
        "relevance_score": None,
        "key_findings": [],
        "confidence_score": None,
        "retry_count": 0,
        "current_stage": "generate_queries",
        "validated_count": 0,
        "query_index": 0,
        "queries": [],
        "errors": [],
    }

    asyncio.create_task(run_research_graph(session_id, initial_state))
    logger.info("[%s] Research session created for topic: %r", session_id, topic)

    return {"session_id": session_id, "status": "started"}
