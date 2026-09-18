PRAGMA foreign_keys = OFF;

-- A migration 012 original marcou source_hash como UNIQUE globalmente.
-- Isso impedia preservar dois arquivos INI diferentes com conteúdo idêntico.
-- O identificador de versão deve ser (arquivo, hash), não apenas o hash.
CREATE TABLE IF NOT EXISTS mame_folder_filter_source_v2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    byte_length INTEGER NOT NULL DEFAULT 0,
    imported_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('captured','completed','failed')),
    UNIQUE(file_name, source_hash)
);

INSERT INTO mame_folder_filter_source_v2
    (id, file_name, file_path, source_hash, byte_length, imported_at, status)
SELECT
    id, file_name, file_path, source_hash, byte_length, imported_at, status
FROM mame_folder_filter_source;

DROP TABLE mame_folder_filter_source;
ALTER TABLE mame_folder_filter_source_v2 RENAME TO mame_folder_filter_source;

CREATE INDEX IF NOT EXISTS ix_mame_folder_filter_source_name
    ON mame_folder_filter_source(file_name);
CREATE INDEX IF NOT EXISTS ix_mame_folder_filter_source_hash
    ON mame_folder_filter_source(source_hash);
CREATE INDEX IF NOT EXISTS ix_mame_folder_filter_entry_source_machine
    ON mame_folder_filter_entry(source_id, machine_name);
CREATE INDEX IF NOT EXISTS ix_mame_folder_filter_entry_machine
    ON mame_folder_filter_entry(machine_name);
CREATE INDEX IF NOT EXISTS ix_mame_folder_filter_entry_section
    ON mame_folder_filter_entry(source_id, section);

PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('018_mame_folder_filter_storage', datetime('now'));
