"""Persistência dos metadados e resultados dos scans V2."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from .rom_scan_service import ScanResult


class ScanRepository:
    """Persiste histórico de scans sem acoplar o serviço ao Qt."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scan_runs (
                    scan_id TEXT PRIMARY KEY,
                    profile_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    system TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    finished_at REAL,
                    files_examined INTEGER NOT NULL DEFAULT 0,
                    archives_examined INTEGER NOT NULL DEFAULT 0,
                    items_examined INTEGER NOT NULL DEFAULT 0,
                    errors INTEGER NOT NULL DEFAULT 0,
                    status_counts_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )

    def save(self, result: ScanResult, *, status: str = "completed") -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO scan_runs (
                    scan_id, profile_id, source, system, status, started_at, finished_at,
                    files_examined, archives_examined, items_examined, errors, status_counts_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.scan_id,
                    result.profile_id,
                    result.source,
                    result.system,
                    status,
                    result.started_at,
                    result.finished_at or None,
                    result.files_examined,
                    result.archives_examined,
                    result.items_examined,
                    result.errors,
                    json.dumps(dict(result.status_counts), ensure_ascii=False),
                ),
            )

    def latest_for_profile(self, profile_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM scan_runs WHERE profile_id = ? ORDER BY started_at DESC LIMIT 1",
                (profile_id,),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["status_counts"] = json.loads(data.pop("status_counts_json") or "{}")
        return data


__all__ = ["ScanRepository"]
