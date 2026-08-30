PRAGMA foreign_keys = ON;

-- Raw ListXML preservation. This is the lossless source layer: every XML
-- element, attribute and text value is stored, even when a future MAME build
-- introduces fields that SERM does not yet understand.
CREATE TABLE IF NOT EXISTS mame_listxml_import (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emulator_id INTEGER NOT NULL REFERENCES emulator_definition(id) ON DELETE CASCADE,
    executable TEXT NOT NULL,
    mame_build TEXT,
    mame_config TEXT,
    debug TEXT,
    imported_at TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    xml_path TEXT,
    machine_count INTEGER NOT NULL DEFAULT 0,
    parser_version TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_mame_listxml_import_hash
    ON mame_listxml_import(source_hash);

CREATE TABLE IF NOT EXISTS mame_xml_node (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER NOT NULL REFERENCES mame_listxml_import(id) ON DELETE CASCADE,
    parent_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE CASCADE,
    machine_id INTEGER,
    element_name TEXT NOT NULL,
    ordinal INTEGER NOT NULL DEFAULT 0,
    xml_path TEXT NOT NULL,
    text_value TEXT,
    attributes_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(import_id, xml_path)
);

CREATE INDEX IF NOT EXISTS ix_mame_xml_node_machine
    ON mame_xml_node(import_id, machine_id);
CREATE INDEX IF NOT EXISTS ix_mame_xml_node_element
    ON mame_xml_node(import_id, element_name);

CREATE TABLE IF NOT EXISTS mame_machine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id INTEGER NOT NULL REFERENCES mame_listxml_import(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sourcefile TEXT,
    isdevice TEXT,
    runnable TEXT,
    cloneof TEXT,
    romof TEXT,
    sampleof TEXT,
    description TEXT,
    year TEXT,
    manufacturer TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL,
    UNIQUE(import_id, name)
);

CREATE INDEX IF NOT EXISTS ix_mame_machine_name
    ON mame_machine(name);
CREATE INDEX IF NOT EXISTS ix_mame_machine_clone
    ON mame_machine(import_id, cloneof);
CREATE INDEX IF NOT EXISTS ix_mame_machine_source
    ON mame_machine(import_id, sourcefile);

CREATE TABLE IF NOT EXISTS mame_biosset (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT,
    description TEXT,
    default_value TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mame_rom (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT,
    bios TEXT,
    size TEXT,
    crc TEXT,
    sha1 TEXT,
    md5 TEXT,
    merge TEXT,
    region TEXT,
    offset TEXT,
    status TEXT,
    optional TEXT,
    dispose TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_mame_rom_machine
    ON mame_rom(machine_id);
CREATE INDEX IF NOT EXISTS ix_mame_rom_hash
    ON mame_rom(sha1, crc);

CREATE TABLE IF NOT EXISTS mame_disk (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT,
    md5 TEXT,
    sha1 TEXT,
    merge TEXT,
    region TEXT,
    index_value TEXT,
    writable TEXT,
    status TEXT,
    optional TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mame_device_ref (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT,
    tag TEXT,
    mandatory TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mame_sample (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mame_chip (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    type TEXT,
    name TEXT,
    clock TEXT,
    tag TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mame_sound (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    channels TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

-- Display is the canonical source for the Timing Advisor. A machine may have
-- multiple emulated screens.
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
    confidence TEXT NOT NULL DEFAULT 'authoritative',
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_mame_display_machine
    ON mame_display(machine_id);
CREATE INDEX IF NOT EXISTS ix_mame_display_geometry
    ON mame_display(width, height, refresh_hz);

CREATE TABLE IF NOT EXISTS mame_input (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    players TEXT,
    buttons TEXT,
    coins TEXT,
    service TEXT,
    tilt TEXT,
    control_type TEXT,
    ways TEXT,
    minimum TEXT,
    maximum TEXT,
    sensitivity TEXT,
    keydelta TEXT,
    reverse TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mame_dipswitch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT,
    tag TEXT,
    mask TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mame_dipvalue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dipswitch_id INTEGER NOT NULL REFERENCES mame_dipswitch(id) ON DELETE CASCADE,
    name TEXT,
    value TEXT,
    default_value TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mame_configuration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT,
    tag TEXT,
    mask TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mame_configvalue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    configuration_id INTEGER NOT NULL REFERENCES mame_configuration(id) ON DELETE CASCADE,
    name TEXT,
    value TEXT,
    default_value TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mame_port (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    tag TEXT,
    type TEXT,
    mask TEXT,
    defvalue TEXT,
    value TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mame_adjuster (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT,
    default_value TEXT,
    minimum TEXT,
    maximum TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

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
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mame_feature (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    type TEXT,
    status TEXT,
    overall TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mame_device (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    type TEXT,
    tag TEXT,
    clock TEXT,
    shortname TEXT,
    name TEXT,
    fixed_image TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mame_slot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT,
    tag TEXT,
    fixed TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mame_slotoption (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id INTEGER NOT NULL REFERENCES mame_slot(id) ON DELETE CASCADE,
    name TEXT,
    devname TEXT,
    default_value TEXT,
    selectable TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mame_softwarelist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    tag TEXT,
    name TEXT,
    status TEXT,
    filter TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mame_ramoption (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    name TEXT,
    default_value TEXT,
    xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
);

-- External display facts. They are intentionally separate from ListXML so
-- provenance and fallback decisions remain explicit.
CREATE TABLE IF NOT EXISTS mame_display_source (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emulator_id INTEGER NOT NULL REFERENCES emulator_definition(id) ON DELETE CASCADE,
    source_name TEXT NOT NULL,
    source_path TEXT,
    source_hash TEXT,
    imported_at TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'imported'
);

CREATE TABLE IF NOT EXISTS mame_external_display_fact (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES mame_display_source(id) ON DELETE CASCADE,
    machine_name TEXT NOT NULL,
    resolution_width INTEGER,
    resolution_height INTEGER,
    refresh_hz REAL,
    refresh_raw TEXT,
    orientation TEXT,
    pixel_aspect_x INTEGER,
    pixel_aspect_y INTEGER,
    raw_value TEXT,
    line_number INTEGER,
    UNIQUE(source_id, machine_name)
);

CREATE INDEX IF NOT EXISTS ix_mame_external_display_machine
    ON mame_external_display_fact(machine_name);

CREATE TABLE IF NOT EXISTS mame_display_resolution (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    display_id INTEGER REFERENCES mame_display(id) ON DELETE CASCADE,
    width INTEGER,
    height INTEGER,
    refresh_hz REAL,
    orientation TEXT,
    pixel_aspect_x INTEGER,
    pixel_aspect_y INTEGER,
    resolution_source TEXT NOT NULL,
    refresh_source TEXT NOT NULL,
    orientation_source TEXT NOT NULL,
    pixel_aspect_source TEXT NOT NULL,
    resolution_confidence TEXT NOT NULL,
    refresh_confidence TEXT NOT NULL,
    orientation_confidence TEXT NOT NULL,
    pixel_aspect_confidence TEXT NOT NULL,
    fallback_used INTEGER NOT NULL DEFAULT 0 CHECK (fallback_used IN (0,1)),
    compared_at TEXT NOT NULL,
    UNIQUE(machine_id, display_id)
);

CREATE TABLE IF NOT EXISTS mame_display_comparison (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    display_id INTEGER REFERENCES mame_display(id) ON DELETE SET NULL,
    source_a TEXT NOT NULL,
    source_b TEXT NOT NULL,
    field_name TEXT NOT NULL,
    value_a TEXT,
    value_b TEXT,
    result TEXT NOT NULL,
    detail TEXT,
    compared_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_mame_display_comparison_machine
    ON mame_display_comparison(machine_id, field_name);

CREATE TABLE IF NOT EXISTS mame_machine_display_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES mame_machine(id) ON DELETE CASCADE,
    display_id INTEGER REFERENCES mame_display(id) ON DELETE SET NULL,
    profile_version TEXT NOT NULL,
    width INTEGER,
    height INTEGER,
    refresh_hz REAL,
    orientation TEXT,
    pixel_aspect_x INTEGER,
    pixel_aspect_y INTEGER,
    source_resolution TEXT,
    source_refresh TEXT,
    source_orientation TEXT,
    source_pixel_aspect TEXT,
    fallback_used INTEGER NOT NULL DEFAULT 0 CHECK (fallback_used IN (0,1)),
    status TEXT NOT NULL DEFAULT 'resolved',
    generated_at TEXT NOT NULL,
    UNIQUE(machine_id, display_id, profile_version)
);

CREATE INDEX IF NOT EXISTS ix_mame_machine_display_profile_machine
    ON mame_machine_display_profile(machine_id);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('003_mame_catalog_schema', datetime('now'));
