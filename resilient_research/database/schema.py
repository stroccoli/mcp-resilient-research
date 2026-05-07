"""DDL for all four tables. Applied at server startup via init_db()."""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id                  TEXT    PRIMARY KEY,
    topic               TEXT    NOT NULL,
    research_goal       TEXT    NOT NULL,
    constraints         TEXT    NOT NULL DEFAULT '{}',
    status              TEXT    NOT NULL DEFAULT 'pending'
                                CHECK(status IN ('pending','processing','completed','failed')),
    sources_found       INTEGER NOT NULL DEFAULT 0,
    sources_validated   INTEGER NOT NULL DEFAULT 0,
    sources_discarded   INTEGER NOT NULL DEFAULT 0,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artifacts (
    id                  TEXT    PRIMARY KEY,
    session_id          TEXT    NOT NULL REFERENCES sessions(id),
    source_url          TEXT    NOT NULL,
    author              TEXT,
    organization        TEXT,
    country             TEXT,
    publication_date    TEXT,
    authority_level     TEXT    CHECK(authority_level IN ('High','Medium','Low')),
    confidence_score    REAL    NOT NULL,
    key_findings        TEXT    NOT NULL DEFAULT '[]',
    provenance_metadata TEXT    NOT NULL DEFAULT '{}',
    raw_content_hash    TEXT    NOT NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS discards (
    id                  TEXT    PRIMARY KEY,
    session_id          TEXT    NOT NULL REFERENCES sessions(id),
    source_url          TEXT    NOT NULL,
    rejection_reason    TEXT    NOT NULL,
    rejection_stage     TEXT    NOT NULL
                                CHECK(rejection_stage IN (
                                    'scrape',
                                    'metadata_extraction',
                                    'authority_scoring',
                                    'relevance_assessment',
                                    'constraint_check'
                                )),
    authority_level     TEXT,
    confidence_score    REAL,
    metadata            TEXT    DEFAULT '{}',
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS error_logs (
    id              TEXT    PRIMARY KEY,
    session_id      TEXT    NOT NULL REFERENCES sessions(id),
    stage           TEXT    NOT NULL
                            CHECK(stage IN ('search','scrape','evaluate','save')),
    error_type      TEXT    NOT NULL,
    error_message   TEXT    NOT NULL,
    url             TEXT,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    resolved        INTEGER NOT NULL DEFAULT 0 CHECK(resolved IN (0,1)),
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_artifacts_session   ON artifacts(session_id);
CREATE INDEX IF NOT EXISTS idx_discards_session    ON discards(session_id);
CREATE INDEX IF NOT EXISTS idx_error_logs_session  ON error_logs(session_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_artifacts_url
    ON artifacts(session_id, source_url);
"""


# Individual DDL statements — avoids executescript() which demands an
# exclusive lock on the whole file (unreliable on Azure Files / SMB mounts).
_SCHEMA_STATEMENTS = [
    s.strip() for s in SCHEMA_SQL.split(";") if s.strip()
]


async def init_db() -> None:
    """Create all tables and indexes. Safe to call multiple times."""
    from .connection import get_connection

    conn = await get_connection()
    async with conn.cursor() as cur:
        for stmt in _SCHEMA_STATEMENTS:
            await cur.execute(stmt)
    await conn.commit()
