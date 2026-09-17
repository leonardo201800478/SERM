PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS mame_resolution (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_document_id INTEGER NOT NULL REFERENCES mame_source_document(id) ON DELETE CASCADE,
    machine_id INTEGER REFERENCES mame_machine(id) ON DELETE SET NULL,
    machine_name TEXT NOT NULL,
    resolution_raw TEXT NOT NULL,
    width INTEGER NOT NULL CHECK(width > 0),
    height INTEGER NOT NULL CHECK(height > 0),
    resolved_status TEXT NOT NULL DEFAULT 'resolved' CHECK(resolved_status IN ('resolved','unresolved')),
    imported_at TEXT NOT NULL,
    UNIQUE(source_document_id, machine_name)
);

CREATE INDEX IF NOT EXISTS ix_mame_resolution_machine ON mame_resolution(machine_id);
CREATE INDEX IF NOT EXISTS ix_mame_resolution_name ON mame_resolution(machine_name);
CREATE INDEX IF NOT EXISTS ix_mame_resolution_source ON mame_resolution(source_document_id);
CREATE INDEX IF NOT EXISTS ix_mame_resolution_dimensions ON mame_resolution(width, height);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('013_mame_resolution_sources', datetime('now'));
