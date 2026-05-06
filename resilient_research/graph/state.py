"""
LangGraph state definition for the research pipeline.

Each field that can accumulate across nodes uses operator.add as reducer;
all others are replaced on each update (default reducer).
"""

import operator
from typing import Annotated, TypedDict


class ResearchConstraints(TypedDict, total=False):
    min_authority: str           # "High" | "Medium" | "Low"
    allowed_countries: list[str] # ISO-2 codes; empty list = no restriction (soft check)
    max_sources: int             # stop after this many validated artifacts
    max_queries: int             # max search query variations to run


class ResearchState(TypedDict):
    # ── Session identity ──────────────────────────────────────────────────────
    session_id: str
    topic: str
    research_goal: str
    constraints: ResearchConstraints

    # ── URL pipeline ──────────────────────────────────────────────────────────
    pending_urls: list[str]     # discovered, not yet processed
    processed_urls: list[str]   # attempted (success or failure)
    current_url: str | None     # URL currently under evaluation

    # ── Content under evaluation ──────────────────────────────────────────────
    scraped_content: str | None
    content_hash: str | None

    # ── Evaluation results ────────────────────────────────────────────────────
    extracted_metadata: dict | None
    authority_level: str | None
    authority_score: float | None
    relevance_score: float | None
    key_findings: list[str]
    confidence_score: float | None

    # ── Control flow ──────────────────────────────────────────────────────────
    retry_count: int
    current_stage: str          # signals used by edge routing functions
    validated_count: int
    query_index: int
    queries: list[str]

    # ── Accumulated errors (reducer = list concat) ────────────────────────────
    errors: Annotated[list[dict], operator.add]
