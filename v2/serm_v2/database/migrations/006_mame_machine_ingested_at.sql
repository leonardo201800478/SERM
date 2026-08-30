PRAGMA foreign_keys = ON;

-- Timestamp for the normalized MAME machine ingestion record.
-- Keep this as TEXT to match the SQLite timestamp conventions used by SERM.
ALTER TABLE mame_machine ADD COLUMN ingested_at TEXT;

CREATE INDEX IF NOT EXISTS ix_mame_machine_ingested_at
    ON mame_machine(import_id, ingested_at);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('006_mame_machine_ingested_at', datetime('now'));
