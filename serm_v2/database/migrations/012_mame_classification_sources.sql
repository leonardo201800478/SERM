PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS mame_source_document (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    byte_length INTEGER NOT NULL DEFAULT 0,
    imported_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('captured','completed','failed')),
    UNIQUE(source_type, source_hash)
);
CREATE INDEX IF NOT EXISTS ix_mame_source_document_type ON mame_source_document(source_type);
CREATE INDEX IF NOT EXISTS ix_mame_source_document_name ON mame_source_document(source_name);

CREATE TABLE IF NOT EXISTS mame_classification (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER REFERENCES mame_machine(id) ON DELETE CASCADE,
    source_document_id INTEGER NOT NULL REFERENCES mame_source_document(id) ON DELETE CASCADE,
    machine_name TEXT NOT NULL,
    section_raw TEXT NOT NULL,
    category TEXT,
    subcategory TEXT,
    flags_raw TEXT,
    resolved_status TEXT NOT NULL DEFAULT 'resolved' CHECK(resolved_status IN ('resolved','unresolved')),
    imported_at TEXT NOT NULL,
    UNIQUE(source_document_id, machine_name, section_raw)
);
CREATE INDEX IF NOT EXISTS ix_mame_classification_machine ON mame_classification(machine_id);
CREATE INDEX IF NOT EXISTS ix_mame_classification_name ON mame_classification(machine_name);
CREATE INDEX IF NOT EXISTS ix_mame_classification_source ON mame_classification(source_document_id);
CREATE INDEX IF NOT EXISTS ix_mame_classification_category ON mame_classification(category, subcategory);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('012_mame_classification_sources', datetime('now'));
