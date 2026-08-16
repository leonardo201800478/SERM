-- ========================================================================
-- MAME SET BUILDER
-- SCHEMA COMPLETO DO BANCO DE DADOS
-- ========================================================================
--
-- Versão: 1.1
--
-- Este arquivo é o schema oficial da aplicação.
--
-- IMPORTANTE:
--   O database.py carrega este arquivo automaticamente.
--
-- Estrutura:
--
--   mame_installation
--       |
--       +-- machine
--              |
--              +-- rom
--              +-- disk
--              +-- bios
--              +-- device
--              +-- chip
--              +-- display
--              +-- input
--              |     |
--              |     +-- control
--              +-- feature
--              +-- software_list
--              +-- slot
--              |     |
--              |     +-- slot_option
--              +-- chd_dependency
--              +-- machine_category
--
--   category
--
--   filter_profile
--
-- ========================================================================


-- ========================================================================
-- 1. INSTALAÇÃO DO MAME
-- ========================================================================

CREATE TABLE IF NOT EXISTS mame_installation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    version TEXT NOT NULL,

    executable_path TEXT UNIQUE NOT NULL,

    executable_hash TEXT NOT NULL,

    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ========================================================================
-- 2. MÁQUINAS
-- ========================================================================

CREATE TABLE IF NOT EXISTS machine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    mame_installation_id INTEGER NOT NULL,

    name TEXT UNIQUE NOT NULL,

    description TEXT,

    year TEXT,

    manufacturer TEXT,

    sourcefile TEXT,

    cloneof TEXT,

    romof TEXT,

    sampleof TEXT,

    is_bios INTEGER DEFAULT 0,

    is_device INTEGER DEFAULT 0,

    is_mechanical INTEGER DEFAULT 0,

    runnable INTEGER DEFAULT 1,

    emulation_status TEXT,

    driver_status TEXT,

    savestate INTEGER DEFAULT 0,

    requires_artwork INTEGER DEFAULT 0,

    unofficial INTEGER DEFAULT 0,

    nosoundhardware INTEGER DEFAULT 0,

    incomplete INTEGER DEFAULT 0,

    FOREIGN KEY (
        mame_installation_id
    )
    REFERENCES mame_installation(id)
    ON DELETE CASCADE
);


-- ========================================================================
-- 3. ROMS
-- ========================================================================

CREATE TABLE IF NOT EXISTS rom (
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

    FOREIGN KEY (
        machine_id
    )
    REFERENCES machine(id)
    ON DELETE CASCADE
);


-- ========================================================================
-- 4. DISKS / CHD / HDD / CD / LD
-- ========================================================================
--
-- IMPORTANTE:
--
-- A coluna "size" armazena o tamanho real do arquivo CHD encontrado
-- pelo scanner.
--
-- O MAME -listxml não fornece necessariamente o tamanho físico do CHD.
-- Essa informação é obtida durante o Scan ROMs.
--
-- A coluna "disk_index" substitui a antiga coluna "index".
--
-- ========================================================================

CREATE TABLE IF NOT EXISTS disk (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    machine_id INTEGER NOT NULL,

    name TEXT NOT NULL,

    sha1 TEXT,

    merge TEXT,

    region TEXT,

    disk_index INTEGER DEFAULT 0,

    writable INTEGER DEFAULT 0,

    status TEXT DEFAULT 'good',

    optional INTEGER DEFAULT 0,

    size INTEGER DEFAULT 0,

    FOREIGN KEY (
        machine_id
    )
    REFERENCES machine(id)
    ON DELETE CASCADE
);


-- ========================================================================
-- 5. BIOS
-- ========================================================================

CREATE TABLE IF NOT EXISTS bios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    machine_id INTEGER NOT NULL,

    name TEXT NOT NULL,

    description TEXT,

    is_default INTEGER DEFAULT 0,

    FOREIGN KEY (
        machine_id
    )
    REFERENCES machine(id)
    ON DELETE CASCADE
);


-- ========================================================================
-- 6. DEVICES
-- ========================================================================

