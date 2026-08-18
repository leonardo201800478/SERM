-- MAME Set Builder - dataset pipeline v2
-- Operational metadata for a reproducible MAME dataset build.

CREATE TABLE IF NOT EXISTS dataset_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mame_installation_id INTEGER NOT NULL,
    mame_version TEXT NOT NULL,
    xml_path TEXT NOT NULL,
    xml_sha256 TEXT,
    catver_path TEXT,
    catver_sha256 TEXT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    machine_count INTEGER NOT NULL DEFAULT 0,
    rom_count INTEGER NOT NULL DEFAULT 0,
    disk_count INTEGER NOT NULL DEFAULT 0,
    chd_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    FOREIGN KEY (mame_installation_id) REFERENCES mame_installation(id)
);
CREATE INDEX IF NOT EXISTS idx_dataset_run_status ON dataset_run(status);
CREATE INDEX IF NOT EXISTS idx_dataset_run_version ON dataset_run(mame_version);

CREATE TABLE IF NOT EXISTS catver_entry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_run_id INTEGER,
    machine_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    main_category TEXT NOT NULL,
    sub_category TEXT,
    version_added TEXT,
    source TEXT NOT NULL DEFAULT 'catver.ini',
    UNIQUE(machine_id, source),
    FOREIGN KEY (dataset_run_id) REFERENCES dataset_run(id) ON DELETE SET NULL,
    FOREIGN KEY (machine_id) REFERENCES machine(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES category(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_catver_machine ON catver_entry(machine_id);
CREATE INDEX IF NOT EXISTS idx_catver_category ON catver_entry(category_id);

CREATE TABLE IF NOT EXISTS chd_scan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_run_id INTEGER,
    machine_id INTEGER NOT NULL,
    disk_id INTEGER,
    path TEXT NOT NULL,
    file_size INTEGER NOT NULL DEFAULT 0,
    header_sha1 TEXT,
    data_sha1 TEXT,
    verify_status TEXT NOT NULL DEFAULT 'not_checked',
    checked_at TEXT,
    error TEXT,
    UNIQUE(dataset_run_id, path),
    FOREIGN KEY (dataset_run_id) REFERENCES dataset_run(id) ON DELETE CASCADE,
    FOREIGN KEY (machine_id) REFERENCES machine(id) ON DELETE CASCADE,
    FOREIGN KEY (disk_id) REFERENCES disk(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_chd_scan_machine ON chd_scan(machine_id);
CREATE INDEX IF NOT EXISTS idx_chd_scan_status ON chd_scan(verify_status);

CREATE TABLE IF NOT EXISTS rom_source_match (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_run_id INTEGER,
    rom_id INTEGER,
    source_path TEXT NOT NULL,
    archive_member TEXT,
    source_kind TEXT NOT NULL,
    actual_size INTEGER,
    actual_crc TEXT,
    actual_sha1 TEXT,
    validation_status TEXT NOT NULL DEFAULT 'unscanned',
    bytes_read INTEGER NOT NULL DEFAULT 0,
    checked_at TEXT,
    error TEXT,
    UNIQUE(dataset_run_id, source_path, archive_member, rom_id),
    FOREIGN KEY (dataset_run_id) REFERENCES dataset_run(id) ON DELETE CASCADE,
    FOREIGN KEY (rom_id) REFERENCES rom(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_rom_source_match_rom ON rom_source_match(rom_id);
CREATE INDEX IF NOT EXISTS idx_rom_source_match_crc_size ON rom_source_match(actual_crc, actual_size);
CREATE INDEX IF NOT EXISTS idx_rom_source_match_sha1 ON rom_source_match(actual_sha1);

PRAGMA user_version = 2;
