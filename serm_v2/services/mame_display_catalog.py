"""Ingestão lossless do MAME ListXML e resolução/display fallbacks.

O ListXML é a fonte primária para identidade e timing. A resolução.ini e a
Vsync.ini são fontes externas/fallback e nunca sobrescrevem silenciosamente
um valor presente no ListXML. O XML bruto também é preservado por nó/atributo,
permitindo suportar novos campos do MAME sem perda de informação.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..runtime.paths import data_root, database_path
from .sqlite_utils import require_lastrowid


class MameDisplayCatalogError(RuntimeError):
    """Erro durante extração, parsing ou persistência do catálogo MAME."""


@dataclass(frozen=True, slots=True)
class DisplayFact:
    """Fato de vídeo normalizado a partir de um display do ListXML."""

    tag: str | None
    display_type: str | None
    rotate: str | None
    width: int | None
    height: int | None
    refresh_hz: float | None
    refresh_raw: str | None
    pixclock: str | None
    htotal: str | None
    hbend: str | None
    hbstart: str | None
    vtotal: str | None
    vbend: str | None
    vbstart: str | None
    flipx: str | None


@dataclass(frozen=True, slots=True)
class DisplayImportResult:
    """Resumo de uma importação ListXML."""

    import_id: int
    machine_count: int
    display_count: int
    xml_path: Path
    source_hash: str
    mame_build: str | None


class MameDisplayCatalog:
    """Constrói o catálogo normalizado e lossless de um ListXML do MAME."""

    PARSER_VERSION = "1.0"
    RAW_ROOT = data_root() / "mame" / "listxml"

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or database_path()

    def import_executable(
        self,
        executable: str | Path,
        *,
        timeout: float = 180.0,
        force: bool = False,
    ) -> DisplayImportResult:
        """Executa ``mame -listxml`` e persiste o catálogo completo."""
        executable_path = Path(executable).expanduser().resolve()
        if not executable_path.is_file():
            raise MameDisplayCatalogError(f"MAME executable not found: {executable_path}")

        try:
            completed = subprocess.run(
                [str(executable_path), "-listxml"],
                cwd=executable_path.parent,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
                shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MameDisplayCatalogError(f"Falha ao executar MAME -listxml: {exc}") from exc
        if completed.returncode != 0:
            raise MameDisplayCatalogError(
                f"MAME -listxml retornou {completed.returncode}: {completed.stderr.strip()}"
            )
        return self.import_xml(
            completed.stdout,
            executable=executable_path,
            force=force,
        )

    def import_xml(
        self,
        xml_text: str,
        *,
        executable: str | Path,
        force: bool = False,
    ) -> DisplayImportResult:
        """Importa XML já extraído, preservando todos os elementos e atributos."""
        if not xml_text.strip():
            raise MameDisplayCatalogError("ListXML vazio.")
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise MameDisplayCatalogError("ListXML inválido.") from exc
        if root.tag != "mame":
            raise MameDisplayCatalogError(f"Raiz inesperada no ListXML: {root.tag}")

        source_hash = hashlib.sha256(xml_text.encode("utf-8")).hexdigest()
        now = datetime.now(UTC).isoformat()
        xml_path = self.RAW_ROOT / f"listxml-{source_hash[:16]}.xml"
        self.RAW_ROOT.mkdir(parents=True, exist_ok=True)
        xml_path.write_text(xml_text, encoding="utf-8", newline="\n")

        machine_elements = [element for element in root if element.tag == "machine"]
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            self._ensure_schema(connection)
            emulator_id = connection.execute(
                "SELECT id FROM emulator_definition WHERE slug='mame'"
            ).fetchone()
            if emulator_id is None:
                raise MameDisplayCatalogError("emulator_definition('mame') não existe.")
            emulator_id = int(emulator_id[0])

            if not force:
                existing = connection.execute(
                    "SELECT id, machine_count, xml_path, mame_build FROM mame_listxml_import WHERE source_hash=?",
                    (source_hash,),
                ).fetchone()
                if existing:
                    return DisplayImportResult(
                        import_id=int(existing[0]),
                        machine_count=int(existing[1]),
                        display_count=connection.execute(
                            "SELECT COUNT(*) FROM mame_display d JOIN mame_machine m ON m.id=d.machine_id WHERE m.import_id=?",
                            (existing[0],),
                        ).fetchone()[0],
                        xml_path=Path(existing[2]),
                        source_hash=source_hash,
                        mame_build=existing[3],
                    )

            import_row = connection.execute(
                """INSERT INTO mame_listxml_import
                (emulator_id, executable, mame_build, mame_config, debug, imported_at,
                 source_hash, xml_path, machine_count, parser_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    emulator_id,
                    str(Path(executable).resolve()),
                    root.attrib.get("build"),
                    root.attrib.get("mameconfig"),
                    root.attrib.get("debug"),
                    now,
                    source_hash,
                    str(xml_path),
                    len(machine_elements),
                    self.PARSER_VERSION,
                ),
            )
            import_id = require_lastrowid(import_row.lastrowid)

            # Root node is persisted as well, so no XML-level information is lost.
            self._insert_tree(
                connection,
                import_id=import_id,
                element=root,
                parent_node_id=None,
                machine_id=None,
                path="/mame",
            )

            display_count = 0
            for machine_element in machine_elements:
                machine = self._insert_machine(connection, import_id, machine_element)
                self._insert_tree(
                    connection,
                    import_id=import_id,
                    element=machine_element,
                    parent_node_id=None,
                    machine_id=machine,
                    path=f"/mame/machine[@name='{machine_element.attrib.get('name', '')}']",
                    skip_root_machine_link=True,
                )
                display_count += self._insert_normalized_children(
                    connection, machine, machine_element
                )
            connection.commit()

        return DisplayImportResult(
            import_id=import_id,
            machine_count=len(machine_elements),
            display_count=display_count,
            xml_path=xml_path,
            source_hash=source_hash,
            mame_build=root.attrib.get("build"),
        )

    def _insert_machine(
        self, connection: sqlite3.Connection, import_id: int, element: ET.Element
    ) -> int:
        """Insere a identidade principal da máquina."""
        attrs = element.attrib
        description = element.findtext("description")
        year = element.findtext("year")
        manufacturer = element.findtext("manufacturer")
        row = connection.execute(
            """INSERT INTO mame_machine
            (import_id, name, sourcefile, isdevice, runnable, cloneof, romof, sampleof,
             description, year, manufacturer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                import_id,
                attrs.get("name", ""),
                attrs.get("sourcefile"),
                attrs.get("isdevice"),
                attrs.get("runnable"),
                attrs.get("cloneof"),
                attrs.get("romof"),
                attrs.get("sampleof"),
                description,
                year,
                manufacturer,
            ),
        )
        return require_lastrowid(row.lastrowid)

    def _insert_tree(
        self,
        connection: sqlite3.Connection,
        *,
        import_id: int,
        element: ET.Element,
        parent_node_id: int | None,
        machine_id: int | None,
        path: str,
        skip_root_machine_link: bool = False,
    ) -> int:
        """Persiste recursivamente cada nó XML, seus atributos e texto."""
        attrs = json.dumps(dict(element.attrib), ensure_ascii=False, sort_keys=True)
        row = connection.execute(
            """INSERT OR IGNORE INTO mame_xml_node
            (import_id, parent_node_id, machine_id, element_name, ordinal, xml_path,
             text_value, attributes_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                import_id,
                parent_node_id,
                machine_id,
                element.tag,
                0,
                path,
                (element.text or "").strip() or None,
                attrs,
            ),
        )
        node_id = int(
            row.lastrowid
            or connection.execute(
                "SELECT id FROM mame_xml_node WHERE import_id=? AND xml_path=?",
                (import_id, path),
            ).fetchone()[0]
        )
        if element.tag == "machine" and machine_id is not None and not skip_root_machine_link:
            connection.execute(
                "UPDATE mame_machine SET xml_node_id=? WHERE id=?", (node_id, machine_id)
            )

        counters: dict[str, int] = {}
        for child in element:
            ordinal = counters.get(child.tag, 0)
            counters[child.tag] = ordinal + 1
            key = child.attrib.get("name") or child.attrib.get("tag") or str(ordinal)
            child_path = f"{path}/{child.tag}[{key}]"
            child_node = self._insert_tree(
                connection,
                import_id=import_id,
                element=child,
                parent_node_id=node_id,
                machine_id=machine_id,
                path=child_path,
            )
            connection.execute(
                "UPDATE mame_xml_node SET ordinal=? WHERE id=?",
                (ordinal, child_node),
            )
        return node_id

    def _insert_normalized_children(  # NOSONAR - tag-specific XML normalization requires these branches
        self,
        connection: sqlite3.Connection,
        machine_id: int,
        machine: ET.Element,
    ) -> int:  # NOSONAR - tag-specific XML normalization requires these branches
        """Extrai as entidades conhecidas do ListXML para consultas eficientes."""
        display_count = 0
        for child in machine:
            tag = child.tag
            if tag == "biosset":
                a = child.attrib
                connection.execute(
                    "INSERT INTO mame_biosset(machine_id,name,description,default_value) VALUES(?,?,?,?)",
                    (machine_id, a.get("name"), a.get("description"), a.get("default")),
                )
            elif tag == "rom":
                self._insert_attrs(
                    connection,
                    "mame_rom",
                    machine_id,
                    child.attrib,
                    {
                        "name": "name",
                        "bios": "bios",
                        "size": "size",
                        "crc": "crc",
                        "sha1": "sha1",
                        "md5": "md5",
                        "merge": "merge",
                        "region": "region",
                        "offset": "offset",
                        "status": "status",
                        "optional": "optional",
                        "dispose": "dispose",
                    },
                )
            elif tag == "disk":
                self._insert_attrs(
                    connection,
                    "mame_disk",
                    machine_id,
                    child.attrib,
                    {
                        "name": "name",
                        "md5": "md5",
                        "sha1": "sha1",
                        "merge": "merge",
                        "region": "region",
                        "index": "index_value",
                        "writable": "writable",
                        "status": "status",
                        "optional": "optional",
                    },
                )
            elif tag == "device_ref":
                self._insert_attrs(
                    connection,
                    "mame_device_ref",
                    machine_id,
                    child.attrib,
                    {
                        "name": "name",
                        "tag": "tag",
                        "mandatory": "mandatory",
                    },
                )
            elif tag == "sample":
                self._insert_attrs(
                    connection, "mame_sample", machine_id, child.attrib, {"name": "name"}
                )
            elif tag == "chip":
                self._insert_attrs(
                    connection,
                    "mame_chip",
                    machine_id,
                    child.attrib,
                    {
                        "type": "type",
                        "name": "name",
                        "clock": "clock",
                        "tag": "tag",
                    },
                )
            elif tag == "sound":
                self._insert_attrs(
                    connection, "mame_sound", machine_id, child.attrib, {"channels": "channels"}
                )
            elif tag == "display":
                self._insert_display(connection, machine_id, child)
                display_count += 1
            elif tag == "input":
                self._insert_attrs(
                    connection,
                    "mame_input",
                    machine_id,
                    child.attrib,
                    {
                        "players": "players",
                        "buttons": "buttons",
                        "coins": "coins",
                        "service": "service",
                        "tilt": "tilt",
                    },
                )
                for control in child.findall("control"):
                    connection.execute(
                        """UPDATE mame_input SET control_type=?, ways=?, minimum=?, maximum=?, sensitivity=?, keydelta=?, reverse=?
                        WHERE id=(SELECT MAX(id) FROM mame_input WHERE machine_id=?)""",
                        (
                            control.attrib.get("type"),
                            control.attrib.get("ways"),
                            control.attrib.get("minimum"),
                            control.attrib.get("maximum"),
                            control.attrib.get("sensitivity"),
                            control.attrib.get("keydelta"),
                            control.attrib.get("reverse"),
                            machine_id,
                        ),
                    )
            elif tag == "dipswitch":
                row = connection.execute(
                    "INSERT INTO mame_dipswitch(machine_id,name,tag,mask) VALUES(?,?,?,?)",
                    (
                        machine_id,
                        child.attrib.get("name"),
                        child.attrib.get("tag"),
                        child.attrib.get("mask"),
                    ),
                )
                dip_id = require_lastrowid(row.lastrowid)
                for value in child.findall("dipvalue"):
                    connection.execute(
                        "INSERT INTO mame_dipvalue(dipswitch_id,name,value,default_value) VALUES(?,?,?,?)",
                        (
                            dip_id,
                            value.attrib.get("name"),
                            value.attrib.get("value"),
                            value.attrib.get("default"),
                        ),
                    )
            elif tag == "configuration":
                row = connection.execute(
                    "INSERT INTO mame_configuration(machine_id,name,tag,mask) VALUES(?,?,?,?)",
                    (
                        machine_id,
                        child.attrib.get("name"),
                        child.attrib.get("tag"),
                        child.attrib.get("mask"),
                    ),
                )
                config_id = require_lastrowid(row.lastrowid)
                for value in (
                    child.findall("conflocation")
                    + child.findall("confsetting")
                    + child.findall("configvalue")
                ):
                    connection.execute(
                        "INSERT INTO mame_configvalue(configuration_id,name,value,default_value) VALUES(?,?,?,?)",
                        (
                            config_id,
                            value.attrib.get("name"),
                            value.attrib.get("value"),
                            value.attrib.get("default"),
                        ),
                    )
            elif tag == "port":
                self._insert_attrs(
                    connection,
                    "mame_port",
                    machine_id,
                    child.attrib,
                    {
                        "tag": "tag",
                        "type": "type",
                        "mask": "mask",
                        "defvalue": "defvalue",
                        "value": "value",
                    },
                )
            elif tag == "adjuster":
                self._insert_attrs(
                    connection,
                    "mame_adjuster",
                    machine_id,
                    child.attrib,
                    {
                        "name": "name",
                        "default": "default_value",
                        "minimum": "minimum",
                        "maximum": "maximum",
                    },
                )
            elif tag == "driver":
                self._insert_attrs(
                    connection,
                    "mame_driver",
                    machine_id,
                    child.attrib,
                    {
                        "status": "status",
                        "emulation": "emulation",
                        "color": "color",
                        "sound": "sound",
                        "graphic": "graphic",
                        "cocktail": "cocktail",
                        "protection": "protection",
                        "savestate": "savestate",
                    },
                )
            elif tag == "feature":
                self._insert_attrs(
                    connection,
                    "mame_feature",
                    machine_id,
                    child.attrib,
                    {
                        "type": "type",
                        "status": "status",
                        "overall": "overall",
                    },
                )
            elif tag == "device":
                self._insert_attrs(
                    connection,
                    "mame_device",
                    machine_id,
                    child.attrib,
                    {
                        "type": "type",
                        "tag": "tag",
                        "clock": "clock",
                        "shortname": "shortname",
                        "name": "name",
                        "fixed_image": "fixed_image",
                    },
                )
            elif tag == "slot":
                row = connection.execute(
                    "INSERT INTO mame_slot(machine_id,name,tag,fixed) VALUES(?,?,?,?)",
                    (
                        machine_id,
                        child.attrib.get("name"),
                        child.attrib.get("tag"),
                        child.attrib.get("fixed"),
                    ),
                )
                slot_id = require_lastrowid(row.lastrowid)
                for option in child.findall("slotoption"):
                    connection.execute(
                        "INSERT INTO mame_slotoption(slot_id,name,devname,default_value,selectable) VALUES(?,?,?,?,?)",
                        (
                            slot_id,
                            option.attrib.get("name"),
                            option.attrib.get("devname"),
                            option.attrib.get("default"),
                            option.attrib.get("selectable"),
                        ),
                    )
            elif tag == "softwarelist":
                self._insert_attrs(
                    connection,
                    "mame_softwarelist",
                    machine_id,
                    child.attrib,
                    {
                        "tag": "tag",
                        "name": "name",
                        "status": "status",
                        "filter": "filter",
                    },
                )
            elif tag == "ramoption":
                self._insert_attrs(
                    connection,
                    "mame_ramoption",
                    machine_id,
                    child.attrib,
                    {
                        "name": "name",
                        "default": "default_value",
                    },
                )
        return display_count

    def _insert_display(
        self, connection: sqlite3.Connection, machine_id: int, element: ET.Element
    ) -> None:
        """Insere todos os atributos de timing/display conhecidos."""
        a = element.attrib
        connection.execute(
            """INSERT INTO mame_display
            (machine_id,tag,type,rotate,width,height,refresh_hz,refresh_raw,pixclock,htotal,hbend,hbstart,
             vtotal,vbend,vbstart,hsync,vsync,orientation_raw,source,confidence)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                machine_id,
                a.get("tag"),
                a.get("type"),
                a.get("rotate"),
                self._int(a.get("width")),
                self._int(a.get("height")),
                self._float(a.get("refresh")),
                a.get("refresh"),
                a.get("pixclock"),
                a.get("htotal"),
                a.get("hbend"),
                a.get("hbstart"),
                a.get("vtotal"),
                a.get("vbend"),
                a.get("vbstart"),
                a.get("hsync"),
                a.get("vsync"),
                a.get("rotate"),
                "listxml",
                "authoritative",
            ),
        )

    @staticmethod
    def _insert_attrs(
        connection, table: str, machine_id: int, attrs: dict[str, str], mapping: dict[str, str]
    ) -> None:
        """Insere uma entidade simples usando um mapeamento atributo→coluna."""
        columns = ["machine_id", *mapping.values()]
        values = [machine_id, *(attrs.get(source) for source in mapping)]
        placeholders = ",".join("?" for _ in columns)
        connection.execute(
            f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})",
            values,
        )

    @staticmethod
    def _int(value: str | None) -> int | None:
        """Converte inteiro opcional sem transformar ausência em zero."""
        try:
            return int(value) if value is not None else None
        except ValueError:
            return None

    @staticmethod
    def _float(value: str | None) -> float | None:
        """Converte float opcional sem perder o valor textual original."""
        try:
            return float(value) if value is not None else None
        except ValueError:
            return None

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        """Aplica todas as migrations antes de persistir o catálogo."""
        migration_root = Path(__file__).resolve().parents[1] / "database" / "migrations"
        connection.executescript(
            (migration_root / "001_configuration_schema.sql").read_text(encoding="utf-8")
        )
        second = migration_root / "002_configuration_localization.sql"
        if second.is_file():
            connection.executescript(second.read_text(encoding="utf-8"))
        connection.executescript(
            (migration_root / "003_mame_catalog_schema.sql").read_text(encoding="utf-8")
        )


__all__ = ["DisplayFact", "DisplayImportResult", "MameDisplayCatalog", "MameDisplayCatalogError"]
