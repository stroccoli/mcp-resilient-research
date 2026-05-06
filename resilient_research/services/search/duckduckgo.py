"""DuckDuckGo search provider (no API key required, sync library wrapped async)."""

import asyncio

from duckduckgo_search import DDGS

from .base import AbstractSearchProvider


class DuckDuckGoProvider(AbstractSearchProvider):
    name = "duckduckgo"

    async def search(self, query: str, max_results: int = 10) -> list[str]:
        loop = asyncio.get_event_loop()

        def _sync_search() -> list[str]:
            with DDGS() as ddgs:
                results = ddgs.text(query, max_results=max_results)
                return [r["href"] for r in results if r.get("href")]

        return await loop.run_in_executor(None, _sync_search)
