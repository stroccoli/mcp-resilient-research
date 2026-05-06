"""Tests for all database repository functions."""

import pytest

from resilient_research.database import repository as repo


# ── Sessions ──────────────────────────────────────────────────────────────────

async def test_create_and_get_session(test_db):
    sid = await repo.create_session("French Revolution", "Understand its causes", {"max_sources": 5})
    session = await repo.get_session(sid)

    assert session is not None
    assert session["topic"] == "French Revolution"
    assert session["research_goal"] == "Understand its causes"
    assert session["status"] == "pending"
    assert session["sources_found"] == 0
    assert session["constraints"]["max_sources"] == 5


async def test_get_session_not_found(test_db):
    result = await repo.get_session("nonexistent-id")
    assert result is None


async def test_update_session_status(test_db):
    sid = await repo.create_session("Topic", "Goal", {})
    await repo.update_session_status(sid, "processing")
    session = await repo.get_session(sid)
    assert session["status"] == "processing"


async def test_increment_session_counter(test_db):
    sid = await repo.create_session("Topic", "Goal", {})
    await repo.increment_session_counter(sid, "sources_found")
    await repo.increment_session_counter(sid, "sources_found")
    session = await repo.get_session(sid)
    assert session["sources_found"] == 2


async def test_add_to_session_counter(test_db):
    sid = await repo.create_session("Topic", "Goal", {})
    await repo.add_to_session_counter(sid, "sources_found", 7)
    session = await repo.get_session(sid)
    assert session["sources_found"] == 7


async def test_increment_counter_invalid_field(test_db):
    sid = await repo.create_session("Topic", "Goal", {})
    with pytest.raises(ValueError, match="Invalid counter field"):
        await repo.increment_session_counter(sid, "bad_field")


# ── Artifacts ─────────────────────────────────────────────────────────────────

async def test_create_and_get_artifact(test_db):
    sid = await repo.create_session("Topic", "Goal", {})
    await repo.create_artifact(
        session_id=sid,
        source_url="https://jstor.org/article/1",
        author="Marie Curie",
        organization="Sorbonne",
        country="FR",
        publication_date="2020-01-15",
        authority_level="High",
        confidence_score=0.88,
        key_findings=["Finding A", "Finding B"],
        provenance_metadata={"content_type": "academic"},
        raw_content_hash="abc123",
    )

    artifacts = await repo.get_artifacts(sid)
    assert len(artifacts) == 1
    art = artifacts[0]
    assert art["author"] == "Marie Curie"
    assert art["country"] == "FR"
    assert art["authority_level"] == "High"
    assert art["confidence_score"] == pytest.approx(0.88)
    assert art["key_findings"] == ["Finding A", "Finding B"]
    assert art["provenance_metadata"]["content_type"] == "academic"


async def test_artifacts_sorted_by_confidence_desc(test_db):
    sid = await repo.create_session("Topic", "Goal", {})

    for score in (0.5, 0.9, 0.7):
        await repo.create_artifact(
            session_id=sid,
            source_url=f"https://example.com/{score}",
            author=None, organization=None, country=None, publication_date=None,
            authority_level="Medium", confidence_score=score,
            key_findings=[], provenance_metadata={}, raw_content_hash=str(score),
        )

    artifacts = await repo.get_artifacts(sid)
    scores = [a["confidence_score"] for a in artifacts]
    assert scores == sorted(scores, reverse=True)


async def test_artifact_url_deduplication(test_db):
    sid = await repo.create_session("Topic", "Goal", {})
    url = "https://dupe.com/article"

    await repo.create_artifact(
        session_id=sid, source_url=url, author=None, organization=None,
        country=None, publication_date=None, authority_level="Low",
        confidence_score=0.5, key_findings=[], provenance_metadata={}, raw_content_hash="x",
    )

    assert await repo.artifact_url_exists(sid, url) is True
    assert await repo.artifact_url_exists(sid, "https://other.com") is False


# ── Discards ──────────────────────────────────────────────────────────────────

async def test_create_and_get_discard(test_db):
    sid = await repo.create_session("Topic", "Goal", {})
    await repo.create_discard(
        session_id=sid,
        source_url="https://blog.example.com",
        rejection_reason="Authority 'Low' below required 'High'",
        rejection_stage="constraint_check",
        authority_level="Low",
        confidence_score=0.21,
        metadata={"note": "personal blog"},
    )

    discards = await repo.get_discards(sid)
    assert len(discards) == 1
    d = discards[0]
    assert d["source_url"] == "https://blog.example.com"
    assert d["rejection_stage"] == "constraint_check"
    assert d["authority_level"] == "Low"
    assert d["metadata"]["note"] == "personal blog"


# ── Error Logs ────────────────────────────────────────────────────────────────

async def test_create_and_get_error_log(test_db):
    sid = await repo.create_session("Topic", "Goal", {})
    await repo.create_error_log(
        session_id=sid,
        stage="scrape",
        error_type="TimeoutError",
        error_message="Connection timed out after 30s",
        url="https://slow.example.com",
        retry_count=3,
    )

    logs = await repo.get_error_logs(sid)
    assert len(logs) == 1
    log = logs[0]
    assert log["stage"] == "scrape"
    assert log["error_type"] == "TimeoutError"
    assert log["retry_count"] == 3
    assert log["resolved"] == 0


async def test_resolve_error_log(test_db):
    sid = await repo.create_session("Topic", "Goal", {})
    log_id = await repo.create_error_log(sid, "search", "RuntimeError", "all providers failed")

    await repo.resolve_error_log(log_id)
    logs = await repo.get_error_logs(sid)
    assert logs[0]["resolved"] == 1
