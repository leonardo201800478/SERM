PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS mame_vsync (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_document_id INTEGER NOT NULL REFERENCES mame_source_document(id) ON DELETE CASCADE,
    machine_id INTEGER REFERENCES mame_machine(id) ON DELETE SET NULL,
    machine_name TEXT NOT NULL,
    vsync_enabled INTEGER NOT NULL DEFAULT 1 CHECK(vsync_enabled IN (0,1)),
    value_raw TEXT NOT NULL DEFAULT '1',
    resolved_status TEXT NOT NULL DEFAULT 'resolved' CHECK(resolved_status IN ('resolved','unresolved')),
    imported_at TEXT NOT NULL,
    UNIQUE(source_document_id, machine_name)
);

CREATE INDEX IF NOT EXISTS ix_mame_vsync_machine ON mame_vsync(machine_id);
CREATE INDEX IF NOT EXISTS ix_mame_vsync_name ON mame_vsync(machine_name);
CREATE INDEX IF NOT EXISTS ix_mame_vsync_source ON mame_vsync(source_document_id);
CREATE INDEX IF NOT EXISTS ix_mame_vsync_enabled ON mame_vsync(vsync_enabled);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('014_mame_vsync_sources', datetime('now'));
