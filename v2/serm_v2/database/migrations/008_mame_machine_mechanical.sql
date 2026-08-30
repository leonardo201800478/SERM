PRAGMA foreign_keys = ON;

-- MAME ListXML exposes ismechanical as a machine classification attribute.
-- It is optional because not every machine entry carries the attribute.
ALTER TABLE mame_machine ADD COLUMN ismechanical TEXT;

CREATE INDEX IF NOT EXISTS ix_mame_machine_mechanical
    ON mame_machine(import_id, ismechanical);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('008_mame_machine_mechanical', datetime('now'));
