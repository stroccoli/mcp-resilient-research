"""Brave Search API provider."""

import httpx

from ...config import settings
from ..resilience import with_retry
from .base import AbstractSearchProvider

_BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveSearchProvider(AbstractSearchProvider):
    name = "brave"

    async def search(self, query: str, max_results: int = 10) -> list[str]:
        if not settings.brave_api_key:
            raise RuntimeError("BRAVE_API_KEY is not configured.")

        async def _call() -> list[str]:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    _BRAVE_SEARCH_URL,
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": settings.brave_api_key,
                    },
                    params={"q": query, "count": min(max_results, 20)},
                )
                resp.raise_for_status()
                data = resp.json()
                return [r["url"] for r in data.get("web", {}).get("results", [])]

        return await with_retry(_call, stage="search")
