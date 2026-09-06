PRAGMA foreign_keys = ON;

-- A tabela de filtros referencia o scan bruto, mas nunca o modifica.
-- scan_runs recebe catalog_label/scan_type/scan_file_path por migração
-- compatível executada pelo ScanRepository, pois SQLite não possui
-- ALTER TABLE ... ADD COLUMN IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS filter_runs (
    filter_run_id TEXT PRIMARY KEY,
    scan_id TEXT NOT NULL REFERENCES scan_runs(scan_id) ON DELETE CASCADE,
    profile_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    filtered_file_path TEXT NOT NULL,
    input_count INTEGER NOT NULL DEFAULT 0,
    output_count INTEGER NOT NULL DEFAULT 0,
    status_counts_json TEXT NOT NULL DEFAULT '{}',
    filters_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_filter_runs_scan ON filter_runs(scan_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_filter_runs_profile ON filter_runs(profile_id, created_at DESC);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES ('014_scan_filter_pipeline', datetime('now'));
