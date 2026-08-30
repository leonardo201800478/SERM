PRAGMA foreign_keys = ON;

-- MAME ListXML exposes machine classification independently from device
-- classification. Keep this fact explicit because the catalog and filtering
-- layers use it to distinguish BIOS machines from normal runnable systems.
ALTER TABLE mame_machine ADD COLUMN isbios TEXT;

CREATE INDEX IF NOT EXISTS ix_mame_machine_classification
    ON mame_machine(import_id, isdevice, isbios, runnable);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('005_mame_machine_classification', datetime('now'));
