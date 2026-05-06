"""Exponential-backoff retry utility shared by all I/O services."""

import asyncio
import logging
import random
from typing import Awaitable, Callable, TypeVar

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class PermanentFailure(Exception):
    """Non-retryable HTTP error (4xx except 429). Bubbles up to callers."""

    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f"Permanent failure HTTP {status_code} for {url}")


async def with_retry(
    coro_factory: Callable[[], Awaitable[T]],
    max_retries: int | None = None,
    base_delay: float | None = None,
    max_delay: float | None = None,
    stage: str = "unknown",
) -> T:
    """
    Call *coro_factory()* up to *max_retries* + 1 times with exponential
    back-off and ±20 % jitter.

    Retries on: TimeoutException, NetworkError, HTTP 429, HTTP 5xx.
    Raises PermanentFailure immediately for HTTP 400 / 403 / 404.
    """
    _max = max_retries if max_retries is not None else settings.max_retry_count
    _base = base_delay if base_delay is not None else settings.backoff_base_delay
    _max_delay = max_delay if max_delay is not None else settings.backoff_max_delay

    last_exc: Exception | None = None

    for attempt in range(_max + 1):
        try:
            return await coro_factory()

        except PermanentFailure:
            raise  # never retry permanent failures

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            if status in (400, 403, 404):
                raise PermanentFailure(
                    status_code=status, url=str(exc.request.url)
                ) from exc
            last_exc = exc

        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc

        except Exception as exc:  # noqa: BLE001
            last_exc = exc

        if attempt < _max:
            delay = min(_base * (2**attempt), _max_delay)
            jitter = delay * 0.2 * random.random()
            wait = delay + jitter
            logger.warning(
                "[%s] Attempt %d/%d failed (%s: %s). Retrying in %.2fs.",
                stage,
                attempt + 1,
                _max,
                type(last_exc).__name__,
                last_exc,
                wait,
            )
            await asyncio.sleep(wait)

    raise RuntimeError(
        f"[{stage}] All {_max} retries exhausted."
    ) from last_exc
