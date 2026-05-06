"""Node 11: check_completion — decide whether to end, fetch more, or loop."""

import logging

from ...database import repository as repo
from ..state import ResearchState

logger = logging.getLogger(__name__)


async def node_check_completion(state: ResearchState) -> dict:
    """
    Decide whether to end the session, run the next search query, or continue
    processing pending URLs.
    """
    validated = state.get("validated_count", 0)
    max_sources = state["constraints"].get("max_sources", 15)
    query_index = state.get("query_index", 0)
    total_queries = len(state.get("queries", []))

    # Reached max validated sources → done.
    if validated >= max_sources:
        logger.info(
            "[%s] Reached max_sources=%d. Session complete.", state["session_id"], max_sources
        )
        await repo.update_session_status(state["session_id"], "completed")
        return {"current_stage": "end"}

    # No more queries AND no pending URLs → done.
    if query_index >= total_queries:
        logger.info(
            "[%s] No more queries. Session complete (validated=%d).",
            state["session_id"],
            validated,
        )
        await repo.update_session_status(state["session_id"], "completed")
        return {"current_stage": "end"}

    # More search queries available — run the next one.
    logger.info(
        "[%s] Running next query (%d/%d).", state["session_id"], query_index + 1, total_queries
    )
    return {"current_stage": "search"}
