"""
Provider rotation router: Brave → SerpAPI → DuckDuckGo.

Each provider tracks its own rate-limit backoff window independently.
When a provider fails, it is marked unavailable for an exponentially growing
window, and the next provider in the chain is tried immediately.
"""

import logging
from datetime import datetime, timedelta, timezone

from ...config import settings
from .base import AbstractSearchProvider
from .brave import BraveSearchProvider
from .duckduckgo import DuckDuckGoProvider
from .serpapi import SerpAPIProvider

logger = logging.getLogger(__name__)


class ProviderRouter:
    """Ordered rotation across all configured search providers."""

    def __init__(self) -> None:
        self._providers: list[AbstractSearchProvider] = [
            BraveSearchProvider(),
            SerpAPIProvider(),
            DuckDuckGoProvider(),
        ]
        # Maps provider.name → UTC datetime until which it is rate-limited.
        self._rate_limited_until: dict[str, datetime] = {}
        # Per-provider failure count for progressive backoff.
        self._failure_counts: dict[str, int] = {}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _is_available(self, provider: AbstractSearchProvider) -> bool:
        until = self._rate_limited_until.get(provider.name)
        if until is None:
            return True
        return datetime.now(timezone.utc) >= until

    def _mark_rate_limited(self, provider: AbstractSearchProvider) -> None:
        count = self._failure_counts.get(provider.name, 0) + 1
        self._failure_counts[provider.name] = count
        backoff = min(
            settings.backoff_base_delay * (2 ** (count - 1)),
            settings.backoff_max_delay,
        )
        self._rate_limited_until[provider.name] = (
            datetime.now(timezone.utc) + timedelta(seconds=backoff)
        )
        logger.warning(
            "Provider %r marked rate-limited for %.0fs (failure #%d).",
            provider.name,
            backoff,
            count,
        )

    def _reset_failures(self, provider: AbstractSearchProvider) -> None:
        self._failure_counts.pop(provider.name, None)
        self._rate_limited_until.pop(provider.name, None)

    # ── Public API ────────────────────────────────────────────────────────────

    async def search(self, query: str, max_results: int = 10) -> list[str]:
        """
        Try each provider in order (Brave → SerpAPI → DDG).
        Returns results from the first successful provider.
        Raises RuntimeError if all providers fail.
        """
        last_exc: Exception | None = None

        for provider in self._providers:
            if not self._is_available(provider):
                logger.info("Provider %r is rate-limited — skipping.", provider.name)
                continue

            try:
                results = await provider.search(query, max_results=max_results)
                self._reset_failures(provider)
                logger.info(
                    "Provider %r returned %d URLs for query %r.",
                    provider.name,
                    len(results),
                    query[:60],
                )
                return results

            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                self._mark_rate_limited(provider)
                logger.warning(
                    "Provider %r failed: %s",
                    provider.name,
                    exc,
                )

        raise RuntimeError(
            "All search providers failed or are rate-limited."
        ) from last_exc
