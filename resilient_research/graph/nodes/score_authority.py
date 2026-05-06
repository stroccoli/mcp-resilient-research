"""Node 6: score_authority — classify source credibility (High/Medium/Low)."""

from ...database import repository as repo
from ...services.evaluator import score_authority
from ..state import ResearchState


async def node_score_authority(state: ResearchState) -> dict:
    url = state["current_url"]
    meta = state.get("extracted_metadata") or {}
    content = state.get("scraped_content", "")

    try:
        result = await score_authority(
            url=url,
            author=meta.get("author", "Unknown"),
            organization=meta.get("organization", "Unknown"),
            content_type=meta.get("content_type", "unknown"),
            content_preview=content[:2000],
        )
        return {
            "authority_level": result["authority_level"],
            "authority_score": float(result.get("authority_score", 0.5)),
            "current_stage": "assess_relevance",
        }

    except Exception as exc:  # noqa: BLE001
        err = {
            "stage": "evaluate",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "url": url,
        }
        await repo.create_error_log(
            state["session_id"], "evaluate", type(exc).__name__, str(exc), url=url
        )
        await repo.create_discard(
            state["session_id"], url, f"Authority scoring failed: {exc}",
            "authority_scoring",
        )
        await repo.increment_session_counter(state["session_id"], "sources_discarded")
        return {"errors": [err], "current_url": None, "current_stage": "pick_url"}
