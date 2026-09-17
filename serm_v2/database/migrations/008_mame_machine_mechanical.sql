PRAGMA foreign_keys = ON;

-- Compatibility marker only. ismechanical is defined in migration 003.
CREATE INDEX IF NOT EXISTS ix_mame_machine_mechanical
    ON mame_machine(import_id, ismechanical);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('008_mame_machine_mechanical', datetime('now'));
