PRAGMA foreign_keys = ON;

-- Compatibility marker only. ingested_at is defined in migration 003.
CREATE INDEX IF NOT EXISTS ix_mame_machine_ingested_at
    ON mame_machine(import_id, ingested_at);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('006_mame_machine_ingested_at', datetime('now'));
