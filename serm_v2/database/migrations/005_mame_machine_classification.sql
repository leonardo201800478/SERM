PRAGMA foreign_keys = ON;

-- Compatibility marker only. The canonical MAME machine columns are defined
-- once, in migration 003. This migration must never ALTER mame_machine.
CREATE INDEX IF NOT EXISTS ix_mame_machine_classification
    ON mame_machine(import_id, isdevice, isbios, runnable);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('005_mame_machine_classification', datetime('now'));