CREATE TABLE IF NOT EXISTS device (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    machine_id INTEGER NOT NULL,

    tag TEXT,

    name TEXT,

    FOREIGN KEY (
        machine_id
    )
    REFERENCES machine(id)
    ON DELETE CASCADE
);


-- ========================================================================
-- 7. CHIPS
-- ========================================================================

CREATE TABLE IF NOT EXISTS chip (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    machine_id INTEGER NOT NULL,

    type TEXT,

    tag TEXT,

    name TEXT,

    clock INTEGER,

    FOREIGN KEY (
        machine_id
    )
    REFERENCES machine(id)
    ON DELETE CASCADE
);


-- ========================================================================
-- 8. DISPLAYS
-- ========================================================================

CREATE TABLE IF NOT EXISTS display (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    machine_id INTEGER NOT NULL,

    tag TEXT,

    type TEXT,

    rotate INTEGER DEFAULT 0,

    flipx INTEGER DEFAULT 0,

    width INTEGER,

    height INTEGER,

    refresh REAL,

    FOREIGN KEY (
        machine_id
    )
    REFERENCES machine(id)
    ON DELETE CASCADE
);


-- ========================================================================
-- 9. INPUTS
-- ========================================================================

CREATE TABLE IF NOT EXISTS input (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    machine_id INTEGER NOT NULL,

    players INTEGER DEFAULT 1,

    coins INTEGER DEFAULT 0,

    service INTEGER DEFAULT 0,

    tilt INTEGER DEFAULT 0,

    FOREIGN KEY (
        machine_id
    )
    REFERENCES machine(id)
    ON DELETE CASCADE
);


-- ========================================================================
-- 10. CONTROLS
-- ========================================================================

CREATE TABLE IF NOT EXISTS control (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    input_id INTEGER NOT NULL,

    type TEXT,

    player INTEGER DEFAULT 0,

    buttons INTEGER,

    minimum INTEGER,

    maximum INTEGER,

    sensitivity INTEGER,

    keydelta INTEGER,

    reverse INTEGER DEFAULT 0,

    ways INTEGER,

    FOREIGN KEY (
        input_id
    )
    REFERENCES input(id)
    ON DELETE CASCADE
);


-- ========================================================================
-- 11. FEATURES
-- ========================================================================

CREATE TABLE IF NOT EXISTS feature (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    machine_id INTEGER NOT NULL,

    type TEXT,

    status TEXT,

    overall TEXT,

    FOREIGN KEY (
        machine_id
    )
    REFERENCES machine(id)
    ON DELETE CASCADE
);


-- ========================================================================
-- 12. SOFTWARE LISTS
-- ========================================================================

CREATE TABLE IF NOT EXISTS software_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    machine_id INTEGER NOT NULL,

    tag TEXT,

    name TEXT,

    status TEXT,

    filter TEXT,

    FOREIGN KEY (
        machine_id
    )
    REFERENCES machine(id)
    ON DELETE CASCADE
);


-- ========================================================================
-- 13. SLOTS
-- ========================================================================

CREATE TABLE IF NOT EXISTS slot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    machine_id INTEGER NOT NULL,

    name TEXT NOT NULL,

    FOREIGN KEY (
        machine_id
    )
    REFERENCES machine(id)
    ON DELETE CASCADE
);


-- ========================================================================
-- 14. SLOT OPTIONS
-- ========================================================================

CREATE TABLE IF NOT EXISTS slot_option (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    slot_id INTEGER NOT NULL,

    name TEXT NOT NULL,

    devname TEXT,

    is_default INTEGER DEFAULT 0,

    FOREIGN KEY (
        slot_id
    )
    REFERENCES slot(id)
    ON DELETE CASCADE
);


-- ========================================================================
-- 15. CHD DEPENDENCIES
-- ========================================================================

CREATE TABLE IF NOT EXISTS chd_dependency (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    machine_id INTEGER NOT NULL,

    name TEXT NOT NULL,

    sha1 TEXT,

    region TEXT,

    required INTEGER DEFAULT 1,

    FOREIGN KEY (
        machine_id
    )
    REFERENCES machine(id)
    ON DELETE CASCADE
);


