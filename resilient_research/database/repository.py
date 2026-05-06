"""All async CRUD operations for the four database tables."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from .connection import db_cursor, get_connection


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


# ── Sessions ──────────────────────────────────────────────────────────────────

async def create_session(topic: str, research_goal: str, constraints: dict) -> str:
    """Insert a new session row and return its UUID."""
    session_id = _new_id()
    async with db_cursor() as cur:
        await cur.execute(
            """
            INSERT INTO sessions (id, topic, research_goal, constraints, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (session_id, topic, research_goal, json.dumps(constraints)),
        )
    return session_id


async def get_session(session_id: str) -> dict | None:
    conn = await get_connection()
    async with conn.execute(
        "SELECT * FROM sessions WHERE id = ?", (session_id,)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return None
    d = dict(row)
    d["constraints"] = json.loads(d["constraints"])
    return d


async def update_session_status(session_id: str, status: str) -> None:
    async with db_cursor() as cur:
        await cur.execute(
            "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
            (status, _utcnow(), session_id),
        )


async def increment_session_counter(session_id: str, field: str) -> None:
    _allowed = {"sources_found", "sources_validated", "sources_discarded"}
    if field not in _allowed:
        raise ValueError(f"Invalid counter field: {field!r}")
    async with db_cursor() as cur:
        await cur.execute(
            f"UPDATE sessions SET {field} = {field} + 1, updated_at = ? WHERE id = ?",
            (_utcnow(), session_id),
        )


async def add_to_session_counter(session_id: str, field: str, delta: int) -> None:
    """Increment a counter by an arbitrary positive amount."""
    _allowed = {"sources_found", "sources_validated", "sources_discarded"}
    if field not in _allowed:
        raise ValueError(f"Invalid counter field: {field!r}")
    if delta <= 0:
        return
    async with db_cursor() as cur:
        await cur.execute(
            f"UPDATE sessions SET {field} = {field} + ?, updated_at = ? WHERE id = ?",
            (delta, _utcnow(), session_id),
        )


# ── Artifacts ─────────────────────────────────────────────────────────────────

async def create_artifact(
    session_id: str,
    source_url: str,
    author: str | None,
    organization: str | None,
    country: str | None,
    publication_date: str | None,
    authority_level: str,
    confidence_score: float,
    key_findings: list[str],
    provenance_metadata: dict,
    raw_content_hash: str,
) -> str:
    artifact_id = _new_id()
    async with db_cursor() as cur:
        await cur.execute(
            """
            INSERT INTO artifacts (
                id, session_id, source_url, author, organization, country,
                publication_date, authority_level, confidence_score,
                key_findings, provenance_metadata, raw_content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id, session_id, source_url, author, organization, country,
                publication_date, authority_level, confidence_score,
                json.dumps(key_findings), json.dumps(provenance_metadata), raw_content_hash,
            ),
        )
    return artifact_id


async def get_artifacts(session_id: str) -> list[dict]:
    conn = await get_connection()
    async with conn.execute(
        "SELECT * FROM artifacts WHERE session_id = ? ORDER BY confidence_score DESC",
        (session_id,),
    ) as cur:
        rows = await cur.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["key_findings"] = json.loads(d["key_findings"])
        d["provenance_metadata"] = json.loads(d["provenance_metadata"])
        result.append(d)
    return result


async def artifact_url_exists(session_id: str, source_url: str) -> bool:
    conn = await get_connection()
    async with conn.execute(
        "SELECT 1 FROM artifacts WHERE session_id = ? AND source_url = ?",
        (session_id, source_url),
    ) as cur:
        return await cur.fetchone() is not None


# ── Discards ──────────────────────────────────────────────────────────────────

async def create_discard(
    session_id: str,
    source_url: str,
    rejection_reason: str,
    rejection_stage: str,
    authority_level: str | None = None,
    confidence_score: float | None = None,
    metadata: dict | None = None,
) -> str:
    discard_id = _new_id()
    async with db_cursor() as cur:
        await cur.execute(
            """
            INSERT INTO discards (
                id, session_id, source_url, rejection_reason, rejection_stage,
                authority_level, confidence_score, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                discard_id, session_id, source_url, rejection_reason, rejection_stage,
                authority_level, confidence_score, json.dumps(metadata or {}),
            ),
        )
    return discard_id


async def get_discards(session_id: str) -> list[dict]:
    conn = await get_connection()
    async with conn.execute(
        "SELECT * FROM discards WHERE session_id = ? ORDER BY created_at DESC",
        (session_id,),
    ) as cur:
        rows = await cur.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["metadata"] = json.loads(d["metadata"])
        result.append(d)
    return result


# ── Error Logs ────────────────────────────────────────────────────────────────

async def create_error_log(
    session_id: str,
    stage: str,
    error_type: str,
    error_message: str,
    url: str | None = None,
    retry_count: int = 0,
) -> str:
    log_id = _new_id()
    async with db_cursor() as cur:
        await cur.execute(
            """
            INSERT INTO error_logs (
                id, session_id, stage, error_type, error_message, url, retry_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (log_id, session_id, stage, error_type, error_message, url, retry_count),
        )
    return log_id


async def get_error_logs(session_id: str) -> list[dict]:
    conn = await get_connection()
    async with conn.execute(
        "SELECT * FROM error_logs WHERE session_id = ? ORDER BY created_at DESC",
        (session_id,),
    ) as cur:
        rows = await cur.fetchall()
    return [dict(row) for row in rows]


async def resolve_error_log(log_id: str) -> None:
    async with db_cursor() as cur:
        await cur.execute(
            "UPDATE error_logs SET resolved = 1 WHERE id = ?", (log_id,)
        )
