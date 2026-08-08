"""
Esquema completo do banco de dados SQLite para o MAME Set Builder (Fase 2).
Inclui tabelas para todas as informações do listxml.
"""

import sqlite3

CREATE_TABLES = """
-- Tabela dataset (já existente)
CREATE TABLE IF NOT EXISTS dataset (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL UNIQUE,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_executable TEXT
);

-- Tabela machine (já existente, com mais campos opcionais)
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
    disk_index INTEGER,
    writable INTEGER DEFAULT 0,
    status TEXT,
    optional INTEGER DEFAULT 0,
    FOREIGN KEY(machine_id) REFERENCES machine(id)
);

-- Driver (status de emulação)
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

-- ==================== NOVAS TABELAS (FASE 2) ====================

-- Input (portas e controles)
CREATE TABLE IF NOT EXISTS input (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    service INTEGER DEFAULT 0,
    tilt INTEGER DEFAULT 0,
    coin INTEGER DEFAULT 0,
    FOREIGN KEY(machine_id) REFERENCES machine(id)
);

-- Portas de entrada (detalhamento)
CREATE TABLE IF NOT EXISTS input_port (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input_id INTEGER NOT NULL,
    tag TEXT,
    type TEXT,
    mask INTEGER,
    defvalue INTEGER,
    FOREIGN KEY(input_id) REFERENCES input(id)
);

-- Dip switches
CREATE TABLE IF NOT EXISTS dipswitch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input_id INTEGER NOT NULL,
    tag TEXT,
    name TEXT,
    mask INTEGER,
    defvalue INTEGER,
    FOREIGN KEY(input_id) REFERENCES input(id)
);

-- Configurações
CREATE TABLE IF NOT EXISTS configuration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input_id INTEGER NOT NULL,
    tag TEXT,
    name TEXT,
    mask INTEGER,
    defvalue INTEGER,
    FOREIGN KEY(input_id) REFERENCES input(id)
);

-- Display
CREATE TABLE IF NOT EXISTS display (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    tag TEXT,
    type TEXT,
    rotate INTEGER DEFAULT 0,
    width INTEGER,
    height INTEGER,
    refresh REAL,
    pixclock INTEGER,
    htotal INTEGER,
    vtotal INTEGER,
    FOREIGN KEY(machine_id) REFERENCES machine(id)
);

-- Sound
CREATE TABLE IF NOT EXISTS sound (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    channels INTEGER DEFAULT 0,
    FOREIGN KEY(machine_id) REFERENCES machine(id)
);

-- Chips (CPU, sound, etc.)
CREATE TABLE IF NOT EXISTS chip (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    tag TEXT,
    type TEXT,
    name TEXT,
    clock INTEGER,
    FOREIGN KEY(machine_id) REFERENCES machine(id)
);

-- Device references
CREATE TABLE IF NOT EXISTS device_ref (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    name TEXT,
    FOREIGN KEY(machine_id) REFERENCES machine(id)
);

-- Slots
CREATE TABLE IF NOT EXISTS slot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    name TEXT,
    FOREIGN KEY(machine_id) REFERENCES machine(id)
);

-- Opções de slot (corrigido: default -> is_default)
CREATE TABLE IF NOT EXISTS slot_option (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id INTEGER NOT NULL,
    name TEXT,
    devname TEXT,
    is_default INTEGER DEFAULT 0,
    FOREIGN KEY(slot_id) REFERENCES slot(id)
);

-- Software lists
CREATE TABLE IF NOT EXISTS softwarelist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    name TEXT,
    status TEXT,
    filter TEXT,
    FOREIGN KEY(machine_id) REFERENCES machine(id)
);

-- Features
CREATE TABLE IF NOT EXISTS feature (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    name TEXT,
    value TEXT,
    FOREIGN KEY(machine_id) REFERENCES machine(id)
);

-- RAM options (corrigido: default -> default_value)
CREATE TABLE IF NOT EXISTS ramoption (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    name TEXT,
    default_value TEXT,
    FOREIGN KEY(machine_id) REFERENCES machine(id)
);

-- ==================== ÍNDICES ====================
CREATE INDEX IF NOT EXISTS idx_machine_name ON machine(name);
CREATE INDEX IF NOT EXISTS idx_machine_cloneof ON machine(cloneof);
CREATE INDEX IF NOT EXISTS idx_rom_crc ON rom(crc);
CREATE INDEX IF NOT EXISTS idx_rom_sha1 ON rom(sha1);
CREATE INDEX IF NOT EXISTS idx_disk_sha1 ON disk(sha1);
CREATE INDEX IF NOT EXISTS idx_dipswitch_input ON dipswitch(input_id);
CREATE INDEX IF NOT EXISTS idx_chip_machine ON chip(machine_id);
CREATE INDEX IF NOT EXISTS idx_device_ref_machine ON device_ref(machine_id);
CREATE INDEX IF NOT EXISTS idx_slot_machine ON slot(machine_id);
"""

def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(CREATE_TABLES)
    conn.commit()