-- ========================================================================
-- 16. CATEGORIAS
-- ========================================================================

CREATE TABLE IF NOT EXISTS category (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT UNIQUE NOT NULL,

    display_name TEXT NOT NULL,

    source TEXT DEFAULT 'manual'
);


-- ========================================================================
-- 17. MACHINE -> CATEGORY
-- ========================================================================

CREATE TABLE IF NOT EXISTS machine_category (
    machine_id INTEGER NOT NULL,

    category_id INTEGER NOT NULL,

    PRIMARY KEY (
        machine_id,
        category_id
    ),

    FOREIGN KEY (
        machine_id
    )
    REFERENCES machine(id)
    ON DELETE CASCADE,

    FOREIGN KEY (
        category_id
    )
    REFERENCES category(id)
    ON DELETE CASCADE
);


-- ========================================================================
-- 18. PERFIS DE FILTRO
-- ========================================================================

CREATE TABLE IF NOT EXISTS filter_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL,

    description TEXT,

    profile_data TEXT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    is_default INTEGER DEFAULT 0
);


-- ========================================================================
-- ÍNDICES - MACHINE
-- ========================================================================

CREATE INDEX IF NOT EXISTS
    idx_machine_name
    ON machine(name);


CREATE INDEX IF NOT EXISTS
    idx_machine_cloneof
    ON machine(cloneof);


CREATE INDEX IF NOT EXISTS
    idx_machine_romof
    ON machine(romof);


CREATE INDEX IF NOT EXISTS
    idx_machine_sourcefile
    ON machine(sourcefile);


CREATE INDEX IF NOT EXISTS
    idx_machine_emulation_status
    ON machine(emulation_status);


CREATE INDEX IF NOT EXISTS
    idx_machine_driver_status
    ON machine(driver_status);


CREATE INDEX IF NOT EXISTS
    idx_machine_is_bios
    ON machine(is_bios);


CREATE INDEX IF NOT EXISTS
    idx_machine_is_device
    ON machine(is_device);


CREATE INDEX IF NOT EXISTS
    idx_machine_is_mechanical
    ON machine(is_mechanical);


-- ========================================================================
-- ÍNDICES - ROM
-- ========================================================================

CREATE INDEX IF NOT EXISTS
    idx_rom_machine_id
    ON rom(machine_id);


CREATE INDEX IF NOT EXISTS
    idx_rom_name
    ON rom(name);


CREATE INDEX IF NOT EXISTS
    idx_rom_crc
    ON rom(crc);


CREATE INDEX IF NOT EXISTS
    idx_rom_sha1
    ON rom(sha1);


CREATE INDEX IF NOT EXISTS
    idx_rom_crc_size
    ON rom(crc, size);


CREATE INDEX IF NOT EXISTS
    idx_rom_merge
    ON rom(merge);


-- ========================================================================
-- ÍNDICES - DISK
-- ========================================================================

CREATE INDEX IF NOT EXISTS
    idx_disk_machine_id
    ON disk(machine_id);


CREATE INDEX IF NOT EXISTS
    idx_disk_name
    ON disk(name);


CREATE INDEX IF NOT EXISTS
    idx_disk_sha1
    ON disk(sha1);


CREATE INDEX IF NOT EXISTS
    idx_disk_merge
    ON disk(merge);


-- ========================================================================
-- ÍNDICES - BIOS
-- ========================================================================

CREATE INDEX IF NOT EXISTS
    idx_bios_machine_id
    ON bios(machine_id);


CREATE INDEX IF NOT EXISTS
    idx_bios_name
    ON bios(name);


-- ========================================================================
-- ÍNDICES - DEVICES
-- ========================================================================

CREATE INDEX IF NOT EXISTS
    idx_device_machine_id
    ON device(machine_id);


-- ========================================================================
-- ÍNDICES - CHIPS
-- ========================================================================

CREATE INDEX IF NOT EXISTS
    idx_chip_machine_id
    ON chip(machine_id);


