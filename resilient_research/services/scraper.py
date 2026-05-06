"""HTTP scraper: fetch and clean page text with exponential-backoff retry."""

import hashlib
import logging

import httpx
from bs4 import BeautifulSoup

from .resilience import PermanentFailure, with_retry

logger = logging.getLogger(__name__)

# Maximum characters passed downstream to the LLM evaluator.
_MAX_CONTENT_CHARS = 15_000

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ResilientResearchBot/1.0; "
        "+https://github.com/resilient-research)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en,fr,de;q=0.8",
}


async def scrape(url: str) -> tuple[str, str]:
    """
    Fetch *url*, strip boilerplate, and return (text_content, sha256_hash).

    Raises:
        PermanentFailure — HTTP 400 / 403 / 404 (do not retry at call site).
        RuntimeError     — all retries exhausted.
    """

    async def _call() -> tuple[str, str]:
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers=_HEADERS,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            return text[:_MAX_CONTENT_CHARS], content_hash

    return await with_retry(_call, stage="scrape")
