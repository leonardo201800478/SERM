"""Ingestão do Vsync.ini do MAME como fonte auxiliar do catálogo."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .sqlite_utils import require_lastrowid


class MameVsyncError(RuntimeError):
    """Erro controlado durante a ingestão do Vsync.ini."""


class MameVsyncService:
    """Importa a lista de máquinas com sincronização vertical habilitada."""

    SOURCE_TYPE = "vsync_ini"

    def __init__(self, database_path: Path, mame_root: Path) -> None:
        self.database_path = Path(database_path)
        self.mame_root = Path(mame_root)

    def locate_vsync_ini(self) -> Path:
        """Localiza Vsync.ini em folders/ ou na raiz do MAME."""
        for candidate in (self.mame_root / "folders" / "Vsync.ini", self.mame_root / "Vsync.ini"):
            if candidate.is_file():
                return candidate
        for base in (self.mame_root / "folders", self.mame_root):
            if base.is_dir():
                for candidate in base.iterdir():
                    if candidate.is_file() and candidate.name.casefold() == "vsync.ini":
                        return candidate
        raise MameVsyncError("Vsync.ini não encontrado em folders/ nem na raiz do MAME.")

    @staticmethod
    def _hash_file(path: Path) -> tuple[str, int]:
        """Calcula SHA-256 e tamanho do arquivo em streaming."""
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                size += len(block)
                digest.update(block)
        return digest.hexdigest(), size

    @staticmethod
    def _entries(path: Path):
        """Produz nomes de máquinas, ignorando comentários, seções e linhas vazias."""
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith((";", "#")):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    continue
                yield line

    def ingest(self, logger=None) -> dict[str, int | str]:
        """Importa Vsync.ini de forma idempotente, descartando nomes duplicados."""
        path = self.locate_vsync_ini()
        source_hash, byte_length = self._hash_file(path)
        now = datetime.now(UTC).isoformat()
        log = logger or (lambda message: None)
        log(f"MAME | VSYNC | START | arquivo={path}")

        connection = sqlite3.connect(self.database_path, timeout=60.0)
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            previous = connection.execute(
                "SELECT id, status FROM mame_source_document WHERE source_type=? AND source_hash=? ORDER BY id DESC LIMIT 1",
                (self.SOURCE_TYPE, source_hash),
            ).fetchone()
            if previous and previous[1] == "completed":
                source_id = int(previous[0])
                row = connection.execute(
                    """SELECT COUNT(*), SUM(resolved_status='resolved'), SUM(resolved_status='unresolved')
                       FROM mame_vsync WHERE source_document_id=?""",
                    (source_id,),
                ).fetchone()
                entries, resolved, unresolved = int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)
                log(
                    f"MAME | VSYNC | REUSE | source_id={source_id} | mesmo SHA-256 | entradas={entries:,}"
                )
                return {
                    "source_id": source_id,
                    "entries": entries,
                    "resolved": resolved,
                    "unresolved": unresolved,
                    "status": "reused",
                }

            connection.execute("BEGIN")
            cursor = connection.execute(
                """INSERT INTO mame_source_document
                   (source_type, source_name, source_path, source_hash, byte_length, imported_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'captured')""",
                (self.SOURCE_TYPE, path.name, str(path), source_hash, byte_length, now),
            )
            source_id = require_lastrowid(cursor.lastrowid)
            machines = {
                row[1]: row[0] for row in connection.execute("SELECT id, name FROM mame_machine")
            }

            entries = resolved = unresolved = duplicates = 0
            seen: set[str] = set()

            for machine_name in self._entries(path):
                # O arquivo pode conter o mesmo driver/máquina mais de uma vez.
                # A tabela possui UNIQUE(source_document_id, machine_name), portanto
                # a duplicidade deve ser tratada antes do INSERT.
                if machine_name in seen:
                    duplicates += 1
                    continue
                seen.add(machine_name)

                machine_id = machines.get(machine_name)
                status = "resolved" if machine_id is not None else "unresolved"
                connection.execute(
                    """INSERT INTO mame_vsync
                       (source_document_id, machine_id, machine_name, vsync_enabled, value_raw, resolved_status, imported_at)
                       VALUES (?, ?, ?, 1, '1', ?, ?)""",
                    (source_id, machine_id, machine_name, status, now),
                )
                entries += 1
                if machine_id is None:
                    unresolved += 1
                else:
                    resolved += 1

                if entries % 5000 == 0:
                    log(
                        f"MAME | VSYNC | PROGRESS | entradas={entries:,} "
                        f"| resolvidas={resolved:,} | não_resolvidas={unresolved:,} "
                        f"| duplicadas={duplicates:,}"
                    )

            connection.execute(
                "UPDATE mame_source_document SET status='completed' WHERE id=?",
                (source_id,),
            )
            connection.commit()
            log(
                f"MAME | VSYNC | DONE | entradas={entries:,} | resolvidas={resolved:,} "
                f"| não_resolvidas={unresolved:,} | duplicadas={duplicates:,} | source_id={source_id}"
            )
            return {
                "source_id": source_id,
                "entries": entries,
                "resolved": resolved,
                "unresolved": unresolved,
                "duplicates": duplicates,
                "status": "completed",
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


__all__ = ["MameVsyncError", "MameVsyncService"]
