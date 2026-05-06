"""Node 4: scrape_url — fetch and hash the page content."""

from ...database import repository as repo
from ...services.resilience import PermanentFailure
from ...services.scraper import scrape
from ..state import ResearchState


async def node_scrape_url(state: ResearchState) -> dict:
    url = state["current_url"]

    try:
        text, content_hash = await scrape(url)
        return {
            "scraped_content": text,
            "content_hash": content_hash,
            "current_stage": "extract_metadata",
        }

    except PermanentFailure as exc:
        reason = f"HTTP {exc.status_code}: permanent scrape failure"
        await repo.create_discard(state["session_id"], url, reason, "scrape")
        await repo.increment_session_counter(state["session_id"], "sources_discarded")
        return {"current_url": None, "current_stage": "pick_url"}

    except Exception as exc:  # noqa: BLE001
        err = {
            "stage": "scrape",
            "error_type": type(exc).__name__,
            "message": str(exc),
            "url": url,
        }
        await repo.create_error_log(
            state["session_id"], "scrape", type(exc).__name__, str(exc), url=url
        )
        await repo.create_discard(
            state["session_id"], url, f"Scrape error: {exc}", "scrape"
        )
        await repo.increment_session_counter(state["session_id"], "sources_discarded")
        return {"errors": [err], "current_url": None, "current_stage": "pick_url"}
