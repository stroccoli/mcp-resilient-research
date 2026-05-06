"""Integration tests for the three MCP tool functions."""

from unittest.mock import AsyncMock, patch

import pytest

from resilient_research.database import repository as repo


# ── start_autonomous_research ─────────────────────────────────────────────────

async def test_start_research_returns_session_id(test_db):
    with patch("resilient_research.tools.start_research.asyncio.create_task") as mock_task:
        from resilient_research.tools.start_research import start_autonomous_research

        result = await start_autonomous_research(
            topic="French Revolution",
            research_goal="Understand the main causes",
            constraints={"max_sources": 3},
        )

    assert "session_id" in result
    assert result["status"] == "started"
    assert mock_task.call_count == 1

    # Session should be in DB
    session = await repo.get_session(result["session_id"])
    assert session is not None
    assert session["topic"] == "French Revolution"
    assert session["status"] == "pending"


async def test_start_research_invalid_authority(test_db):
    with patch("resilient_research.tools.start_research.asyncio.create_task"):
        from resilient_research.tools.start_research import start_autonomous_research
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="min_authority"):
            await start_autonomous_research(
                topic="Topic",
                research_goal="Goal",
                constraints={"min_authority": "Ultra"},
            )


async def test_start_research_normalises_country_codes(test_db):
    with patch("resilient_research.tools.start_research.asyncio.create_task"):
        from resilient_research.tools.start_research import start_autonomous_research

        result = await start_autonomous_research(
            topic="Topic",
            research_goal="Goal",
            constraints={"allowed_countries": ["fr", "de"]},
        )

    session = await repo.get_session(result["session_id"])
    assert "FR" in session["constraints"]["allowed_countries"]
    assert "DE" in session["constraints"]["allowed_countries"]


# ── get_research_status ───────────────────────────────────────────────────────

async def test_get_status_not_found(test_db):
    from resilient_research.tools.get_status import get_research_status

    result = await get_research_status("no-such-session")

    assert "error" in result


async def test_get_status_existing_session(test_db):
    from resilient_research.tools.get_status import get_research_status

    sid = await repo.create_session("Topic", "Goal", {"max_sources": 10})
    await repo.update_session_status(sid, "processing")
    await repo.increment_session_counter(sid, "sources_found")
    await repo.increment_session_counter(sid, "sources_validated")

    result = await get_research_status(sid)

    assert result["session_id"] == sid
    assert result["status"] == "processing"
    assert result["sources_found"] == 1
    assert result["sources_validated"] == 1
    assert result["sources_discarded"] == 0
    assert isinstance(result["errors"], list)


async def test_get_status_includes_error_log(test_db):
    from resilient_research.tools.get_status import get_research_status

    sid = await repo.create_session("Topic", "Goal", {})
    await repo.create_error_log(sid, "scrape", "TimeoutError", "timed out", url="https://slow.com")

    result = await get_research_status(sid)
    assert len(result["errors"]) == 1
    assert result["errors"][0]["error_type"] == "TimeoutError"


# ── get_discarded_logs ────────────────────────────────────────────────────────

async def test_get_discarded_not_found(test_db):
    from resilient_research.tools.get_discarded import get_discarded_logs

    result = await get_discarded_logs("ghost-session")

    assert "error" in result


async def test_get_discarded_empty(test_db):
    from resilient_research.tools.get_discarded import get_discarded_logs

    sid = await repo.create_session("Topic", "Goal", {})
    result = await get_discarded_logs(sid)

    assert result["total_discarded"] == 0
    assert result["discards"] == []


async def test_get_discarded_with_entries(test_db):
    from resilient_research.tools.get_discarded import get_discarded_logs

    sid = await repo.create_session("Topic", "Goal", {})
    await repo.create_discard(
        sid, "https://bad.com", "Low authority", "constraint_check",
        authority_level="Low", confidence_score=0.18,
    )
    await repo.create_discard(
        sid, "https://off-topic.com", "Relevance score 0.11 below threshold",
        "relevance_assessment",
    )

    result = await get_discarded_logs(sid)

    assert result["total_discarded"] == 2
    urls = {d["source_url"] for d in result["discards"]}
    assert "https://bad.com" in urls
    assert "https://off-topic.com" in urls
