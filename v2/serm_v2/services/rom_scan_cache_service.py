"""Cache físico seguro para acelerar scans MAME sem pular validação.

O cache é um banco SQLite local. A chave inclui o catálogo e a assinatura do
ZIP (caminho, tamanho e mtime_ns), portanto um arquivo alterado nunca reutiliza
um resultado antigo.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..runtime.paths import scans_root
from .rom_scan_service import ScanEvidence, _MachineResult


class RomScanCacheService:
    """Cache persistente por machine/ZIP com SQLite."""

    FORMAT = "SERM-ROM-CACHE-V2"

    @staticmethod
    def _database() -> Path:
        root = scans_root() / "cache"
        root.mkdir(parents=True, exist_ok=True)
        return root / "mame_hash_cache.sqlite3"

    @classmethod
    def _connect(cls) -> sqlite3.Connection:
        connection = sqlite3.connect(cls._database(), timeout=30.0)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS rom_cache (
                catalog_hash TEXT NOT NULL,
                machine TEXT NOT NULL,
                path TEXT NOT NULL,
                size INTEGER NOT NULL,
                mtime_ns INTEGER NOT NULL,
                payload TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (catalog_hash, machine, path)
            )"""
        )
        return connection

    @staticmethod
    def _file_signature(path: Path) -> dict[str, Any] | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        if not path.is_file():
            return None
        return {
            "path": str(path.resolve()),
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
        }

    @classmethod
    def load(cls, machine: str, catalog_hash: str, zip_path: Path) -> _MachineResult | None:
        signature = cls._file_signature(zip_path)
        if signature is None:
            return None
        try:
            with cls._connect() as connection:
                row = connection.execute(
                    "SELECT path,size,mtime_ns,payload FROM rom_cache "
                    "WHERE catalog_hash=? AND machine=? AND path=?",
                    (catalog_hash, machine, signature["path"]),
                ).fetchone()
        except sqlite3.Error:
            return None
        if row is None:
            return None
        if int(row[1]) != signature["size"] or int(row[2]) != signature["mtime_ns"]:
            return None
        try:
            payload = json.loads(str(row[3]))
            if payload.get("format") != cls.FORMAT:
                return None
            records = [ScanEvidence(**item) for item in payload.get("records", [])]
            return _MachineResult(
                machine=machine,
                records=records,
                files_examined=int(payload.get("files_examined", 1)),
                archives_examined=int(payload.get("archives_examined", 1)),
                items_examined=int(payload.get("items_examined", 0)),
                bytes_read=0,
                errors=0,
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    @classmethod
    def save(cls, machine: str, catalog_hash: str, zip_path: Path, result: _MachineResult) -> None:
        """Persiste apenas resultados sem erro; falhas nunca entram no cache."""
        if result.errors or not zip_path.is_file():
            return
        signature = cls._file_signature(zip_path)
        if signature is None:
            return
        payload = {
            "format": cls.FORMAT,
            "machine": machine,
            "catalog_hash": catalog_hash,
            "files_examined": result.files_examined,
            "archives_examined": result.archives_examined,
            "items_examined": result.items_examined,
            "records": [asdict(record) for record in result.records],
        }
        try:
            with cls._connect() as connection:
                connection.execute(
                    "INSERT OR REPLACE INTO rom_cache "
                    "(catalog_hash,machine,path,size,mtime_ns,payload,updated_at) "
                    "VALUES (?,?,?,?,?,?,strftime('%s','now'))",
                    (
                        catalog_hash,
                        machine,
                        signature["path"],
                        signature["size"],
                        signature["mtime_ns"],
                        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    ),
                )
                connection.commit()
        except sqlite3.Error:
            # O cache é apenas uma otimização; falha de cache nunca interrompe scan.
            return


__all__ = ["RomScanCacheService"]
