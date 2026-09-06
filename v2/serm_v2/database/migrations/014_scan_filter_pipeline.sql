PRAGMA foreign_keys = ON;

-- O scan bruto é uma auditoria imutável do catálogo selecionado.
-- Filtros nunca alteram scan_runs/scan_items.

ALTER TABLE scan_runs ADD COLUMN catalog_label TEXT;
ALTER TABLE scan_runs ADD COLUMN scan_type TEXT NOT NULL DEFAULT 'full';
ALTER TABLE scan_runs ADD COLUMN scan_file_path TEXT;

CREATE INDEX IF NOT EXISTS ix_scan_runs_catalog ON scan_runs(source, system, catalog_label, scan_type, started_at DESC);

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
