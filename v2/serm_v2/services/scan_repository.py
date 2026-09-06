"""Persistência dos metadados, evidências e snapshot bruto dos scans V2."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .rom_scan_service import ScanResult
from .scan_file_repository import ScanFileRepository


class ScanRepository:
    """Persiste scans sem reconstruir uma lista gigante de evidências."""

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
                catalog_label TEXT, scan_type TEXT NOT NULL DEFAULT 'full', scan_file_path TEXT,
                status TEXT NOT NULL, started_at REAL NOT NULL, finished_at REAL,
                files_examined INTEGER NOT NULL DEFAULT 0, archives_examined INTEGER NOT NULL DEFAULT 0,
                items_examined INTEGER NOT NULL DEFAULT 0, errors INTEGER NOT NULL DEFAULT 0,
                status_counts_json TEXT NOT NULL DEFAULT '{}')""")
            columns = {row[1] for row in connection.execute("PRAGMA table_info(scan_runs)")}
            additions = {
                "profile_schema_version": "INTEGER NOT NULL DEFAULT 1",
                "dat_path": "TEXT",
                "catalog_hash": "TEXT",
                "catalog_label": "TEXT",
                "scan_type": "TEXT NOT NULL DEFAULT 'full'",
                "scan_file_path": "TEXT",
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
            connection.execute("""CREATE TABLE IF NOT EXISTS filter_runs (
                filter_run_id TEXT PRIMARY KEY, scan_id TEXT NOT NULL REFERENCES scan_runs(scan_id) ON DELETE CASCADE,
                profile_id TEXT NOT NULL, created_at REAL NOT NULL, filtered_file_path TEXT NOT NULL,
                input_count INTEGER NOT NULL DEFAULT 0, output_count INTEGER NOT NULL DEFAULT 0,
                status_counts_json TEXT NOT NULL DEFAULT '{}', filters_json TEXT NOT NULL DEFAULT '{}')""")
            connection.execute("CREATE INDEX IF NOT EXISTS ix_filter_runs_scan ON filter_runs(scan_id,created_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS ix_filter_runs_profile ON filter_runs(profile_id,created_at DESC)")

    @staticmethod
    def _iter_stream_evidence(stream_path: Path):
        with stream_path.open("r", encoding="utf-8") as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("record_type") == "evidence":
                    yield record

    def save(self, result: ScanResult, *, status: str = "completed", dat_path: str | None = None, profile_schema_version: int = 1) -> None:
        scan_file = ScanFileRepository.save(result)
        with self._connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO scan_runs (
                scan_id, profile_id, profile_schema_version, source, system, dat_path, catalog_hash,
                catalog_label, scan_type, scan_file_path, status, started_at, finished_at,
                files_examined, archives_examined, items_examined, errors, status_counts_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (result.scan_id, result.profile_id, profile_schema_version, result.source, result.system,
                 dat_path, result.catalog_hash, result.catalog_label, result.scan_type, str(scan_file), status,
                 result.started_at, result.finished_at or None, result.files_examined, result.archives_examined,
                 result.items_examined, result.errors, json.dumps(dict(result.status_counts), ensure_ascii=False)),
            )
            connection.execute("DELETE FROM scan_items WHERE scan_id=?", (result.scan_id,))
            stream_path = Path(result.evidence_stream_path) if result.evidence_stream_path else None
            if stream_path and stream_path.is_file():
                batch: list[tuple] = []
                for e in self._iter_stream_evidence(stream_path):
                    batch.append((result.scan_id, e.get("machine_name"), e.get("rom_name"), "ROM", e.get("status", "ERROR"),
                                  e.get("expected_size"), e.get("actual_size"), e.get("expected_crc", ""), e.get("actual_crc", ""),
                                  e.get("expected_sha1", ""), e.get("actual_sha1", ""), e.get("expected_md5", ""), e.get("actual_md5", ""),
                                  e.get("path"), e.get("archive_path"), e.get("archive_member"), e.get("merge_name"),
                                  int(bool(e.get("optional"))), e.get("message", ""), e.get("error")))
                    if len(batch) >= 1000:
                        connection.executemany("""INSERT INTO scan_items (
                            scan_id,machine_name,rom_name,item_type,status,expected_size,actual_size,expected_crc,actual_crc,
                            expected_sha1,actual_sha1,expected_md5,actual_md5,path,archive_path,archive_member,merge_name,optional,message,error
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", batch)
                        batch.clear()
                if batch:
                    connection.executemany("""INSERT INTO scan_items (
                        scan_id,machine_name,rom_name,item_type,status,expected_size,actual_size,expected_crc,actual_crc,
                        expected_sha1,actual_sha1,expected_md5,actual_md5,path,archive_path,archive_member,merge_name,optional,message,error
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", batch)

    def save_filter_result(self, result: dict) -> None:
        with self._connect() as connection:
            connection.execute("""INSERT OR REPLACE INTO filter_runs (
                filter_run_id, scan_id, profile_id, created_at, filtered_file_path,
                input_count, output_count, status_counts_json, filters_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
                result["filter_run_id"], result["scan_id"], result["profile_id"], result["created_at"],
                result["filtered_file_path"], result["input_count"], result["output_count"],
                json.dumps(result.get("filter_counts", {}), ensure_ascii=False),
                json.dumps(result.get("filters", {}), ensure_ascii=False),
            ))

    def latest_for_profile(self, profile_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM scan_runs WHERE profile_id=? ORDER BY started_at DESC LIMIT 1", (profile_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["status_counts"] = json.loads(data.pop("status_counts_json") or "{}")
        return data

    def list_for_source(self, source: str, *, status: str | None = "completed") -> list[dict]:
        query = "SELECT * FROM scan_runs WHERE lower(source)=lower(?)"
        params: list[object] = [source]
        if status is not None:
            query += " AND status=?"
            params.append(status)
        query += " ORDER BY started_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def delete(self, scan_id: str) -> bool:
        """Remove o registro, evidências e snapshot bruto de um scan."""
        record = self.get(scan_id)
        if record is None:
            return False
        paths: list[Path] = []
        raw_path = record.get("scan_file_path")
        if raw_path:
            paths.append(Path(str(raw_path)))
        fallback = ScanFileRepository.latest_path(scan_id)
        if fallback and fallback not in paths:
            paths.append(fallback)
        with self._connect() as connection:
            connection.execute("DELETE FROM scan_runs WHERE scan_id=?", (scan_id,))
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        return True

    def get(self, scan_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM scan_runs WHERE scan_id=?", (scan_id,)).fetchone()
        return dict(row) if row else None

    def evidence(self, scan_id: str, *, status: str | None = None) -> list[dict]:
        with self._connect() as connection:
            query = "SELECT * FROM scan_items WHERE scan_id=?"
            params: list[object] = [scan_id]
            if status:
                query += " AND status=?"
                params.append(status)
            query += " ORDER BY machine_name, rom_name"
            return [dict(row) for row in connection.execute(query, params)]

    def raw_file(self, scan_id: str) -> Path | None:
        record = self.get(scan_id)
        if not record or not record.get("scan_file_path"):
            return ScanFileRepository.latest_path(scan_id)
        path = Path(str(record["scan_file_path"]))
        return path if path.is_file() else ScanFileRepository.latest_path(scan_id)


__all__ = ["ScanRepository"]