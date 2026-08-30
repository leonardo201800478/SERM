PRAGMA foreign_keys = ON;

-- Migration 007 finalizes MAME machine metadata indexes.
-- isbios is supplied by migration 005.
-- ingested_at is supplied by migration 006.
-- ismechanical may already exist when migration 007 is retried after an
-- interrupted executescript; the importer also preserves it in mame_xml_node.
-- Do not ALTER the table here: SQLite ALTER TABLE ADD COLUMN is not
-- idempotent, and a previous failed migration can have persisted the column.

CREATE INDEX IF NOT EXISTS ix_mame_machine_flags
    ON mame_machine(import_id, isdevice, isbios, ismechanical, runnable);

CREATE INDEX IF NOT EXISTS ix_mame_machine_ingested_at
    ON mame_machine(import_id, ingested_at);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('007_mame_machine_metadata', datetime('now'));
