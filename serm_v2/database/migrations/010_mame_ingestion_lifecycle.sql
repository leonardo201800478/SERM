PRAGMA foreign_keys = ON;

-- Lifecycle of the lossless ListXML acquisition. This table intentionally
-- contains no machine-level data: phase 1 only captures the complete source.
CREATE TABLE IF NOT EXISTS mame_ingestion_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER REFERENCES mame_listxml_import(id) ON DELETE SET NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('running','completed','failed','cancelled')),
    stage TEXT NOT NULL,
    executable TEXT NOT NULL,
    mame_build TEXT,
    source_hash TEXT,
    byte_length INTEGER NOT NULL DEFAULT 0,
    machine_count INTEGER NOT NULL DEFAULT 0,
    elapsed_seconds REAL,
    error_type TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS ix_mame_ingestion_run_status
    ON mame_ingestion_run(status, started_at);
CREATE INDEX IF NOT EXISTS ix_mame_ingestion_run_hash
    ON mame_ingestion_run(source_hash);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('010_mame_ingestion_lifecycle', datetime('now'));
