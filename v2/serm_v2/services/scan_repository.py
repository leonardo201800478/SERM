"""Persistência dos metadados e resultados dos scans V2."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .rom_scan_service import ScanResult


class ScanRepository:
    """Persiste histórico e evidências dos scans sem acoplar o serviço ao Qt."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS scan_runs (
                scan_id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, profile_schema_version INTEGER NOT NULL DEFAULT 1,
                source TEXT NOT NULL, system TEXT NOT NULL, dat_path TEXT, catalog_hash TEXT,
                status TEXT NOT NULL, started_at REAL NOT NULL, finished_at REAL,
                files_examined INTEGER NOT NULL DEFAULT 0, archives_examined INTEGER NOT NULL DEFAULT 0,
                items_examined INTEGER NOT NULL DEFAULT 0, errors INTEGER NOT NULL DEFAULT 0,
                status_counts_json TEXT NOT NULL DEFAULT '{}')""")
            columns = {row[1] for row in connection.execute("PRAGMA table_info(scan_runs)")}
            additions = {
                "profile_schema_version": "INTEGER NOT NULL DEFAULT 1", "dat_path": "TEXT", "catalog_hash": "TEXT",
            }
            for name, definition in additions.items():
                if name not in columns:
                    connection.execute(f"ALTER TABLE scan_runs ADD COLUMN {name} {definition}")
            connection.execute("""CREATE TABLE IF NOT EXISTS scan_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT, scan_id TEXT NOT NULL REFERENCES scan_runs(scan_id) ON DELETE CASCADE,
                machine_name TEXT, rom_name TEXT, item_type TEXT NOT NULL DEFAULT 'ROM', status TEXT NOT NULL,
                expected_size INTEGER, actual_size INTEGER, expected_crc TEXT, actual_crc TEXT,
                expected_sha1 TEXT, actual_sha1 TEXT, expected_md5 TEXT, actual_md5 TEXT,
                path TEXT, archive_path TEXT, archive_member TEXT, merge_name TEXT, optional INTEGER NOT NULL DEFAULT 0,
                message TEXT, error TEXT)""")
            connection.execute("CREATE INDEX IF NOT EXISTS ix_scan_items_scan_status ON scan_items(scan_id,status)")

    def save(self, result: ScanResult, *, status: str = "completed", dat_path: str | None = None,
             profile_schema_version: int = 1) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO scan_runs (
                    scan_id, profile_id, profile_schema_version, source, system, dat_path, catalog_hash,
                    status, started_at, finished_at, files_examined, archives_examined, items_examined, errors, status_counts_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (result.scan_id, result.profile_id, profile_schema_version, result.source, result.system, dat_path,
                 result.catalog_hash, status, result.started_at, result.finished_at or None, result.files_examined,
                 result.archives_examined, result.items_examined, result.errors,
                 json.dumps(dict(result.status_counts), ensure_ascii=False)),
            )
            connection.execute("DELETE FROM scan_items WHERE scan_id=?", (result.scan_id,))
            connection.executemany(
                """INSERT INTO scan_items (
                    scan_id,machine_name,rom_name,item_type,status,expected_size,actual_size,expected_crc,actual_crc,
                    expected_sha1,actual_sha1,expected_md5,actual_md5,path,archive_path,archive_member,merge_name,optional,message,error
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [(result.scan_id, e.machine_name, e.rom_name, "ROM", e.status, e.expected_size, e.actual_size,
                  e.expected_crc, e.actual_crc, e.expected_sha1, e.actual_sha1, e.expected_md5, e.actual_md5,
                  e.path, e.archive_path, e.archive_member, e.merge_name, int(e.optional), e.message, e.error)
                 for e in result.evidence],
            )

    def latest_for_profile(self, profile_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM scan_runs WHERE profile_id=? ORDER BY started_at DESC LIMIT 1", (profile_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["status_counts"] = json.loads(data.pop("status_counts_json") or "{}")
        return data

    def evidence(self, scan_id: str, *, status: str | None = None) -> list[dict]:
        with self._connect() as connection:
            query = "SELECT * FROM scan_items WHERE scan_id=?"
            params: list[object] = [scan_id]
            if status:
                query += " AND status=?"; params.append(status)
            query += " ORDER BY machine_name, rom_name"
            return [dict(row) for row in connection.execute(query, params)]


__all__ = ["ScanRepository"]
