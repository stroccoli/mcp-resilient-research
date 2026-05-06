"""Node 5: extract_metadata — pull structured metadata from the scraped page."""

from ...database import repository as repo
from ...services.evaluator import extract_metadata
from ..state import ResearchState


async def node_extract_metadata(state: ResearchState) -> dict:
    url = state["current_url"]
    content = state.get("scraped_content", "")

    try:
        metadata = await extract_metadata(url, content)
        return {"extracted_metadata": metadata, "current_stage": "score_authority"}

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
            state["session_id"], url, f"Metadata extraction failed: {exc}",
            "metadata_extraction",
        )
        await repo.increment_session_counter(state["session_id"], "sources_discarded")
        return {"errors": [err], "current_url": None, "current_stage": "pick_url"}
