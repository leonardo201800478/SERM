PRAGMA foreign_keys = ON;

-- Fontes de filtros auxiliares do MAME (folders/*.ini).
-- O ListXML continua sendo a fonte de verdade do catálogo; estas tabelas
-- apenas preservam listas externas/auxiliares e permitem consultas rápidas.
CREATE TABLE IF NOT EXISTS mame_folder_filter_source (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    source_hash TEXT NOT NULL UNIQUE,
    byte_length INTEGER NOT NULL DEFAULT 0,
    imported_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('captured','completed','failed')),
    UNIQUE(file_name, source_hash)
);

CREATE INDEX IF NOT EXISTS ix_mame_folder_filter_source_name
    ON mame_folder_filter_source(file_name);

CREATE TABLE IF NOT EXISTS mame_folder_filter_entry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES mame_folder_filter_source(id) ON DELETE CASCADE,
    section TEXT,
    machine_name TEXT NOT NULL,
    raw_value TEXT NOT NULL,
    UNIQUE(source_id, section, machine_name)
);

CREATE INDEX IF NOT EXISTS ix_mame_folder_filter_entry_source_machine
    ON mame_folder_filter_entry(source_id, machine_name);
CREATE INDEX IF NOT EXISTS ix_mame_folder_filter_entry_machine
    ON mame_folder_filter_entry(machine_name);
CREATE INDEX IF NOT EXISTS ix_mame_folder_filter_entry_section
    ON mame_folder_filter_entry(source_id, section);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('012_mame_folder_filters', datetime('now'));