-- ========================================================================
-- ÍNDICES - DISPLAYS
-- ========================================================================

CREATE INDEX IF NOT EXISTS
    idx_display_machine_id
    ON display(machine_id);


-- ========================================================================
-- ÍNDICES - INPUTS
-- ========================================================================

CREATE INDEX IF NOT EXISTS
    idx_input_machine_id
    ON input(machine_id);


-- ========================================================================
-- ÍNDICES - CONTROLS
-- ========================================================================

CREATE INDEX IF NOT EXISTS
    idx_control_input_id
    ON control(input_id);


-- ========================================================================
-- ÍNDICES - FEATURES
-- ========================================================================

CREATE INDEX IF NOT EXISTS
    idx_feature_machine_id
    ON feature(machine_id);


-- ========================================================================
-- ÍNDICES - SOFTWARE LIST
-- ========================================================================

CREATE INDEX IF NOT EXISTS
    idx_software_list_machine_id
    ON software_list(machine_id);


-- ========================================================================
-- ÍNDICES - SLOTS
-- ========================================================================

CREATE INDEX IF NOT EXISTS
    idx_slot_machine_id
    ON slot(machine_id);


-- ========================================================================
-- ÍNDICES - SLOT OPTIONS
-- ========================================================================

CREATE INDEX IF NOT EXISTS
    idx_slot_option_slot_id
    ON slot_option(slot_id);


-- ========================================================================
-- ÍNDICES - CHD DEPENDENCIES
-- ========================================================================

CREATE INDEX IF NOT EXISTS
    idx_chd_dependency_machine_id
    ON chd_dependency(machine_id);


CREATE INDEX IF NOT EXISTS
    idx_chd_dependency_sha1
    ON chd_dependency(sha1);


-- ========================================================================
-- ÍNDICES - MACHINE CATEGORY
-- ========================================================================

CREATE INDEX IF NOT EXISTS
    idx_machine_category_machine
    ON machine_category(machine_id);


CREATE INDEX IF NOT EXISTS
    idx_machine_category_category
    ON machine_category(category_id);


-- ========================================================================
-- CATEGORIAS INICIAIS
-- ========================================================================
--
-- Essas categorias são a base utilizada pela camada de filtros.
--
-- O parser pode posteriormente associar máquinas às categorias
-- conforme os dados presentes no LISTXML e/ou regras do projeto.
--
-- INSERT OR IGNORE garante que a inicialização do schema seja
-- idempotente.
--
-- ========================================================================

INSERT OR IGNORE INTO category
    (name, display_name, source)
VALUES
    ('arcade', 'Arcade', 'manual'),

    ('system', 'System', 'manual'),

    ('bios', 'BIOS', 'manual'),

    ('devices', 'Devices', 'manual'),

    ('electromechanical', 'Electromechanical', 'manual'),

    ('casino', 'Casino', 'manual'),

    ('mahjong', 'Mahjong', 'manual'),

    ('screenless', 'Screenless', 'manual'),

    ('mature', 'Mature', 'manual'),

    ('driving', 'Driving', 'manual'),

    ('fighter', 'Fighter', 'manual'),

    ('gambling', 'Gambling', 'manual'),

    ('game_console', 'Game Console', 'manual'),

    ('chd', 'CHD', 'manual'),

    ('ball_paddle', 'Ball & Paddle', 'manual'),

    ('board_game', 'Board Game', 'manual'),

    ('calculator', 'Calculator', 'manual'),

    ('card_games', 'Card Games', 'manual'),

    ('maze', 'Maze', 'manual'),

    ('handheld', 'Handheld', 'manual'),

    ('climbing', 'Climbing', 'manual'),

    ('medal_game', 'Medal Game', 'manual'),

    ('musical', 'Musical', 'manual'),

    ('platform', 'Platform', 'manual'),

    ('shooter', 'Shooter', 'manual'),

    ('slot_machine', 'Slot Machine', 'manual'),

    ('sports', 'Sports', 'manual'),

    ('tabletop', 'Tabletop', 'manual'),

    ('telephone', 'Telephone', 'manual');