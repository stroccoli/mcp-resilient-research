"""
Shared pytest fixtures.

All async tests share one event loop (asyncio_default_fixture_loop_scope = "session")
so the module-level asyncio.Lock in database/connection.py is safe across tests.

Each test that touches the DB gets an isolated SQLite file via test_db.
"""

import pytest
import aiosqlite

import resilient_research.database.connection as db_conn
from resilient_research.database.schema import SCHEMA_SQL


@pytest.fixture
async def test_db(tmp_path):
    """
    Provide an isolated aiosqlite connection for a single test.

    Patches db_conn._connection so all repository calls use the test DB.
    Cleans up and restores state after the test.
    """
    db_path = str(tmp_path / "test.db")
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.executescript(SCHEMA_SQL)
    await conn.commit()

    # Inject the test connection into the module-level singleton.
    original_conn = db_conn._connection
    original_lock = db_conn._lock
    db_conn._connection = conn
    db_conn._lock = None  # will be re-created lazily per event loop

    yield conn

    db_conn._connection = original_conn
    db_conn._lock = original_lock
    await conn.close()


@pytest.fixture
def mock_litellm(monkeypatch):
    """
    Replace litellm.acompletion with an AsyncMock.

    Usage in tests:
        mock_litellm.return_value = _make_llm_response({...})
    """
    from unittest.mock import AsyncMock
    import litellm

    mock = AsyncMock()
    monkeypatch.setattr(litellm, "acompletion", mock)
    return mock
