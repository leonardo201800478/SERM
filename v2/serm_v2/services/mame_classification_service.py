"""Importação versionada do CATLIST para enriquecimento do catálogo MAME."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class MameClassificationError(RuntimeError):
    """Erro controlado durante a ingestão do CATLIST."""


class MameClassificationService:
    """Localiza, valida e importa CATLIST sem alterar dados do ListXML.

    ``folders/catlist.ini`` tem prioridade sobre ``cat32en/catlist.ini``.
    Seções de configuração do arquivo não são classificações de máquinas.
    """

    SOURCE_TYPE = "catlist"
    NON_CLASSIFICATION_SECTIONS = {"FOLDER_SETTINGS"}

    def __init__(self, database_path: Path, mame_root: Path) -> None:
        self.database_path = Path(database_path)
        self.mame_root = Path(mame_root)

    def locate_catlist(self) -> Path:
        """Retorna o primeiro CATLIST existente na ordem de precedência."""
        for candidate in (
            self.mame_root / "folders" / "catlist.ini",
            self.mame_root / "cat32en" / "catlist.ini",
        ):
            if candidate.is_file():
                return candidate
        raise MameClassificationError("CATLIST não encontrado em folders/ nem cat32en/.")

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

    @classmethod
    def _parse_section(cls, section: str) -> tuple[str | None, str | None, str | None]:
        """Extrai categoria, subcategoria e flags de uma seção CATLIST."""
        raw = section.strip()
        if raw.upper() in cls.NON_CLASSIFICATION_SECTIONS or ":" not in raw:
            return None, None, None
        _, value = raw.split(":", 1)
        flags = None
        flag_match = re.search(r"\s*\*([^*]*)\*\s*$", value)
        if flag_match:
            flags = flag_match.group(1).strip() or None
            value = value[: flag_match.start()].strip()
        parts = [part.strip() for part in value.split("/", 1)]
        return parts[0] or None, (parts[1] if len(parts) == 2 else None), flags

    @classmethod
    def _entries(cls, path: Path):
        """Produz somente classificações, ignorando FOLDER_SETTINGS e outras seções sem ':'."""
        current = ""
        is_classification = False
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith(";") or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    current = line[1:-1].strip()
                    is_classification = (
                        current.upper() not in cls.NON_CLASSIFICATION_SECTIONS
                        and ":" in current
                    )
                    continue
                if is_classification:
                    yield current, line

    def _remove_previous_source(self, connection: sqlite3.Connection, source_id: int) -> None:
        """Remove uma importação anterior da mesma fonte para permitir reprocessamento."""
        connection.execute("DELETE FROM mame_classification WHERE source_document_id=?", (source_id,))
        connection.execute("DELETE FROM mame_source_document WHERE id=?", (source_id,))

    def ingest(self, logger=None) -> dict[str, int | str]:
        """Importa CATLIST atomicamente e permite reprocessamento da mesma versão."""
        path = self.locate_catlist()
        source_hash, byte_length = self._hash_file(path)
        now = datetime.now(timezone.utc).isoformat()
        log = logger or (lambda message: None)
        log(f"MAME | CATLIST | START | arquivo={path}")

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
                self._remove_previous_source(connection, old_id)
                log(f"MAME | CATLIST | REPROCESS | source_id_anterior={old_id} | mesmo SHA-256")

            cursor = connection.execute(
                """INSERT INTO mame_source_document
                   (source_type, source_name, source_path, source_hash, byte_length, imported_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'captured')""",
                (self.SOURCE_TYPE, path.name, str(path), source_hash, byte_length, now),
            )
            source_id = int(cursor.lastrowid)

            machine_rows = {
                row[1]: row[0]
                for row in connection.execute("SELECT id, name FROM mame_machine")
            }
            entries = resolved = unresolved = 0
            for section, machine_name in self._entries(path):
                category, subcategory, flags = self._parse_section(section)
                machine_id = machine_rows.get(machine_name)
                resolved_status = "resolved" if machine_id is not None else "unresolved"
                connection.execute(
                    """INSERT INTO mame_classification
                       (machine_id, source_document_id, machine_name, section_raw,
                        category, subcategory, flags_raw, resolved_status, imported_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (machine_id, source_id, machine_name, section, category,
                     subcategory, flags, resolved_status, now),
                )
                entries += 1
                if machine_id is None:
                    unresolved += 1
                else:
                    resolved += 1
                if entries % 5000 == 0:
                    log(
                        f"MAME | CATLIST | PROGRESS | entradas={entries:,} | "
                        f"resolvidas={resolved:,} | não_resolvidas={unresolved:,}"
                    )

            connection.execute(
                "UPDATE mame_source_document SET status='completed' WHERE id=?", (source_id,)
            )
            connection.commit()
            log(
                f"MAME | CATLIST | DONE | entradas={entries:,} | "
                f"resolvidas={resolved:,} | não_resolvidas={unresolved:,} | source_id={source_id}"
            )
            return {"source_id": source_id, "entries": entries, "resolved": resolved,
                    "unresolved": unresolved, "status": "completed"}
        except Exception:
            connection.rollback()
            connection.close()
            raise
        finally:
            try:
                connection.close()
            except Exception:
                pass


__all__ = ["MameClassificationError", "MameClassificationService"]
