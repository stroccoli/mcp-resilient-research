"""SerpAPI (Google Search) provider."""

import httpx

from ...config import settings
from ..resilience import with_retry
from .base import AbstractSearchProvider

_SERPAPI_URL = "https://serpapi.com/search"


class SerpAPIProvider(AbstractSearchProvider):
    name = "serpapi"

    async def search(self, query: str, max_results: int = 10) -> list[str]:
        if not settings.serpapi_key:
            raise RuntimeError("SERPAPI_KEY is not configured.")

        async def _call() -> list[str]:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    _SERPAPI_URL,
                    params={
                        "q": query,
                        "api_key": settings.serpapi_key,
                        "num": min(max_results, 20),
                        "engine": "google",
                        "hl": "en",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return [r["link"] for r in data.get("organic_results", [])]

        return await with_retry(_call, stage="search")
