PRAGMA foreign_keys = ON;

-- Migration 007 finalizes indexes that depend only on columns guaranteed by
-- migrations 003, 005 and 006. Machine classification fields added later are
-- indexed by their own migration, so this migration remains safe on a clean DB.

CREATE INDEX IF NOT EXISTS ix_mame_machine_classification
    ON mame_machine(import_id, isdevice, isbios, runnable);

CREATE INDEX IF NOT EXISTS ix_mame_machine_ingested_at
    ON mame_machine(import_id, ingested_at);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('007_mame_machine_metadata', datetime('now'));
