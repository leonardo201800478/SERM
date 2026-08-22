"""Persistência dos catálogos independentes dos emuladores."""
from __future__ import annotations

import hashlib
import logging
import sqlite3
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.database.database import Database

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CatalogPersistenceResult:
    """Resumo da persistência de um catálogo."""

    emulator: str
    version: str | None
    machine_count: int
    rom_count: int
    content_hash: str


class EmulatorCatalogRepository:
    """Repositório SQLite para catálogos multi-emulador."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Cria as tabelas do catálogo caso o banco ainda não as possua."""
        migration = Path(__file__).resolve().parents[2] / "database" / "migrations" / "emulator_catalog.sql"
        if not migration.is_file():
            raise FileNotFoundError(f"Migração de catálogo não encontrada: {migration}")
        self.database.executescript(migration.read_text(encoding="utf-8"))

    def replace_from_xml(self, *, emulator: str, version: str | None, source: str, xml_path: Path) -> CatalogPersistenceResult:
        """Substitui integralmente o catálogo de um emulador."""
        path = Path(xml_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Catálogo XML não encontrado: {path}")
        if path.stat().st_size == 0:
            raise ValueError(f"Catálogo XML vazio: {path}")

        content_hash = self._sha256(path)
        root = ET.parse(path).getroot()
        emulator_key = emulator.strip().casefold()
        if not emulator_key:
            raise ValueError("Emulador do catálogo não pode ser vazio")

        machine_elements = root.findall("machine") or root.findall("game")
        machines: list[tuple[dict[str, object], list[dict[str, object]]]] = []
        rom_count = 0

        for machine in machine_elements:
            name = (machine.get("name") or "").strip()
            if not name:
                continue
            machine_data = {
                "name": name,
                "description": self._child_text(machine, "description"),
                "year": self._child_text(machine, "year"),
                "manufacturer": self._child_text(machine, "manufacturer"),
                "sourcefile": machine.get("sourcefile"),
                "cloneof": machine.get("cloneof"),
                "romof": machine.get("romof"),
                "sampleof": machine.get("sampleof"),
                "platform": self._platform(machine),
                "runnable": self._int_bool(machine.get("runnable"), default=1),
                "emulation_status": self._child_attr(machine, "driver", "status"),
                "driver_status": self._child_attr(machine, "driver", "status"),
            }
            roms: list[dict[str, object]] = []
            for rom in machine.findall("rom"):
                rom_name = (rom.get("name") or "").strip()
                if not rom_name:
                    continue
                roms.append({
                    "name": rom_name,
                    "size": self._int_or_none(rom.get("size")),
                    "crc": self._normalize_crc(rom.get("crc")),
                    "sha1": self._normalize_sha1(rom.get("sha1")),
                    "merge": rom.get("merge"),
                    "region": rom.get("region"),
                    "offset": self._int_or_zero(rom.get("offset")),
                    "status": rom.get("status") or "good",
                    "optional": self._int_bool(rom.get("optional"), default=0),
                    "bios": rom.get("bios"),
                })
            rom_count += len(roms)
            machines.append((machine_data, roms))

        if not machines:
            raise ValueError(f"Nenhuma máquina/game encontrada no catálogo: {path}")

        conn = self.database.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            old = conn.execute("SELECT id FROM emulator_catalog WHERE emulator = ?", (emulator_key,)).fetchone()
            if old is not None:
                conn.execute("DELETE FROM emulator_catalog WHERE id = ?", (old["id"],))
            cursor = conn.execute(
                """INSERT INTO emulator_catalog
                    (emulator, version, source, source_path, generated_at, machine_count, content_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (emulator_key, version, source, str(path), datetime.now(timezone.utc).isoformat(), len(machines), content_hash),
            )
            catalog_id = cursor.lastrowid
            if catalog_id is None:
                raise RuntimeError("SQLite não retornou o ID do catálogo")
            for machine_data, roms in machines:
                machine_cursor = conn.execute(
                    """INSERT INTO emulator_catalog_machine
                        (catalog_id, name, description, year, manufacturer, sourcefile, cloneof, romof, sampleof,
                         platform, runnable, emulation_status, driver_status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (catalog_id, machine_data["name"], machine_data["description"], machine_data["year"], machine_data["manufacturer"],
                     machine_data["sourcefile"], machine_data["cloneof"], machine_data["romof"], machine_data["sampleof"],
                     machine_data["platform"], machine_data["runnable"], machine_data["emulation_status"], machine_data["driver_status"]),
                )
                machine_id = machine_cursor.lastrowid
                if machine_id is None:
                    raise RuntimeError("SQLite não retornou o ID da máquina")
                if roms:
                    conn.executemany(
                        """INSERT INTO emulator_catalog_rom
                            (machine_id, name, size, crc, sha1, merge, region, offset, status, optional, bios)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        [(machine_id, r["name"], r["size"], r["crc"], r["sha1"], r["merge"], r["region"], r["offset"], r["status"], r["optional"], r["bios"]) for r in roms],
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("Catálogo não publicado; versão anterior preservada | emulator=%s", emulator_key)
            raise

        logger.info("Catálogo persistido | emulator=%s | version=%s | machines=%d | roms=%d | hash=%s", emulator_key, version or "unknown", len(machines), rom_count, content_hash)
        return CatalogPersistenceResult(emulator_key, version, len(machines), rom_count, content_hash)

    def get_catalog(self, emulator: str) -> sqlite3.Row | None:
        """Retorna os metadados do catálogo atualmente publicado, incluindo ROMs."""
        return self.database.fetchone(
            """SELECT c.*, COALESCE((SELECT COUNT(*) FROM emulator_catalog_rom r
                       JOIN emulator_catalog_machine m ON m.id = r.machine_id
                       WHERE m.catalog_id = c.id), 0) AS rom_count
                FROM emulator_catalog c WHERE c.emulator = ?""",
            (emulator.strip().casefold(),),
        )

    def list_catalogs(self) -> list[sqlite3.Row]:
        """Retorna todos os catálogos publicados com contagens de jogos e ROMs."""
        return self.database.fetchall(
            """SELECT c.*,
                       COALESCE((SELECT COUNT(*) FROM emulator_catalog_machine m WHERE m.catalog_id = c.id), 0) AS game_count,
                       COALESCE((SELECT COUNT(*) FROM emulator_catalog_rom r
                                 JOIN emulator_catalog_machine m ON m.id = r.machine_id
                                 WHERE m.catalog_id = c.id), 0) AS rom_count
                FROM emulator_catalog c ORDER BY c.emulator"""
        )

    def machine_count(self, emulator: str) -> int:
        """Retorna a quantidade de máquinas do catálogo publicado."""
        row = self.database.fetchone("SELECT COUNT(*) AS total FROM emulator_catalog_machine m JOIN emulator_catalog c ON c.id = m.catalog_id WHERE c.emulator = ?", (emulator.strip().casefold(),))
        return int(row["total"]) if row else 0

    def list_machines(self, emulator: str) -> list[sqlite3.Row]:
        """Retorna máquinas do catálogo ordenadas por nome."""
        return self.database.fetchall("SELECT m.* FROM emulator_catalog_machine m JOIN emulator_catalog c ON c.id = m.catalog_id WHERE c.emulator = ? ORDER BY m.name", (emulator.strip().casefold(),))

    @staticmethod
    def _sha256(path: Path) -> str:
        """Calcula SHA-256 em streaming."""
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _child_text(element: ET.Element, tag: str) -> str | None:
        """Obtém texto de um filho XML."""
        value = element.findtext(tag)
        value = value.strip() if value else ""
        return value or None

    @staticmethod
    def _child_attr(element: ET.Element, tag: str, attr: str) -> str | None:
        """Obtém atributo de um filho XML."""
        child = element.find(tag)
        value = child.get(attr) if child is not None else None
        return value.strip() if value else None

    @staticmethod
    def _platform(element: ET.Element) -> str | None:
        """Obtém plataforma de feature platform quando disponível."""
        for feature in element.findall("feature"):
            if (feature.get("type") or "").casefold() == "platform":
                value = feature.get("status") or feature.get("overall")
                return value.strip() if value else None
        return None

    @staticmethod
    def _int_or_none(value: str | None) -> int | None:
        """Converte inteiro decimal/hexadecimal."""
        if value is None or not value.strip():
            return None
        try:
            return int(value, 0)
        except ValueError:
            try:
                return int(value)
            except ValueError:
                return None

    @staticmethod
    def _int_or_zero(value: str | None) -> int:
        """Converte inteiro e usa zero quando inválido."""
        return EmulatorCatalogRepository._int_or_none(value) or 0

    @staticmethod
    def _int_bool(value: str | None, *, default: int) -> int:
        """Converte atributos booleanos do LISTXML."""
        if value is None:
            return default
        return 1 if value.strip().casefold() in {"yes", "true", "1"} else 0

    @staticmethod
    def _normalize_crc(value: str | None) -> str | None:
        """Normaliza CRC para oito dígitos hexadecimais."""
        if not value:
            return None
        clean = value.strip().lower().removeprefix("0x")
        if not clean:
            return None
        try:
            return f"{int(clean, 16):08x}"
        except ValueError:
            return clean

    @staticmethod
    def _normalize_sha1(value: str | None) -> str | None:
        """Normaliza SHA-1."""
        if not value:
            return None
        return value.strip().lower() or None
