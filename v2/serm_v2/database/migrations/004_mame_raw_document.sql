PRAGMA foreign_keys = ON;

-- Exact source document retained inside SQLite. The normalized tables are
-- query-oriented; this table is the immutable provenance/lossless layer.
CREATE TABLE IF NOT EXISTS mame_listxml_document (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER NOT NULL UNIQUE REFERENCES mame_listxml_import(id) ON DELETE CASCADE,
    source_hash TEXT NOT NULL UNIQUE,
    encoding TEXT NOT NULL DEFAULT 'utf-8',
    xml_text TEXT NOT NULL,
    byte_length INTEGER NOT NULL,
    stored_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_mame_listxml_document_import
    ON mame_listxml_document(import_id);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('004_mame_raw_document', datetime('now'));
