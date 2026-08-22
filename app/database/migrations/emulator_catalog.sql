-- ========================================================================
-- MAME SET BUILDER - CATÁLOGOS MULTI-EMULADOR
-- ========================================================================
-- Catálogos independentes de MAME, FBNeo, Supermodel e Flycast.
-- A tabela machine do dataset MAME legado não é substituída.
--
-- IMPORTANTE:
-- O índice de classificação is_device/is_bios é criado pelo repositório
-- somente depois de garantir essas colunas em bancos antigos.
-- ========================================================================

CREATE TABLE IF NOT EXISTS emulator_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emulator TEXT NOT NULL,
    version TEXT,
    source TEXT NOT NULL,
    source_path TEXT NOT NULL,
    generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    machine_count INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT NOT NULL,
    UNIQUE (emulator)
);

CREATE TABLE IF NOT EXISTS emulator_catalog_machine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    catalog_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    year TEXT,
    manufacturer TEXT,
    sourcefile TEXT,
    cloneof TEXT,
    romof TEXT,
    sampleof TEXT,
    platform TEXT,
    runnable INTEGER NOT NULL DEFAULT 1,
    emulation_status TEXT,
    driver_status TEXT,
    is_device INTEGER NOT NULL DEFAULT 0,
    is_bios INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (catalog_id) REFERENCES emulator_catalog(id) ON DELETE CASCADE,
    UNIQUE (catalog_id, name)
);

CREATE TABLE IF NOT EXISTS emulator_catalog_rom (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    size INTEGER,
    crc TEXT,
    sha1 TEXT,
    merge TEXT,
    region TEXT,
    offset INTEGER DEFAULT 0,
    status TEXT DEFAULT 'good',
    optional INTEGER DEFAULT 0,
    bios TEXT,
    FOREIGN KEY (machine_id) REFERENCES emulator_catalog_machine(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_emulator_catalog_machine_name
    ON emulator_catalog_machine(catalog_id, name);
CREATE INDEX IF NOT EXISTS idx_emulator_catalog_machine_cloneof
    ON emulator_catalog_machine(catalog_id, cloneof);
CREATE INDEX IF NOT EXISTS idx_emulator_catalog_machine_sourcefile
    ON emulator_catalog_machine(catalog_id, sourcefile);
CREATE INDEX IF NOT EXISTS idx_emulator_catalog_rom_machine
    ON emulator_catalog_rom(machine_id);
CREATE INDEX IF NOT EXISTS idx_emulator_catalog_rom_crc
    ON emulator_catalog_rom(crc);
CREATE INDEX IF NOT EXISTS idx_emulator_catalog_rom_sha1
    ON emulator_catalog_rom(sha1);
