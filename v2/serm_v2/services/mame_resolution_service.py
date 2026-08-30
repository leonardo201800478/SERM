"""Ingestão do resolution.ini do MAME como fonte auxiliar do catálogo."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
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
        """Localiza resolution.ini na pasta folders, com fallback para a raiz MAME."""
        candidates = (
            self.mame_root / "folders" / "resolution.ini",
            self.mame_root / "resolution.ini",
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        raise MameResolutionError("resolution.ini não encontrado em folders/ nem na raiz do MAME.")

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
        """Produz (resolução_raw, largura, altura, machine_name) por linha."""
        width = height = raw = None
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith(";") or line.startswith("#"):
                    continue
                match = cls.SECTION_RE.match(line)
                if match:
                    width, height = int(match.group(1)), int(match.group(2))
                    raw = line[1:-1].strip()
                    continue
                if raw is not None:
                    yield raw, width, height, line

    def ingest(self, logger=None) -> dict[str, int | str]:
        """Importa resolution.ini atomicamente, permitindo reprocessamento por SHA."""
        path = self.locate_resolution_ini()
        source_hash, byte_length = self._hash_file(path)
        now = datetime.now(timezone.utc).isoformat()
        log = logger or (lambda message: None)
        log(f"MAME | RESOLUTION | START | arquivo={path}")

        connection = sqlite3.connect(self.database_path, timeout=60.0)
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            connection.execute("BEGIN")
            previous = connection.execute(
                "SELECT id FROM mame_source_document WHERE source_type=? AND source_hash=?",
                (self.SOURCE_TYPE, source_hash),
            ).fetchone()
            if previous:
                old_id = int(previous[0])
                connection.execute("DELETE FROM mame_resolution WHERE source_document_id=?", (old_id,))
                connection.execute("DELETE FROM mame_source_document WHERE id=?", (old_id,))
                log(f"MAME | RESOLUTION | REPROCESS | source_id_anterior={old_id} | mesmo SHA-256")

            cursor = connection.execute(
                """INSERT INTO mame_source_document
                   (source_type, source_name, source_path, source_hash, byte_length, imported_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'captured')""",
                (self.SOURCE_TYPE, path.name, str(path), source_hash, byte_length, now),
            )
            source_id = int(cursor.lastrowid)
            machines = {row[1]: row[0] for row in connection.execute("SELECT id, name FROM mame_machine")}

            entries = resolved = unresolved = malformed = 0
            for resolution_raw, width, height, machine_name in self._entries(path):
                machine_id = machines.get(machine_name)
                status = "resolved" if machine_id is not None else "unresolved"
                connection.execute(
                    """INSERT INTO mame_resolution
                       (source_document_id, machine_id, machine_name, resolution_raw,
                        width, height, resolved_status, imported_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (source_id, machine_id, machine_name, resolution_raw, width, height, status, now),
                )
                entries += 1
                if machine_id is None:
                    unresolved += 1
                else:
                    resolved += 1
                if entries % 5000 == 0:
                    log(f"MAME | RESOLUTION | PROGRESS | entradas={entries:,} | resolvidas={resolved:,} | não_resolvidas={unresolved:,}")

            connection.execute("UPDATE mame_source_document SET status='completed' WHERE id=?", (source_id,))
            connection.commit()
            log(f"MAME | RESOLUTION | DONE | entradas={entries:,} | resolvidas={resolved:,} | não_resolvidas={unresolved:,} | source_id={source_id}")
            return {"source_id": source_id, "entries": entries, "resolved": resolved, "unresolved": unresolved, "malformed": malformed, "status": "completed"}
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


__all__ = ["MameResolutionError", "MameResolutionService"]
