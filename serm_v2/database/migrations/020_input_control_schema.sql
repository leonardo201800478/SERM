PRAGMA foreign_keys = ON;

-- Base física do subsistema de controles. A identidade do hardware é
-- independente do emulador que o utilizará.
CREATE TABLE IF NOT EXISTS input_device (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    device_type TEXT NOT NULL DEFAULT 'unknown',
    connection TEXT NOT NULL DEFAULT 'unknown',
    vendor_id INTEGER,
    product_id INTEGER,
    version INTEGER,
    serial TEXT,
    manufacturer TEXT,
    product TEXT,
    usage_page INTEGER,
    usage INTEGER,
    path TEXT,
    interface_number INTEGER,
    bus_type INTEGER,
    sdl_guid TEXT,
    sdl_mapping TEXT,
    backend TEXT NOT NULL DEFAULT 'unknown',
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
    metadata_json TEXT
);
CREATE INDEX IF NOT EXISTS ix_input_device_vid_pid ON input_device(vendor_id, product_id);
CREATE INDEX IF NOT EXISTS ix_input_device_sdl_guid ON input_device(sdl_guid);
CREATE INDEX IF NOT EXISTS ix_input_device_type ON input_device(device_type);

CREATE TABLE IF NOT EXISTS input_element (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES input_device(id) ON DELETE CASCADE,
    element_key TEXT NOT NULL,
    element_type TEXT NOT NULL,
    name TEXT NOT NULL,
    element_index INTEGER,
    logical_control TEXT,
    minimum INTEGER,
    maximum INTEGER,
    metadata_json TEXT,
    UNIQUE(device_id, element_key)
);
CREATE INDEX IF NOT EXISTS ix_input_element_device ON input_element(device_id);
CREATE INDEX IF NOT EXISTS ix_input_element_logical ON input_element(logical_control);

CREATE TABLE IF NOT EXISTS control_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    device_id INTEGER NOT NULL REFERENCES input_device(id) ON DELETE CASCADE,
    target_system TEXT,
    target_emulator TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    metadata_json TEXT
);
CREATE INDEX IF NOT EXISTS ix_control_profile_device ON control_profile(device_id);
CREATE INDEX IF NOT EXISTS ix_control_profile_target ON control_profile(target_system, target_emulator);

CREATE TABLE IF NOT EXISTS control_binding (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES control_profile(id) ON DELETE CASCADE,
    logical_control TEXT NOT NULL,
    physical_element TEXT NOT NULL,
    direction TEXT,
    modifier TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT,
    UNIQUE(profile_id, logical_control, physical_element, direction, modifier)
);
CREATE INDEX IF NOT EXISTS ix_control_binding_profile ON control_binding(profile_id);
CREATE INDEX IF NOT EXISTS ix_control_binding_logical ON control_binding(logical_control);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('020_input_control_schema', datetime('now'));
