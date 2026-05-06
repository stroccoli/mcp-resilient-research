"""Node 12: handle_error — terminal error handler; marks session as failed."""

import logging

from ...database import repository as repo
from ..state import ResearchState

logger = logging.getLogger(__name__)


async def node_handle_error(state: ResearchState) -> dict:
    """
    Called when an unrecoverable pipeline error occurs.
    Marks the session as failed and terminates.
    """
    logger.error(
        "[%s] Unrecoverable error. Marking session failed. Errors: %s",
        state["session_id"],
        state.get("errors"),
    )
    await repo.update_session_status(state["session_id"], "failed")
    return {"current_stage": "end"}
