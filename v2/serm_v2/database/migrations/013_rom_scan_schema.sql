PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS scan_runs (
    scan_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    profile_schema_version INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL,
    system TEXT NOT NULL,
    dat_path TEXT,
    catalog_hash TEXT,
    status TEXT NOT NULL CHECK(status IN ('running','completed','failed','cancelled')),
    started_at REAL NOT NULL,
    finished_at REAL,
    files_examined INTEGER NOT NULL DEFAULT 0,
    archives_examined INTEGER NOT NULL DEFAULT 0,
    items_examined INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    status_counts_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_scan_runs_profile ON scan_runs(profile_id, started_at DESC);
CREATE INDEX IF NOT EXISTS ix_scan_runs_status ON scan_runs(status, started_at DESC);

CREATE TABLE IF NOT EXISTS scan_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id TEXT NOT NULL REFERENCES scan_runs(scan_id) ON DELETE CASCADE,
    machine_name TEXT,
    rom_name TEXT,
    item_type TEXT NOT NULL DEFAULT 'ROM',
    status TEXT NOT NULL,
    expected_size INTEGER,
    actual_size INTEGER,
    expected_crc TEXT,
    actual_crc TEXT,
    expected_sha1 TEXT,
    actual_sha1 TEXT,
    expected_md5 TEXT,
    actual_md5 TEXT,
    path TEXT,
    archive_path TEXT,
    archive_member TEXT,
    merge_name TEXT,
    optional INTEGER NOT NULL DEFAULT 0,
    message TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS ix_scan_items_scan_status ON scan_items(scan_id, status);
CREATE INDEX IF NOT EXISTS ix_scan_items_machine ON scan_items(scan_id, machine_name);
CREATE INDEX IF NOT EXISTS ix_scan_items_crc ON scan_items(expected_crc, actual_crc);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('013_rom_scan_schema', datetime('now'));
