import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiosqlite

from ..config import settings

log = logging.getLogger(__name__)

# Module-level singleton — created once per process.
_connection: aiosqlite.Connection | None = None
_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    """Return (or lazily create) the asyncio.Lock for the running event loop."""
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


def _clear_stale_locks(db_path: str) -> None:
    """Remove SQLite lock/journal files left by a previously crashed process.

    On Azure Files (SMB) these files are never auto-cleaned, so a crashed
    container can leave the database permanently locked for future instances.
    Safe to call before opening the connection — if the files do not exist,
    nothing happens.
    """
    for suffix in ("-journal", "-wal", "-shm"):
        stale = db_path + suffix
        try:
            os.remove(stale)
            log.warning("Removed stale SQLite lock file: %s", stale)
        except FileNotFoundError:
            pass


async def get_connection() -> aiosqlite.Connection:
    """Return the shared aiosqlite connection, creating it on first call."""
    global _connection
    async with _get_lock():
        if _connection is None:
            db_path = os.path.abspath(settings.database_path)
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            _clear_stale_locks(db_path)
            # nolock=1 disables all POSIX advisory file locking — needed on
            # Azure Files (SMB) which does not reliably support fcntl() locks.
            # It is NOT supported by all local SQLite builds, so it is opt-in
            # via the SQLITE_NOLOCK=1 environment variable (set automatically
            # in containerapp.yaml for Azure deployments).
            use_nolock = os.environ.get("SQLITE_NOLOCK", "0") == "1"
            if use_nolock:
                # Pre-create the file so the nolock VFS can open it.
                if not os.path.exists(db_path):
                    open(db_path, "a").close()
                db_uri = f"file://{db_path}?nolock=1"
                _connection = await aiosqlite.connect(
                    db_uri,
                    uri=True,
                    timeout=30,
                )
            else:
                _connection = await aiosqlite.connect(
                    db_path,
                    timeout=30,
                )
            _connection.row_factory = aiosqlite.Row
            await _connection.execute("PRAGMA journal_mode=MEMORY")
            await _connection.execute("PRAGMA busy_timeout=30000")
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
