"""Importador das software lists XML distribuídas no diretório MAME/hash."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from .sqlite_utils import require_lastrowid


class MameSoftwareListError(RuntimeError):
    """Erro durante a ingestão das software lists do MAME."""


class MameSoftwareListService:
    """Persiste os XML de ``hash`` sem depender de ferramentas externas."""

    BATCH_SIZE = 500

    def __init__(self, database: Path, hash_path: Path) -> None:
        self.database = Path(database)
        self.hash_path = Path(hash_path)

    @staticmethod
    def _text(element: ET.Element | None, tag: str) -> str | None:
        value = element.findtext(tag) if element is not None else None
        value = value.strip() if isinstance(value, str) else value
        return value or None

    @staticmethod
    def _int(value: str | None) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

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
        if not self.hash_path.is_dir():
            raise MameSoftwareListError(f"Diretório hash do MAME não encontrado: {self.hash_path}")

        files = sorted(self.hash_path.glob("*.xml"), key=lambda p: p.name.casefold())
        result: dict[str, int | str] = {"files": len(files), "imported": 0, "skipped": 0, "software": 0, "roms": 0, "disks": 0, "failed": 0, "status": "completed"}

        with sqlite3.connect(self.database, timeout=120.0) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=NORMAL")
            for index, path in enumerate(files, 1):
                try:
                    file_hash, byte_length = self._hash(path)
                    existing = db.execute(
                        "SELECT id FROM mame_softwarelist_source WHERE file_name=? AND source_hash=? LIMIT 1",
                        (path.name, file_hash),
                    ).fetchone()
                    if existing:
                        result["skipped"] = int(result["skipped"]) + 1
                        continue

                    root = ET.parse(path).getroot()
                    if root.tag != "softwarelist":
                        raise MameSoftwareListError(f"Raiz inesperada em {path.name}: {root.tag}")
                    list_name = (root.attrib.get("name") or path.stem).strip()
                    description = root.attrib.get("description")
                    software_nodes = root.findall("software")

                    old_sources = db.execute(
                        "SELECT id FROM mame_softwarelist_source WHERE file_name=?",
                        (path.name,),
                    ).fetchall()
                    for row in old_sources:
                        db.execute("DELETE FROM mame_softwarelist_source WHERE id=?", (int(row[0]),))

                    cur = db.execute(
                        """INSERT INTO mame_softwarelist_source
                        (list_name,description,file_name,file_path,source_hash,byte_length,software_count,imported_at,status)
                        VALUES(?,?,?,?,?,?,?,?,?)""",
                        (list_name, description, path.name, str(path), file_hash, byte_length, len(software_nodes), datetime.now(UTC).isoformat(), "captured"),
                    )
                    source_id = require_lastrowid(cur.lastrowid)
                    software_count = rom_count = disk_count = 0

                    for software in software_nodes:
                        attrs = software.attrib
                        infos: list[tuple[str, str | None]] = []
                        for info in software.findall("info"):
                            infos.append((str(info.attrib.get("name") or ""), info.attrib.get("value")))
                        info_json = json.dumps(infos, ensure_ascii=False, separators=(",", ":")) if infos else None
                        cur = db.execute(
                            """INSERT INTO mame_software
                            (source_id,name,cloneof,romof,supported,description,year,publisher,info_json)
                            VALUES(?,?,?,?,?,?,?,?,?)""",
                            (source_id, attrs.get("name", ""), attrs.get("cloneof"), attrs.get("romof"), attrs.get("supported"), self._text(software, "description"), self._text(software, "year"), self._text(software, "publisher"), info_json),
                        )
                        software_id = require_lastrowid(cur.lastrowid)
                        software_count += 1
                        for name, value in infos:
                            if name:
                                db.execute("INSERT INTO mame_software_info(software_id,name,value) VALUES(?,?,?)", (software_id, name, value))

                        for part in software.findall("part"):
                            attrs_part = part.attrib
                            feature_values = [
                                json.dumps(dict(feature.attrib), ensure_ascii=False, separators=(",", ":"))
                                for feature in part.findall("feature")
                            ]
                            cur = db.execute(
                                "INSERT INTO mame_software_part(software_id,name,interface,part_id,features) VALUES(?,?,?,?,?)",
                                (software_id, attrs_part.get("name", ""), attrs_part.get("interface"), attrs_part.get("id"), json.dumps(feature_values, ensure_ascii=False, separators=(",", ":")) if feature_values else None),
                            )
                            part_id = require_lastrowid(cur.lastrowid)
                            for area in part.findall("dataarea"):
                                for rom in area.findall("rom"):
                                    a = rom.attrib
                                    db.execute(
                                        """INSERT INTO mame_software_rom
                                        (part_id,name,size,crc,sha1,md5,offset,status,dispose,loadflag,optional,merge)
                                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                                        (part_id, a.get("name", ""), self._int(a.get("size")), a.get("crc"), a.get("sha1"), a.get("md5"), a.get("offset"), a.get("status"), a.get("dispose"), a.get("loadflag"), a.get("optional"), a.get("merge")),
                                    )
                                    rom_count += 1
                            for diskarea in part.findall("diskarea"):
                                for disk in diskarea.findall("disk"):
                                    a = disk.attrib
                                    db.execute(
                                        """INSERT INTO mame_software_disk
                                        (part_id,name,md5,sha1,merge,region,index_value,writable,status,optional)
                                        VALUES(?,?,?,?,?,?,?,?,?,?)""",
                                        (part_id, a.get("name", ""), a.get("md5"), a.get("sha1"), a.get("merge"), a.get("region"), a.get("index"), a.get("writable"), a.get("status"), a.get("optional")),
                                    )
                                    disk_count += 1

                    db.execute("UPDATE mame_softwarelist_source SET software_count=?,status='completed' WHERE id=?", (software_count, source_id))
                    db.commit()
                    result["imported"] = int(result["imported"]) + 1
                    result["software"] = int(result["software"]) + software_count
                    result["roms"] = int(result["roms"]) + rom_count
                    result["disks"] = int(result["disks"]) + disk_count
                    log(f"MAME | SOFTWARELIST | {path.name} | software={software_count:,} | roms={rom_count:,} | disks={disk_count:,}")
                except (OSError, ET.ParseError, sqlite3.Error, MameSoftwareListError) as exc:
                    db.rollback()
                    result["failed"] = int(result["failed"]) + 1
                    log(f"MAME | SOFTWARELIST | ERROR | {path.name} | {exc}")
            return result


__all__ = ["MameSoftwareListError", "MameSoftwareListService"]
