PRAGMA foreign_keys = ON;

-- Catálogo das software lists oficiais distribuídas em MAME/hash.
-- O XML individual continua sendo a fonte de verdade; estas tabelas existem
-- para busca, filtros, associação com devices e reconstrução de software.
CREATE TABLE IF NOT EXISTS mame_softwarelist_source (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    list_name TEXT NOT NULL,
    description TEXT,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    byte_length INTEGER NOT NULL DEFAULT 0,
    software_count INTEGER NOT NULL DEFAULT 0,
    imported_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN ('captured','completed','failed')),
    UNIQUE(file_name, source_hash)
);
CREATE INDEX IF NOT EXISTS ix_mame_softwarelist_source_name ON mame_softwarelist_source(list_name);
CREATE INDEX IF NOT EXISTS ix_mame_softwarelist_source_hash ON mame_softwarelist_source(source_hash);

CREATE TABLE IF NOT EXISTS mame_software (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES mame_softwarelist_source(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    cloneof TEXT,
    romof TEXT,
    supported TEXT,
    description TEXT,
    year TEXT,
    publisher TEXT,
    info_json TEXT,
    UNIQUE(source_id, name)
);
CREATE INDEX IF NOT EXISTS ix_mame_software_source ON mame_software(source_id);
CREATE INDEX IF NOT EXISTS ix_mame_software_name ON mame_software(name);
CREATE INDEX IF NOT EXISTS ix_mame_software_cloneof ON mame_software(source_id, cloneof);

CREATE TABLE IF NOT EXISTS mame_software_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    software_id INTEGER NOT NULL REFERENCES mame_software(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    value TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_software_info_software ON mame_software_info(software_id);
CREATE INDEX IF NOT EXISTS ix_mame_software_info_name ON mame_software_info(name);

CREATE TABLE IF NOT EXISTS mame_software_part (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    software_id INTEGER NOT NULL REFERENCES mame_software(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    interface TEXT,
    part_id TEXT,
    features TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_software_part_software ON mame_software_part(software_id);

CREATE TABLE IF NOT EXISTS mame_software_rom (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id INTEGER NOT NULL REFERENCES mame_software_part(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    size INTEGER,
    crc TEXT,
    sha1 TEXT,
    md5 TEXT,
    offset TEXT,
    status TEXT,
    dispose TEXT,
    loadflag TEXT,
    optional TEXT,
    merge TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_software_rom_part ON mame_software_rom(part_id);
CREATE INDEX IF NOT EXISTS ix_mame_software_rom_crc ON mame_software_rom(crc);
CREATE INDEX IF NOT EXISTS ix_mame_software_rom_sha1 ON mame_software_rom(sha1);
CREATE INDEX IF NOT EXISTS ix_mame_software_rom_md5 ON mame_software_rom(md5);

CREATE TABLE IF NOT EXISTS mame_software_disk (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id INTEGER NOT NULL REFERENCES mame_software_part(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    md5 TEXT,
    sha1 TEXT,
    merge TEXT,
    region TEXT,
    index_value TEXT,
    writable TEXT,
    status TEXT,
    optional TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_software_disk_part ON mame_software_disk(part_id);
CREATE INDEX IF NOT EXISTS ix_mame_software_disk_sha1 ON mame_software_disk(sha1);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('019_mame_softwarelists', datetime('now'));
