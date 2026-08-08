# src/mame_set_builder/database/schema.py
import sqlite3

CREATE_TABLES = """
-- Dataset (versão e metadados)
CREATE TABLE IF NOT EXISTS dataset (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL UNIQUE,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_executable TEXT
);

-- Máquinas
CREATE TABLE IF NOT EXISTS machine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    year TEXT,
    manufacturer TEXT,
    cloneof TEXT,
    romof TEXT,
    sampleof TEXT,
    isbios INTEGER DEFAULT 0,
    isdevice INTEGER DEFAULT 0,
    ismechanical INTEGER DEFAULT 0,
    runnable INTEGER DEFAULT 1,
    sourcefile TEXT,
    FOREIGN KEY(dataset_id) REFERENCES dataset(id)
);

-- ROMs
CREATE TABLE IF NOT EXISTS rom (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    size INTEGER,
    crc TEXT,
    sha1 TEXT,
    merge TEXT,
    region TEXT,
    offset TEXT,
    status TEXT,
    optional INTEGER DEFAULT 0,
    bios TEXT,
    FOREIGN KEY(machine_id) REFERENCES machine(id)
);

-- Disks
CREATE TABLE IF NOT EXISTS disk (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    sha1 TEXT,
    merge TEXT,
    region TEXT,
    index INTEGER,
    writable INTEGER DEFAULT 0,
    status TEXT,
    optional INTEGER DEFAULT 0,
    FOREIGN KEY(machine_id) REFERENCES machine(id)
);

-- Driver (informações de status de emulação)
CREATE TABLE IF NOT EXISTS driver (
    machine_id INTEGER PRIMARY KEY,
    status TEXT,
    emulation TEXT,
    cocktail INTEGER DEFAULT 0,
    savestate INTEGER DEFAULT 0,
    requiresartwork INTEGER DEFAULT 0,
    unofficial INTEGER DEFAULT 0,
    nosoundhardware INTEGER DEFAULT 0,
    incomplete INTEGER DEFAULT 0,
    FOREIGN KEY(machine_id) REFERENCES machine(id)
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_machine_name ON machine(name);
CREATE INDEX IF NOT EXISTS idx_machine_cloneof ON machine(cloneof);
CREATE INDEX IF NOT EXISTS idx_rom_crc ON rom(crc);
CREATE INDEX IF NOT EXISTS idx_rom_sha1 ON rom(sha1);
CREATE INDEX IF NOT EXISTS idx_disk_sha1 ON disk(sha1);
"""

def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(CREATE_TABLES)
    conn.commit()