PRAGMA foreign_keys = ON;

-- Complete the machine-level metadata exposed by MAME -listxml.
-- isbios/ismechanical are MAME facts; ingested_at is SERM provenance.
ALTER TABLE mame_machine ADD COLUMN ismechanical TEXT;
ALTER TABLE mame_machine ADD COLUMN ingested_at TEXT;

CREATE INDEX IF NOT EXISTS ix_mame_machine_flags
    ON mame_machine(import_id, isdevice, isbios, ismechanical, runnable);

CREATE INDEX IF NOT EXISTS ix_mame_machine_ingested_at
    ON mame_machine(import_id, ingested_at);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('007_mame_machine_metadata', datetime('now'));
