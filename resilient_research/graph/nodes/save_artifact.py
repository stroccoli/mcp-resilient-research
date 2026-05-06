"""Node 9: save_artifact — persist a validated source to the database."""

import logging
from datetime import datetime, timezone

from ...database import repository as repo
from ..state import ResearchState

logger = logging.getLogger(__name__)


async def node_save_artifact(state: ResearchState) -> dict:
    url = state["current_url"]
    meta = state.get("extracted_metadata") or {}

    # Deduplication guard (URL-level within session).
    if await repo.artifact_url_exists(state["session_id"], url):
        logger.info("[%s] Duplicate URL skipped: %s", state["session_id"], url)
        return {"current_url": None, "current_stage": "pick_url"}

    provenance: dict = {
        "search_session": state["session_id"],
        "content_type": meta.get("content_type"),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        # Extension point: add domain-specific provenance fields here.
    }

    await repo.create_artifact(
        session_id=state["session_id"],
        source_url=url,
        author=meta.get("author"),
        organization=meta.get("organization"),
        country=meta.get("country"),
        publication_date=meta.get("publication_date"),
        authority_level=state.get("authority_level", "Low"),
        confidence_score=state.get("confidence_score", 0.0),
        key_findings=state.get("key_findings", []),
        provenance_metadata=provenance,
        raw_content_hash=state.get("content_hash", ""),
    )
    await repo.increment_session_counter(state["session_id"], "sources_validated")

    new_count = state.get("validated_count", 0) + 1
    logger.info(
        "[%s] Artifact saved (%d/%d): %s | score=%.4f | authority=%s",
        state["session_id"],
        new_count,
        state["constraints"].get("max_sources", 15),
        url,
        state.get("confidence_score", 0.0),
        state.get("authority_level"),
    )

    return {
        "validated_count": new_count,
        "current_url": None,
        "current_stage": "pick_url",
    }
