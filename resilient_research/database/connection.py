import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiosqlite

from ..config import settings

# Module-level singleton — created once per process.
_connection: aiosqlite.Connection | None = None
_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    """Return (or lazily create) the asyncio.Lock for the running event loop."""
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


async def get_connection() -> aiosqlite.Connection:
    """Return the shared aiosqlite connection, creating it on first call."""
    global _connection
    async with _get_lock():
        if _connection is None:
            _connection = await aiosqlite.connect(settings.database_path)
            _connection.row_factory = aiosqlite.Row
        return _connection


@asynccontextmanager
async def db_cursor() -> AsyncGenerator[aiosqlite.Cursor, None]:
    """Yield a cursor and auto-commit on success or rollback on error."""
    conn = await get_connection()
    async with conn.cursor() as cursor:
        try:
            yield cursor
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise


async def close_connection() -> None:
    """Close the singleton connection (called on server shutdown)."""
    global _connection, _lock
    if _lock is not None:
        async with _lock:
            if _connection is not None:
                await _connection.close()
                _connection = None
