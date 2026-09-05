"""Ingestão do resolution.ini do MAME como fonte auxiliar do catálogo."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class MameResolutionError(RuntimeError):
    """Erro controlado da ingestão de resolution.ini."""


class MameResolutionService:
    """Lê resolution.ini em streaming e relaciona resoluções às máquinas MAME."""

    SOURCE_TYPE = "resolution_ini"
    SECTION_RE = re.compile(r"^\[\s*(\d+)\s*x\s*(\d+)\s*\]$")

    def __init__(self, database_path: Path, mame_root: Path) -> None:
        self.database_path = Path(database_path)
        self.mame_root = Path(mame_root)

    def locate_resolution_ini(self) -> Path:
        """Localiza resolution.ini em folders e depois na raiz do MAME."""
        for candidate in (
            self.mame_root / "folders" / "resolution.ini",
            self.mame_root / "resolution.ini",
        ):
            if candidate.is_file():
                return candidate
        raise MameResolutionError(
            "resolution.ini não encontrado em folders/ nem na raiz do MAME."
        )

    @staticmethod
    def _hash_file(path: Path) -> tuple[str, int]:
        """Calcula SHA-256 e tamanho sem carregar o arquivo inteiro."""
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                size += len(block)
                digest.update(block)
        return digest.hexdigest(), size

    @classmethod
    def _entries(cls, path: Path):
        """Produz resolução e máquina por streaming."""
        width = height = raw = None
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith((";", "#")):
                    continue
                match = cls.SECTION_RE.match(line)
                if match:
                    width = int(match.group(1))
                    height = int(match.group(2))
                    raw = line[1:-1].strip()
                    continue
                if raw is not None:
                    yield raw, width, height, line

    def ingest(self, logger=None) -> dict[str, int | str]:
        """Importa somente resolution.ini; VSYNC é responsabilidade da fila de INIs."""
        path = self.locate_resolution_ini()
        source_hash, byte_length = self._hash_file(path)
        now = datetime.now(UTC).isoformat()
        log = logger or (lambda message: None)
        log(f"MAME | RESOLUTION | START | arquivo={path}")

        connection = sqlite3.connect(self.database_path, timeout=60.0)
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            previous = connection.execute(
                """SELECT id, status
                   FROM mame_source_document
                   WHERE source_type=? AND source_hash=?
                   ORDER BY id DESC LIMIT 1""",
                (self.SOURCE_TYPE, source_hash),
            ).fetchone()

            if previous and previous[1] == "completed":
                source_id = int(previous[0])
                stats = connection.execute(
                    """SELECT COUNT(*),
                              SUM(resolved_status='resolved'),
                              SUM(resolved_status='unresolved')
                       FROM mame_resolution
                       WHERE source_document_id=?""",
                    (source_id,),
                ).fetchone()
                entries = int(stats[0] or 0)
                resolved = int(stats[1] or 0)
                unresolved = int(stats[2] or 0)
                log(
                    f"MAME | RESOLUTION | REUSE | source_id={source_id} "
                    f"| mesmo SHA-256 | entradas={entries:,}"
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
                   (source_type, source_name, source_path, source_hash,
                    byte_length, imported_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'captured')""",
                (
                    self.SOURCE_TYPE,
                    path.name,
                    str(path),
                    source_hash,
                    byte_length,
                    now,
                ),
            )
            source_id = int(cursor.lastrowid)
            machines = {
                row[1]: row[0]
                for row in connection.execute("SELECT id, name FROM mame_machine")
            }

            entries = resolved = unresolved = 0
            for resolution_raw, width, height, machine_name in self._entries(path):
                machine_id = machines.get(machine_name)
                status = "resolved" if machine_id is not None else "unresolved"
                connection.execute(
                    """INSERT INTO mame_resolution
                       (source_document_id, machine_id, machine_name,
                        resolution_raw, width, height, resolved_status, imported_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        source_id,
                        machine_id,
                        machine_name,
                        resolution_raw,
                        width,
                        height,
                        status,
                        now,
                    ),
                )
                entries += 1
                if machine_id is None:
                    unresolved += 1
                else:
                    resolved += 1

                if entries % 5000 == 0:
                    log(
                        f"MAME | RESOLUTION | PROGRESS | entradas={entries:,} "
                        f"| resolvidas={resolved:,} | não_resolvidas={unresolved:,}"
                    )

            connection.execute(
                "UPDATE mame_source_document SET status='completed' WHERE id=?",
                (source_id,),
            )
            connection.commit()
            log(
                f"MAME | RESOLUTION | DONE | entradas={entries:,} "
                f"| resolvidas={resolved:,} | não_resolvidas={unresolved:,} "
                f"| source_id={source_id}"
            )
            return {
                "source_id": source_id,
                "entries": entries,
                "resolved": resolved,
                "unresolved": unresolved,
                "status": "completed",
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


__all__ = ["MameResolutionError", "MameResolutionService"]
