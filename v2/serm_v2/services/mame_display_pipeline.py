"""Pipeline eficiente de ingestão do ListXML do MAME."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from ..runtime.paths import data_root, database_path


class MameDisplayPipelineError(RuntimeError):
    """Erro durante a ingestão do catálogo MAME."""


class MameDisplayPipeline:
    """Captura ListXML, preserva XML bruto e cria catálogo normalizado."""

    PARSER_VERSION = "1.3"
    RAW_ROOT = data_root() / "mame" / "listxml"
    PROGRESS_INTERVAL = 250

    def __init__(self, db_path: Path | None = None, logger: Callable[[str], None] | None = None) -> None:
        self.db_path = db_path or database_path()
        self.logger = logger or (lambda message: None)

    def _log(self, message: str) -> None:
        """Envia uma mensagem para a GUI ou para o chamador do pipeline."""
        self.logger(message)

    @staticmethod
    def _bind_value(value: Any, *, operation: str, parameter: int, context: str = "") -> Any:
        """Converte apenas wrappers unitários e rejeita estruturas não escalares."""
        if isinstance(value, tuple):
            if len(value) == 1:
                return MameDisplayPipeline._bind_value(value[0], operation=operation, parameter=parameter, context=context)
            raise MameDisplayPipelineError(
                f"Valor não escalar no SQLite | operação={operation} | parâmetro={parameter} | "
                f"tipo=tuple | tamanho={len(value)} | contexto={context or 'não informado'}"
            )
        if isinstance(value, (list, dict, set)):
            raise MameDisplayPipelineError(
                f"Valor não escalar no SQLite | operação={operation} | parâmetro={parameter} | "
                f"tipo={type(value).__name__} | contexto={context or 'não informado'}"
            )
        return value

    def _execute(self, db: sqlite3.Connection, sql: str, params: Sequence[Any], *, operation: str, context: str = "") -> sqlite3.Cursor:
        """Executa SQL preparado com binds validados e diagnóstico contextual."""
        normalized = tuple(self._bind_value(value, operation=operation, parameter=index, context=context) for index, value in enumerate(params, 1))
        try:
            return db.execute(sql, normalized)
        except sqlite3.ProgrammingError as exc:
            raise MameDisplayPipelineError(
                f"Falha no SQLite | operação={operation} | parâmetros={len(normalized)} | contexto={context or 'não informado'} | {exc}"
            ) from exc

    def run(self, executable: str | Path, *, resolution_ini: str | Path | None = None, vsync_ini: str | Path | None = None,
            timeout: float = 180.0, force: bool = False) -> dict[str, object]:
        """Executa captura, ingestão e geração dos perfis de display."""
        executable_path = Path(executable).expanduser().resolve()
        if not executable_path.is_file():
            raise MameDisplayPipelineError(f"MAME não encontrado: {executable_path}")
        self._log(f"MAME | INFO | Executável validado: {executable_path}")
        self._log("MAME | START | Iniciando captura do ListXML pelo executável configurado")
        xml_text = self._run_mame(executable_path, timeout)
        self._log(f"MAME | INFO | ListXML capturado | bytes={len(xml_text.encode('utf-8')):,}")
        result = self._import_xml(xml_text, executable_path, force=force)
        fallback = self._load_fallbacks(resolution_ini, vsync_ini)
        profiles = self._resolve_profiles(result[0], fallback)
        return {"mame_executable": str(executable_path), "mame_build": result[1], "machine_count": result[2],
                "display_count": result[3], "xml_path": str(result[4]), "source_hash": result[5], **profiles}

    @staticmethod
    def _run_mame(executable: Path, timeout: float) -> str:
        """Executa MAME sem shell e retorna o ListXML."""
        try:
            result = subprocess.run([str(executable), "-listxml"], cwd=executable.parent, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False,
                shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MameDisplayPipelineError(f"Falha ao executar -listxml: {exc}") from exc
        if result.returncode != 0:
            raise MameDisplayPipelineError(f"MAME -listxml retornou {result.returncode}: {result.stderr.strip()}")
        if not result.stdout.strip():
            raise MameDisplayPipelineError("MAME -listxml retornou XML vazio.")
        return result.stdout

    def _import_xml(self, xml_text: str, executable: Path, *, force: bool) -> tuple[int, str | None, int, int, Path, str]:
        """Importa o catálogo atomicamente e registra progresso periódico."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise MameDisplayPipelineError("ListXML inválido.") from exc
        if root.tag != "mame":
            raise MameDisplayPipelineError(f"Raiz inesperada: {root.tag}")
        source_hash = hashlib.sha256(xml_text.encode("utf-8")).hexdigest()
        self.RAW_ROOT.mkdir(parents=True, exist_ok=True)
        xml_path = self.RAW_ROOT / f"listxml-{source_hash[:16]}.xml"
        xml_path.write_text(xml_text, encoding="utf-8", newline="\n")
        machines = root.findall("machine")
        self._log(f"MAME | INFO | XML validado | máquinas={len(machines):,} | hash={source_hash[:16]}")

        with sqlite3.connect(self.db_path) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA synchronous=NORMAL")
            db.execute("PRAGMA temp_store=MEMORY")
            self._ensure_schema(db)
            row = db.execute("SELECT id FROM emulator_definition WHERE slug='mame'").fetchone()
            if row is None:
                raise MameDisplayPipelineError("Emulador MAME não está cadastrado.")
            emulator_id = int(row[0])
            if not force:
                existing = db.execute("SELECT id,mame_build,machine_count,xml_path FROM mame_listxml_import WHERE source_hash=? ORDER BY id DESC LIMIT 1", (source_hash,)).fetchone()
                if existing:
                    display_total = db.execute("SELECT COUNT(*) FROM mame_display d JOIN mame_machine m ON m.id=d.machine_id WHERE m.import_id=?", (existing[0],)).fetchone()[0]
                    self._log(f"MAME | INFO | ListXML já ingerido | import_id={existing[0]}")
                    return int(existing[0]), existing[1], int(existing[2]), int(display_total), Path(existing[3]) if existing[3] else xml_path, source_hash
            now = datetime.now(timezone.utc).isoformat()
            cur = self._execute(db, "INSERT INTO mame_listxml_import (emulator_id,executable,mame_build,mame_config,debug,imported_at,source_hash,xml_path,machine_count,parser_version) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (emulator_id, str(executable), root.attrib.get("build"), root.attrib.get("mameconfig"), root.attrib.get("debug"), now, source_hash, str(xml_path), len(machines), self.PARSER_VERSION),
                operation="mame_listxml_import")
            import_id = int(cur.lastrowid)
            root_id = self._insert_node(db, import_id, None, None, root, "/mame")
            totals = [1, 0, 0, 0, 0]
            self._log(f"MAME | INFO | import_id={import_id} | iniciando persistência")
            for machine_index, machine in enumerate(machines):
                context = f"machine[{machine_index}] name={machine.attrib.get('name','?')}"
                machine_id = self._insert_machine(db, import_id, machine, now, context=context)
                machine_path = f"/mame/machine[{machine_index}]"
                node_id, nodes = self._insert_node(db, import_id, root_id, machine_id, machine, machine_path)
                totals[0] += nodes
                self._execute(db, "UPDATE mame_machine SET xml_node_id=? WHERE id=?", (node_id, machine_id), operation="mame_machine.xml_node_id", context=context)
                d, r, k, s = self._normalize_machine(db, machine_id, machine, machine_path, context=context)
                totals[1] += r; totals[2] += k; totals[3] += s; totals[4] += d
                if (machine_index + 1) % self.PROGRESS_INTERVAL == 0 or machine_index + 1 == len(machines):
                    pct = (machine_index + 1) * 100 / len(machines)
                    self._log(f"MAME | PROGRESS | {machine_index + 1:,}/{len(machines):,} | {pct:6.2f}% | nós={totals[0]:,} | ROMs={totals[1]:,} | disks={totals[2]:,} | samples={totals[3]:,} | displays={totals[4]:,}")
            db.commit()
            self._log(f"MAME | INFO | persistência concluída | máquinas={len(machines):,} | nós={totals[0]:,} | ROMs={totals[1]:,} | disks={totals[2]:,} | samples={totals[3]:,} | displays={totals[4]:,}")
        return import_id, root.attrib.get("build"), len(machines), totals[4], xml_path, source_hash

    def _insert_machine(self, self_db: sqlite3.Connection, import_id: int, machine: ET.Element, ingested_at: str, *, context: str) -> int:
        """Insere a identidade e metadados básicos de uma máquina."""
        a = machine.attrib
        cur = self._execute(self_db, "INSERT INTO mame_machine (import_id,name,sourcefile,isbios,isdevice,ismechanical,runnable,cloneof,romof,sampleof,description,year,manufacturer,ingested_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (import_id, a.get("name", ""), a.get("sourcefile"), a.get("isbios"), a.get("isdevice"), a.get("ismechanical"), a.get("runnable"), a.get("cloneof"), a.get("romof"), a.get("sampleof"), machine.findtext("description"), machine.findtext("year"), machine.findtext("manufacturer"), ingested_at),
            operation="mame_machine", context=context)
        return int(cur.lastrowid)

    def _insert_node(self, db: sqlite3.Connection, import_id: int, parent_id: int | None, machine_id: int | None, element: ET.Element, path: str) -> tuple[int, int]:
        """Insere recursivamente a árvore XML sem consultas last_insert_rowid."""
        cur = self._execute(db, "INSERT INTO mame_xml_node (import_id,parent_node_id,machine_id,element_name,ordinal,xml_path,text_value,attributes_json) VALUES(?,?,?,?,?,?,?,?)",
            (import_id, parent_id, machine_id, element.tag, 0, path, (element.text or "").strip() or None, json.dumps(dict(element.attrib), ensure_ascii=False, sort_keys=True)), operation="mame_xml_node", context=path)
        node_id = int(cur.lastrowid); count = 1
        counters: dict[str, int] = {}
        for child in element:
            ordinal = counters.get(child.tag, 0); counters[child.tag] = ordinal + 1
            _, child_count = self._insert_node(db, import_id, node_id, machine_id, child, f"{path}/{child.tag}[{ordinal}]")
            count += child_count
        return node_id, count

    def _normalize_machine(self, db: sqlite3.Connection, machine_id: int, machine: ET.Element, machine_path: str, *, context: str) -> tuple[int, int, int, int]:
        """Normaliza displays, ROMs, disks e samples."""
        d = r = k = s = 0
        for display_index, display in enumerate(machine.findall("display")):
            a = display.attrib; width = self._int(a.get("width")); height = self._int(a.get("height")); refresh_raw = a.get("refresh") or a.get("refresh_hz"); refresh = self._float(refresh_raw); node_id = self._find_node_id(db, machine_id, f"{machine_path}/display[{display_index}]")
            self._execute(db, "INSERT INTO mame_display (machine_id,tag,type,rotate,width,height,refresh_hz,refresh_raw,pixclock,htotal,hbend,hbstart,vtotal,vbend,vbstart,hsync,vsync,xaspect,yaspect,orientation_raw,source,confidence,xml_node_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (machine_id,a.get("tag"),a.get("type"),a.get("rotate"),width,height,refresh,refresh_raw,a.get("pixclock"),a.get("htotal"),a.get("hbend"),a.get("hbstart"),a.get("vtotal"),a.get("vbend"),a.get("vbstart"),a.get("hsync"),a.get("vsync"),self._int(a.get("xaspect")),self._int(a.get("yaspect")),a.get("rotate"),"listxml","authoritative",node_id), operation="mame_display", context=f"{context}/display[{display_index}]"); d += 1
        for rom in machine.findall("rom"): self._insert_rom(db, machine_id, rom, context=context); r += 1
        for disk in machine.findall("disk"): self._insert_disk(db, machine_id, disk, context=context); k += 1
        for sample in machine.findall("sample"):
            self._execute(db, "INSERT INTO mame_sample(machine_id,name) VALUES(?,?)", (machine_id, sample.attrib.get("name")), operation="mame_sample", context=context); s += 1
        return d, r, k, s

    def _insert_rom(self, db: sqlite3.Connection, machine_id: int, element: ET.Element, *, context: str) -> None:
        """Persiste um ROM."""
        a = element.attrib; self._execute(db, "INSERT INTO mame_rom (machine_id,name,bios,size,crc,sha1,md5,merge,region,offset,status,optional,dispose) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (machine_id,a.get("name"),a.get("bios"),a.get("size"),a.get("crc"),a.get("sha1"),a.get("md5"),a.get("merge"),a.get("region"),a.get("offset"),a.get("status"),a.get("optional"),a.get("dispose")), operation="mame_rom", context=context)

    def _insert_disk(self, db: sqlite3.Connection, machine_id: int, element: ET.Element, *, context: str) -> None:
        """Persiste um disk."""
        a = element.attrib; self._execute(db, "INSERT INTO mame_disk (machine_id,name,md5,sha1,merge,region,index_value,writable,status,optional) VALUES(?,?,?,?,?,?,?,?,?,?)", (machine_id,a.get("name"),a.get("md5"),a.get("sha1"),a.get("merge"),a.get("region"),a.get("index"),a.get("writable"),a.get("status"),a.get("optional")), operation="mame_disk", context=context)

    @staticmethod
    def _find_node_id(db: sqlite3.Connection, machine_id: int, path: str) -> int | None:
        """Obtém o nó XML pelo caminho dentro da máquina."""
        row = db.execute("SELECT id FROM mame_xml_node WHERE machine_id=? AND xml_path=? LIMIT 1", (machine_id, path)).fetchone(); return int(row[0]) if row else None

    @staticmethod
    def _int(value: str | None) -> int | None:
        """Converte inteiro opcional."""
        try: return int(value) if value is not None else None
        except (TypeError, ValueError): return None

    @staticmethod
    def _float(value: str | None) -> float | None:
        """Converte float opcional."""
        if value is None: return None
        try: return float(value)
        except (TypeError, ValueError):
            match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value)); return float(match.group(0)) if match else None

    @staticmethod
    def _load_fallbacks(resolution_ini: str | Path | None, vsync_ini: str | Path | None) -> dict[str, dict[str, dict[str, object]]]:
        """Carrega INIs de fallback."""
        return {"resolution.ini": MameDisplayPipeline._parse_fallback(resolution_ini), "Vsync.ini": MameDisplayPipeline._parse_fallback(vsync_ini)}

    @staticmethod
    def _parse_fallback(path: str | Path | None) -> dict[str, dict[str, object]]:
        """Lê seções INI simples."""
        if path is None: return {}
        file_path = Path(path).expanduser().resolve()
        if not file_path.is_file(): return {}
        result: dict[str, dict[str, object]] = {}; section: str | None = None
        for raw in file_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith(("#", ";")): continue
            match = re.match(r"^\[([^]]+)\]$", line)
            if match: section = match.group(1).strip(); result.setdefault(section, {}); continue
            parts = line.split("=", 1) if "=" in line else line.split(None, 1)
            if len(parts) == 2: result.setdefault(section or "__global__", {})[parts[0].strip()] = parts[1].strip()
        return result

    def _resolve_profiles(self, import_id: int, fallback: dict[str, dict[str, dict[str, object]]]) -> dict[str, object]:
        """Gera perfis de display derivados do ListXML."""
        now = datetime.now(timezone.utc).isoformat(); generated = 0
        with sqlite3.connect(self.db_path) as db:
            db.execute("PRAGMA foreign_keys=ON")
            rows = db.execute("SELECT d.id,d.machine_id,d.width,d.height,d.refresh_hz,d.rotate,d.xaspect,d.yaspect FROM mame_display d JOIN mame_machine m ON m.id=d.machine_id WHERE m.import_id=?", (import_id,)).fetchall()
            for display_id, machine_id, width, height, refresh, rotate, xasp, yasp in rows:
                self._execute(db, "INSERT OR IGNORE INTO mame_machine_display_profile (machine_id,display_id,profile_version,width,height,refresh_hz,orientation,pixel_aspect_x,pixel_aspect_y,source_resolution,source_refresh,source_orientation,source_pixel_aspect,fallback_used,status,generated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (machine_id,display_id,self.PARSER_VERSION,width,height,refresh,rotate,xasp,yasp,"listxml" if width is not None and height is not None else "fallback","listxml" if refresh is not None else "fallback","listxml" if rotate is not None else "fallback","listxml" if xasp is not None and yasp is not None else "fallback",0,"resolved",now), operation="mame_machine_display_profile", context=f"display={display_id}"); generated += 1
            db.commit()
        self._log(f"MAME | INFO | Machine Display Profiles={generated:,}")
        return {"profiles_generated": generated, "fallback": fallback}

    @staticmethod
    def _ensure_schema(db: sqlite3.Connection) -> None:
        """Valida a presença das tabelas necessárias à ingestão."""
        required = {"mame_listxml_import","mame_xml_node","mame_machine","mame_rom","mame_disk","mame_display","mame_machine_display_profile"}
        existing = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = sorted(required - existing)
        if missing: raise MameDisplayPipelineError("Schema MAME incompleto; tabelas ausentes: " + ", ".join(missing))


__all__ = ["MameDisplayPipeline", "MameDisplayPipelineError"]
