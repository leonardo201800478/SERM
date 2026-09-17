PRAGMA foreign_keys = ON;

-- Fase 1: somente proveniência e documento completo do ListXML.
-- Nenhuma tabela de máquina/ROM/display é populada pela captura inicial.
CREATE TABLE IF NOT EXISTS mame_listxml_import (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emulator_id INTEGER NOT NULL REFERENCES emulator_definition(id) ON DELETE CASCADE,
    executable TEXT NOT NULL,
    mame_build TEXT,
    mame_config TEXT,
    debug TEXT,
    imported_at TEXT NOT NULL,
    source_hash TEXT NOT NULL UNIQUE,
    xml_path TEXT,
    machine_count INTEGER NOT NULL DEFAULT 0,
    byte_length INTEGER NOT NULL DEFAULT 0,
    parser_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('captured','completed','failed'))
);
CREATE INDEX IF NOT EXISTS ix_mame_listxml_import_build ON mame_listxml_import(mame_build);
CREATE INDEX IF NOT EXISTS ix_mame_listxml_import_executable ON mame_listxml_import(executable);

CREATE TABLE IF NOT EXISTS mame_listxml_document (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER NOT NULL UNIQUE REFERENCES mame_listxml_import(id) ON DELETE CASCADE,
    source_hash TEXT NOT NULL UNIQUE,
    byte_length INTEGER NOT NULL,
    encoding TEXT NOT NULL DEFAULT 'utf-8',
    xml_text TEXT NOT NULL,
    stored_at TEXT NOT NULL
);

-- Catálogo derivado: reservado para fases posteriores. Não participa da Fase 1.
CREATE TABLE IF NOT EXISTS mame_machine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER NOT NULL REFERENCES mame_listxml_import(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sourcefile TEXT,
    isbios TEXT,
    isdevice TEXT,
    ismechanical TEXT,
    runnable TEXT,
    cloneof TEXT,
    romof TEXT,
    sampleof TEXT,
    description TEXT,
    year TEXT,
    manufacturer TEXT,
    xml_node_id INTEGER,
    ingested_at TEXT,
    UNIQUE(import_id, name)
);
CREATE INDEX IF NOT EXISTS ix_mame_machine_name ON mame_machine(name);
CREATE INDEX IF NOT EXISTS ix_mame_machine_import ON mame_machine(import_id);

-- A árvore normalizada foi retirada da ingestão inicial. Será criada apenas
-- quando houver necessidade real de análise derivada do set filtrado.

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('003_mame_catalog_schema', datetime('now'));
