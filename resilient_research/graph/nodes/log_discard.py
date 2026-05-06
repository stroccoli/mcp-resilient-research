"""Node 10: log_discard — pass-through; actual DB writes happen upstream."""

from ..state import ResearchState


async def node_log_discard(state: ResearchState) -> dict:
    """
    Pass-through node.  Actual discard DB writes happen inside the nodes that
    route here (scrape, metadata, authority, relevance, constraints).
    """
    return {"current_stage": "pick_url"}
