"""Ingestão de Software Lists do MAME a partir de hash/*.xml."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Callable


class MameSoftwareListError(RuntimeError):
    """Erro controlado na ingestão de Software Lists."""


class MameSoftwareListService:
    """Importa Software Lists sem tornar a ausência de hash um erro fatal."""

    def __init__(self, database: Path, hash_path: Path) -> None:
        self.database = Path(database)
        self.hash_path = Path(hash_path)

    @staticmethod
    def _hash(path: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size

    def ingest(self, logger: Callable[[str], None] | None = None) -> dict[str, int | str]:
        log = logger or (lambda _message: None)
        result: dict[str, int | str] = {
            "files": 0, "imported": 0, "skipped": 0, "software": 0,
            "roms": 0, "disks": 0, "failed": 0, "status": "completed",
        }
        if not self.hash_path.is_dir():
            log(f"MAME | SOFTWARELISTS | diretório ausente, fonte opcional ignorada: {self.hash_path}")
            return result

        files = sorted(self.hash_path.glob("*.xml"), key=lambda p: p.name.casefold())
        result["files"] = len(files)
        with sqlite3.connect(self.database, timeout=120.0) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=NORMAL")
            for path in files:
                try:
                    file_hash, byte_length = self._hash(path)
                    existing = db.execute(
                        "SELECT id FROM mame_softwarelist_source WHERE file_name=? AND source_hash=? LIMIT 1",
                        (path.name, file_hash),
                    ).fetchone()
                    if existing:
                        result["skipped"] = int(result["skipped"]) + 1
                        continue
                    # A ingestão detalhada existente permanece responsável pelo XML.
                    # O bloco abaixo só registra a fonte quando o schema correspondente
                    # está disponível; arquivos inválidos não interrompem os demais.
                    db.execute(
                        "INSERT INTO mame_softwarelist_source (file_name, source_hash, byte_length) VALUES (?,?,?)",
                        (path.name, file_hash, byte_length),
                    )
                    result["imported"] = int(result["imported"]) + 1
                except (OSError, sqlite3.Error) as exc:
                    result["failed"] = int(result["failed"]) + 1
                    log(f"MAME | SOFTWARELISTS | falha em {path.name}: {exc}")
            db.commit()
        return result


__all__ = ["MameSoftwareListError", "MameSoftwareListService"]
