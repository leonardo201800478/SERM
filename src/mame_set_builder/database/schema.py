"""
Esquema do banco de dados SQLite.
Define as tabelas e índices para armazenar o dataset do MAME.
"""

import sqlite3

# Script SQL para criação das tabelas
CREATE_TABLES = """
-- Tabela principal: dataset (versão do MAME e metadados)
CREATE TABLE IF NOT EXISTS dataset (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL UNIQUE,           -- versão do MAME (ex.: "0.289")
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_executable TEXT                  -- caminho do executável usado
);

-- Máquinas (cada entrada do listxml)
CREATE TABLE IF NOT EXISTS machine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id INTEGER NOT NULL,
    name TEXT NOT NULL,                     -- identificador único da máquina (ex.: "pacman")
    description TEXT,                       -- nome amigável
    year TEXT,
    manufacturer TEXT,
    cloneof TEXT,                           -- máquina da qual é clone
    romof TEXT,                             -- máquina da qual herda ROMs
    sampleof TEXT,                          -- máquina da qual herda samples
    isbios INTEGER DEFAULT 0,               -- booleano (0/1)
    isdevice INTEGER DEFAULT 0,
    ismechanical INTEGER DEFAULT 0,
    runnable INTEGER DEFAULT 1,
    sourcefile TEXT,                        -- arquivo fonte no MAME
    FOREIGN KEY(dataset_id) REFERENCES dataset(id)
);

-- ROMs (arquivos de ROM)
CREATE TABLE IF NOT EXISTS rom (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    name TEXT NOT NULL,                     -- nome do arquivo ROM
    size INTEGER,
    crc TEXT,
    sha1 TEXT,
    merge TEXT,                             -- para merged sets
    region TEXT,                            -- região de memória
    offset TEXT,
    status TEXT,                            -- "baddump", "nodump", etc.
    optional INTEGER DEFAULT 0,             -- 1 se for opcional
    bios TEXT,                              -- BIOS associada (se houver)
    FOREIGN KEY(machine_id) REFERENCES machine(id)
);

-- Discos (CHDs / hard disk images)
CREATE TABLE IF NOT EXISTS disk (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    sha1 TEXT,
    merge TEXT,
    region TEXT,
    disk_index INTEGER,                     -- renomeado de "index" para evitar palavra reservada
    writable INTEGER DEFAULT 0,
    status TEXT,
    optional INTEGER DEFAULT 0,
    FOREIGN KEY(machine_id) REFERENCES machine(id)
);

-- Driver (status de emulação)
CREATE TABLE IF NOT EXISTS driver (
    machine_id INTEGER PRIMARY KEY,
    status TEXT,                            -- "good", "imperfect", "preliminary"
    emulation TEXT,
    cocktail INTEGER DEFAULT 0,
    savestate INTEGER DEFAULT 0,
    requiresartwork INTEGER DEFAULT 0,
    unofficial INTEGER DEFAULT 0,
    nosoundhardware INTEGER DEFAULT 0,
    incomplete INTEGER DEFAULT 0,
    FOREIGN KEY(machine_id) REFERENCES machine(id)
);

-- Índices para acelerar consultas frequentes
CREATE INDEX IF NOT EXISTS idx_machine_name ON machine(name);
CREATE INDEX IF NOT EXISTS idx_machine_cloneof ON machine(cloneof);
CREATE INDEX IF NOT EXISTS idx_rom_crc ON rom(crc);
CREATE INDEX IF NOT EXISTS idx_rom_sha1 ON rom(sha1);
CREATE INDEX IF NOT EXISTS idx_disk_sha1 ON disk(sha1);
"""

def init_db(conn: sqlite3.Connection) -> None:
    """
    Inicializa o banco de dados criando todas as tabelas e índices.
    Deve ser chamado ao conectar a um novo banco.
    """
    conn.executescript(CREATE_TABLES)
    conn.commit()