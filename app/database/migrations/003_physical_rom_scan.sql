CREATE TABLE IF NOT EXISTS rom_scan_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_run_id INTEGER,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    source_count INTEGER NOT NULL DEFAULT 0,
    archive_count INTEGER NOT NULL DEFAULT 0,
    member_count INTEGER NOT NULL DEFAULT 0,
    loose_file_count INTEGER NOT NULL DEFAULT 0,
    bytes_read INTEGER NOT NULL DEFAULT 0,
    valid_match_count INTEGER NOT NULL DEFAULT 0,
    unmatched_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    FOREIGN KEY(dataset_run_id) REFERENCES dataset_run(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_rom_scan_run_status ON rom_scan_run(status);
CREATE INDEX IF NOT EXISTS idx_rom_scan_run_dataset ON rom_scan_run(dataset_run_id);
