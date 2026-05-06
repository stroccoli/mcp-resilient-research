"""
Tests for LangGraph nodes and edge routing functions.

Nodes are tested in isolation with mocked DB calls.
Edge routing functions are pure and require no mocking.
"""

from unittest.mock import AsyncMock, patch

import pytest

from resilient_research.graph.edges import (
    route_from_authority,
    route_from_check_completion,
    route_from_constraints,
    route_from_metadata,
    route_from_pick_next_url,
    route_from_relevance,
    route_from_save,
    route_from_scrape,
)
from resilient_research.graph.state import ResearchState


# ── Helpers ───────────────────────────────────────────────────────────────────

def _state(**overrides) -> ResearchState:
    base: ResearchState = {
        "session_id": "test-session-001",
        "topic": "French Revolution",
        "research_goal": "Understand the main causes",
        "constraints": {
            "min_authority": "Low",
            "allowed_countries": [],
            "max_sources": 5,
            "max_queries": 3,
        },
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
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


# ── Edge routing — pure functions, no mocking needed ─────────────────────────

def test_route_pick_next_url_empty_queue():
    assert route_from_pick_next_url(_state(current_url=None)) == "check_completion"


def test_route_pick_next_url_has_url():
    assert route_from_pick_next_url(_state(current_url="https://a.com")) == "scrape_url"


def test_route_scrape_success():
    assert route_from_scrape(_state(current_stage="extract_metadata")) == "extract_metadata"


def test_route_scrape_failure():
    assert route_from_scrape(_state(current_stage="pick_url")) == "pick_next_url"


def test_route_metadata_success():
    s = _state(current_url="https://a.com", current_stage="score_authority")
    assert route_from_metadata(s) == "score_authority"


def test_route_metadata_failure():
    assert route_from_metadata(_state(current_url=None)) == "pick_next_url"


def test_route_authority_success():
    s = _state(current_url="https://a.com")
    assert route_from_authority(s) == "assess_relevance"


def test_route_authority_failure():
    assert route_from_authority(_state(current_url=None)) == "pick_next_url"


def test_route_relevance_success():
    s = _state(current_url="https://a.com")
    assert route_from_relevance(s) == "apply_constraints"


def test_route_relevance_failure():
    assert route_from_relevance(_state(current_url=None)) == "pick_next_url"


def test_route_constraints_pass():
    assert route_from_constraints(_state(current_stage="save_artifact")) == "save_artifact"


def test_route_constraints_fail():
    assert route_from_constraints(_state(current_stage="pick_url")) == "pick_next_url"


def test_route_save_always_pick_next():
    assert route_from_save(_state()) == "pick_next_url"


def test_route_check_completion_end():
    assert route_from_check_completion(_state(current_stage="end")) == "__end__"


def test_route_check_completion_more_queries():
    assert route_from_check_completion(_state(current_stage="search")) == "search_web"


# ── Node: generate_queries ────────────────────────────────────────────────────

async def test_node_generate_queries_creates_queries():
    from resilient_research.graph.nodes import node_generate_queries

    with patch(
        "resilient_research.graph.nodes.generate_queries.repo.update_session_status",
        new_callable=AsyncMock,
    ):
        state = _state(constraints={"max_queries": 3, "max_sources": 5})
        result = await node_generate_queries(state)

    assert "queries" in result
    assert len(result["queries"]) == 3
    assert result["query_index"] == 0
    assert result["current_stage"] == "search"


# ── Node: apply_constraints ───────────────────────────────────────────────────

async def test_apply_constraints_authority_fail():
    from resilient_research.graph.nodes import node_apply_constraints

    with (
        patch("resilient_research.graph.nodes.apply_constraints.repo.create_discard", new_callable=AsyncMock),
        patch(
            "resilient_research.graph.nodes.apply_constraints.repo.increment_session_counter",
            new_callable=AsyncMock,
        ),
    ):
        state = _state(
            current_url="https://blog.com",
            authority_level="Low",
            authority_score=0.2,
            relevance_score=0.9,
            constraints={
                "min_authority": "High",
                "allowed_countries": [],
                "max_sources": 5,
                "max_queries": 3,
            },
        )
        result = await node_apply_constraints(state)

    assert result["current_stage"] == "pick_url"
    assert result["current_url"] is None


async def test_apply_constraints_country_fail_known():
    """Soft constraint: should reject when country IS known and not in list."""
    from resilient_research.graph.nodes import node_apply_constraints

    with (
        patch("resilient_research.graph.nodes.apply_constraints.repo.create_discard", new_callable=AsyncMock),
        patch(
            "resilient_research.graph.nodes.apply_constraints.repo.increment_session_counter",
            new_callable=AsyncMock,
        ),
    ):
        state = _state(
            current_url="https://news.us/article",
            authority_level="High",
            authority_score=0.85,
            relevance_score=0.85,
            extracted_metadata={"country": "US", "author": "John", "content_type": "news"},
            constraints={
                "min_authority": "Low",
                "allowed_countries": ["FR", "DE"],
                "max_sources": 5,
                "max_queries": 3,
            },
        )
        result = await node_apply_constraints(state)

    assert result["current_stage"] == "pick_url"


async def test_apply_constraints_country_unknown_passes():
    """Soft constraint: should NOT filter when country is 'Unknown'."""
    from resilient_research.graph.nodes import node_apply_constraints

    with (
        patch("resilient_research.graph.nodes.apply_constraints.repo.create_discard", new_callable=AsyncMock) as mock_discard,
        patch(
            "resilient_research.graph.nodes.apply_constraints.repo.increment_session_counter",
            new_callable=AsyncMock,
        ),
    ):
        state = _state(
            current_url="https://some-site.com/article",
            authority_level="Medium",
            authority_score=0.6,
            relevance_score=0.8,
            extracted_metadata={"country": "Unknown", "author": "Unknown", "content_type": "news"},
            constraints={
                "min_authority": "Low",
                "allowed_countries": ["FR", "DE"],
                "max_sources": 5,
                "max_queries": 3,
            },
        )
        result = await node_apply_constraints(state)

    # Should pass constraints (country Unknown is not filtered)
    assert result["current_stage"] == "save_artifact"
    mock_discard.assert_not_called()


async def test_apply_constraints_all_pass():
    from resilient_research.graph.nodes import node_apply_constraints

    with (
        patch("resilient_research.graph.nodes.apply_constraints.repo.create_discard", new_callable=AsyncMock) as mock_discard,
        patch(
            "resilient_research.graph.nodes.apply_constraints.repo.increment_session_counter",
            new_callable=AsyncMock,
        ),
    ):
        state = _state(
            current_url="https://cnrs.fr/article",
            authority_level="High",
            authority_score=0.9,
            relevance_score=0.85,
            extracted_metadata={"country": "FR", "author": "Prof X", "content_type": "academic"},
            constraints={
                "min_authority": "Medium",
                "allowed_countries": ["FR", "DE"],
                "max_sources": 5,
                "max_queries": 3,
            },
        )
        result = await node_apply_constraints(state)

    assert result["current_stage"] == "save_artifact"
    mock_discard.assert_not_called()


# ── Node: check_completion ────────────────────────────────────────────────────

async def test_check_completion_max_sources_reached():
    from resilient_research.graph.nodes import node_check_completion

    with patch(
        "resilient_research.graph.nodes.check_completion.repo.update_session_status",
        new_callable=AsyncMock,
    ) as mock_status:
        state = _state(validated_count=5, constraints={"max_sources": 5, "max_queries": 3})
        result = await node_check_completion(state)

    assert result["current_stage"] == "end"
    mock_status.assert_called_once_with("test-session-001", "completed")


async def test_check_completion_more_queries():
    from resilient_research.graph.nodes import node_check_completion

    with patch(
        "resilient_research.graph.nodes.check_completion.repo.update_session_status",
        new_callable=AsyncMock,
    ):
        state = _state(
            validated_count=2,
            query_index=1,
            queries=["q1", "q2", "q3"],
            constraints={"max_sources": 10, "max_queries": 3},
        )
        result = await node_check_completion(state)

    assert result["current_stage"] == "search"


async def test_check_completion_no_queries_left():
    from resilient_research.graph.nodes import node_check_completion

    with patch(
        "resilient_research.graph.nodes.check_completion.repo.update_session_status",
        new_callable=AsyncMock,
    ) as mock_status:
        state = _state(
            validated_count=2,
            query_index=3,
            queries=["q1", "q2", "q3"],
            constraints={"max_sources": 10, "max_queries": 3},
        )
        result = await node_check_completion(state)

    assert result["current_stage"] == "end"
    mock_status.assert_called_once_with("test-session-001", "completed")
