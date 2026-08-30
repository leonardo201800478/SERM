PRAGMA foreign_keys = ON;

-- Complete the machine-level metadata exposed by MAME -listxml.
-- isbios was added by migration 005 and ingested_at by migration 006.
-- Migration 007 therefore adds only the remaining MAME fact.
ALTER TABLE mame_machine ADD COLUMN ismechanical TEXT;

CREATE INDEX IF NOT EXISTS ix_mame_machine_flags
    ON mame_machine(import_id, isdevice, isbios, ismechanical, runnable);

CREATE INDEX IF NOT EXISTS ix_mame_machine_ingested_at
    ON mame_machine(import_id, ingested_at);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('007_mame_machine_metadata', datetime('now'));
