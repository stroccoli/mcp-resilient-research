"""Node 3: pick_next_url — pop the next URL from the queue."""

from ..state import ResearchState


async def node_pick_next_url(state: ResearchState) -> dict:
    """Pop the next URL from the queue, or signal completion if empty."""
    pending = list(state.get("pending_urls", []))

    if not pending:
        return {"current_url": None, "current_stage": "check_completion"}

    url = pending.pop(0)
    processed = state.get("processed_urls", []) + [url]

    return {
        "current_url": url,
        "pending_urls": pending,
        "processed_urls": processed,
        # Reset per-URL evaluation state.
        "scraped_content": None,
        "content_hash": None,
        "extracted_metadata": None,
        "authority_level": None,
        "authority_score": None,
        "relevance_score": None,
        "key_findings": [],
        "confidence_score": None,
        "retry_count": 0,
        "current_stage": "scrape",
    }
