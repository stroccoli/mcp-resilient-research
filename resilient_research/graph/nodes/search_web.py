"""Node 2: search_web — execute the current query via the provider router."""

import logging

from ...database import repository as repo
from ...services.search.router import ProviderRouter
from ..state import ResearchState

logger = logging.getLogger(__name__)

# Singleton router — shared across all background tasks in the same process.
_router = ProviderRouter()


async def node_search_web(state: ResearchState) -> dict:
    """Execute the current query via the provider router and queue new URLs."""
    query_index = state.get("query_index", 0)
    queries = state.get("queries", [])

    if query_index >= len(queries):
        return {"current_stage": "pick_url"}

    query = queries[query_index]
    max_sources = state["constraints"].get("max_sources", 15)

    try:
        urls = await _router.search(query, max_results=max_sources)

        seen: set[str] = set(
            state.get("processed_urls", []) + state.get("pending_urls", [])
        )
        new_urls = [u for u in urls if u not in seen]

        pending = list(dict.fromkeys(state.get("pending_urls", []) + new_urls))

        if new_urls:
            await repo.add_to_session_counter(
                state["session_id"], "sources_found", len(new_urls)
            )

        logger.info(
            "[%s] Query %d/%d → %d new URLs (pending=%d).",
            state["session_id"],
            query_index + 1,
            len(queries),
            len(new_urls),
            len(pending),
        )
        return {
            "pending_urls": pending,
            "query_index": query_index + 1,
            "current_stage": "pick_url",
        }

    except Exception as exc:  # noqa: BLE001
        err = {
            "stage": "search",
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        await repo.create_error_log(
            state["session_id"], "search", type(exc).__name__, str(exc)
        )
        return {
            "errors": [err],
            "query_index": query_index + 1,
            "current_stage": "pick_url",
        }
