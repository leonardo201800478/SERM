PRAGMA foreign_keys = ON;

-- Catálogo relacional derivado do ListXML.
-- O documento lossless continua sendo a fonte de verdade; estas tabelas
-- existem para filtros, construção de sets, reconstrução e consultas rápidas.

CREATE TABLE IF NOT EXISTS mame_rom (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    bios TEXT,
    size INTEGER,
    crc TEXT,
    sha1 TEXT,
    md5 TEXT,
    merge TEXT,
    region TEXT,
    offset TEXT,
    status TEXT,
    optional TEXT,
    dispose TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_rom_machine ON mame_rom(machine_id);
CREATE INDEX IF NOT EXISTS ix_mame_rom_crc ON mame_rom(crc);
CREATE INDEX IF NOT EXISTS ix_mame_rom_sha1 ON mame_rom(sha1);
CREATE INDEX IF NOT EXISTS ix_mame_rom_merge ON mame_rom(merge);

CREATE TABLE IF NOT EXISTS mame_disk (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
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
CREATE INDEX IF NOT EXISTS ix_mame_disk_machine ON mame_disk(machine_id);
CREATE INDEX IF NOT EXISTS ix_mame_disk_sha1 ON mame_disk(sha1);
CREATE INDEX IF NOT EXISTS ix_mame_disk_merge ON mame_disk(merge);

CREATE TABLE IF NOT EXISTS mame_sample (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_mame_sample_machine ON mame_sample(machine_id);

CREATE TABLE IF NOT EXISTS mame_biosset (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT,
    description TEXT,
    default_flag TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_biosset_machine ON mame_biosset(machine_id);

CREATE TABLE IF NOT EXISTS mame_device_ref (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT,
    tag TEXT,
    mandatory TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_device_ref_machine ON mame_device_ref(machine_id);

CREATE TABLE IF NOT EXISTS mame_chip (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    type TEXT,
    tag TEXT,
    name TEXT,
    clock TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_chip_machine ON mame_chip(machine_id);

CREATE TABLE IF NOT EXISTS mame_display (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    tag TEXT,
    type TEXT,
    rotate TEXT,
    width INTEGER,
    height INTEGER,
    refresh_hz REAL,
    refresh_raw TEXT,
    pixclock TEXT,
    htotal TEXT,
    hbend TEXT,
    hbstart TEXT,
    vtotal TEXT,
    vbend TEXT,
    vbstart TEXT,
    hsync TEXT,
    vsync TEXT,
    xaspect INTEGER,
    yaspect INTEGER,
    orientation_raw TEXT,
    source TEXT NOT NULL DEFAULT 'listxml',
    confidence TEXT NOT NULL DEFAULT 'authoritative'
);
CREATE INDEX IF NOT EXISTS ix_mame_display_machine ON mame_display(machine_id);
CREATE INDEX IF NOT EXISTS ix_mame_display_timing ON mame_display(refresh_hz);

CREATE TABLE IF NOT EXISTS mame_input (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    players INTEGER,
    coins INTEGER,
    service INTEGER,
    tilt INTEGER
);
CREATE INDEX IF NOT EXISTS ix_mame_input_machine ON mame_input(machine_id);

CREATE TABLE IF NOT EXISTS mame_control (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input_id INTEGER NOT NULL REFERENCES mame_input(id) ON DELETE CASCADE,
    type TEXT,
    player INTEGER,
    buttons INTEGER,
    minimum INTEGER,
    maximum INTEGER,
    sensitivity INTEGER,
    keydelta INTEGER,
    reverse TEXT,
    ways TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_control_input ON mame_control(input_id);

CREATE TABLE IF NOT EXISTS mame_dipswitch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT,
    tag TEXT,
    mask TEXT,
    value TEXT,
    default_value TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_dipswitch_machine ON mame_dipswitch(machine_id);

CREATE TABLE IF NOT EXISTS mame_dipvalue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dipswitch_id INTEGER NOT NULL REFERENCES mame_dipswitch(id) ON DELETE CASCADE,
    name TEXT,
    value TEXT,
    description TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_dipvalue_dipswitch ON mame_dipvalue(dipswitch_id);

CREATE TABLE IF NOT EXISTS mame_configuration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT,
    tag TEXT,
    mask TEXT,
    value TEXT,
    default_value TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_configuration_machine ON mame_configuration(machine_id);

CREATE TABLE IF NOT EXISTS mame_confsetting (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    configuration_id INTEGER NOT NULL REFERENCES mame_configuration(id) ON DELETE CASCADE,
    name TEXT,
    value TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_confsetting_configuration ON mame_confsetting(configuration_id);

CREATE TABLE IF NOT EXISTS mame_port (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    tag TEXT,
    type TEXT,
    mask TEXT,
    defvalue TEXT,
    condition TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_port_machine ON mame_port(machine_id);

CREATE TABLE IF NOT EXISTS mame_adjuster (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT,
    default_value TEXT,
    min_value TEXT,
    max_value TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_adjuster_machine ON mame_adjuster(machine_id);

CREATE TABLE IF NOT EXISTS mame_driver (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    status TEXT,
    emulation TEXT,
    color TEXT,
    sound TEXT,
    graphic TEXT,
    cocktail TEXT,
    protection TEXT,
    savestate TEXT,
    requires_artwork TEXT,
    unofficial TEXT,
    incomplete TEXT,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_driver_machine ON mame_driver(machine_id);

CREATE TABLE IF NOT EXISTS mame_feature (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    type TEXT,
    status TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_feature_machine ON mame_feature(machine_id);

CREATE TABLE IF NOT EXISTS mame_device (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    type TEXT,
    tag TEXT,
    name TEXT,
    clock TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_device_machine ON mame_device(machine_id);

CREATE TABLE IF NOT EXISTS mame_slot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_mame_slot_machine ON mame_slot(machine_id);

CREATE TABLE IF NOT EXISTS mame_slot_option (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id INTEGER NOT NULL REFERENCES mame_slot(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    devname TEXT,
    is_default TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_slot_option_slot ON mame_slot_option(slot_id);

CREATE TABLE IF NOT EXISTS mame_softwarelist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    tag TEXT,
    name TEXT,
    status TEXT,
    filter TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_softwarelist_machine ON mame_softwarelist(machine_id);

CREATE TABLE IF NOT EXISTS mame_ramoption (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT,
    default_value TEXT
);
CREATE INDEX IF NOT EXISTS ix_mame_ramoption_machine ON mame_ramoption(machine_id);

-- Campos adicionais do elemento machine usados pelo Set Builder.
ALTER TABLE mame_machine ADD COLUMN emulation_status TEXT;
ALTER TABLE mame_machine ADD COLUMN driver_status TEXT;
ALTER TABLE mame_machine ADD COLUMN savestate TEXT;
ALTER TABLE mame_machine ADD COLUMN requires_artwork TEXT;
ALTER TABLE mame_machine ADD COLUMN unofficial TEXT;
ALTER TABLE mame_machine ADD COLUMN nosoundhardware TEXT;
ALTER TABLE mame_machine ADD COLUMN incomplete TEXT;

CREATE INDEX IF NOT EXISTS ix_mame_machine_clone ON mame_machine(import_id, cloneof);
CREATE INDEX IF NOT EXISTS ix_mame_machine_romof ON mame_machine(import_id, romof);
CREATE INDEX IF NOT EXISTS ix_mame_machine_flags ON mame_machine(import_id, isbios, isdevice, ismechanical, runnable);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('011_mame_catalog_complete', datetime('now'));
