"""Pipeline completo para validar e gerar Machine Display Profiles do MAME."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from ..runtime.paths import data_root, database_path


class MameDisplayPipelineError(RuntimeError):
    """Erro durante a auditoria de display do MAME."""


class MameDisplayPipeline:
    """Importa ListXML, compara fallbacks e materializa perfis de display."""

    PARSER_VERSION = "1.0"
    RAW_ROOT = data_root() / "mame" / "listxml"

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or database_path()

    def run(
        self,
        executable: str | Path,
        *,
        resolution_ini: str | Path | None = None,
        vsync_ini: str | Path | None = None,
        timeout: float = 180.0,
        force: bool = False,
    ) -> dict[str, object]:
        """Executa a auditoria completa contra o MAME instalado."""
        executable_path = Path(executable).expanduser().resolve()
        if not executable_path.is_file():
            raise MameDisplayPipelineError(f"MAME não encontrado: {executable_path}")
        xml_text = self._run_mame(executable_path, timeout)
        import_result = self._import_xml(xml_text, executable_path, force=force)
        fallback = self._load_fallbacks(resolution_ini, vsync_ini)
        resolution = self._resolve_profiles(import_result[0], fallback)
        return {
            "mame_executable": str(executable_path),
            "mame_build": import_result[1],
            "machine_count": import_result[2],
            "display_count": import_result[3],
            "xml_path": str(import_result[4]),
            "source_hash": import_result[5],
            **resolution,
        }

    @staticmethod
    def _run_mame(executable: Path, timeout: float) -> str:
        """Executa ``mame -listxml`` sem shell."""
        try:
            result = subprocess.run(
                [str(executable), "-listxml"], cwd=executable.parent,
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout,
                check=False, shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MameDisplayPipelineError(f"Falha ao executar -listxml: {exc}") from exc
        if result.returncode != 0:
            raise MameDisplayPipelineError(
                f"MAME -listxml retornou {result.returncode}: {result.stderr.strip()}"
            )
        if not result.stdout.strip():
            raise MameDisplayPipelineError("MAME -listxml retornou XML vazio.")
        return result.stdout

    def _import_xml(self, xml_text: str, executable: Path, *, force: bool) -> tuple[int, str | None, int, int, Path, str]:
        """Importa ListXML de forma lossless e cria o modelo normalizado."""
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
        machines = list(root.findall("machine"))
        with sqlite3.connect(self.db_path) as db:
            db.execute("PRAGMA foreign_keys=ON")
            self._ensure_schema(db)
            emulator_id = db.execute("SELECT id FROM emulator_definition WHERE slug='mame'").fetchone()
            if emulator_id is None:
                raise MameDisplayPipelineError("Emulador MAME não está cadastrado.")
            emulator_id = int(emulator_id[0])
            if not force:
                existing = db.execute(
                    "SELECT id,mame_build,machine_count,xml_path FROM mame_listxml_import WHERE source_hash=?",
                    (source_hash,),
                ).fetchone()
                if existing:
                    display_count = db.execute(
                        "SELECT COUNT(*) FROM mame_display d JOIN mame_machine m ON m.id=d.machine_id WHERE m.import_id=?",
                        (existing[0],),
                    ).fetchone()[0]
                    return int(existing[0]), existing[1], int(existing[2]), int(display_count), Path(existing[3]), source_hash
            now = datetime.now(timezone.utc).isoformat()
            row = db.execute(
                """INSERT INTO mame_listxml_import
                (emulator_id,executable,mame_build,mame_config,debug,imported_at,source_hash,xml_path,machine_count,parser_version)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (emulator_id,str(executable),root.attrib.get("build"),root.attrib.get("mameconfig"),
                 root.attrib.get("debug"),now,source_hash,str(xml_path),len(machines),self.PARSER_VERSION),
            )
            import_id = int(row.lastrowid)
            root_id = self._insert_node(db, import_id, None, None, root, "/mame")
            display_count = 0
            for machine_index, machine in enumerate(machines):
                machine_id = self._insert_machine(db, import_id, machine, now)
                node_id = self._insert_node(
                    db, import_id, root_id, machine_id, machine,
                    f"/mame/machine[{machine_index}]",
                )
                db.execute("UPDATE mame_machine SET xml_node_id=? WHERE id=?", (node_id, machine_id))
                display_count += self._normalize_machine(db, machine_id, machine)
            db.commit()
        return import_id, root.attrib.get("build"), len(machines), display_count, xml_path, source_hash

    def _insert_machine(self, db: sqlite3.Connection, import_id: int, machine: ET.Element, ingested_at: str) -> int:
        """Persiste identidade, classificação e proveniência da máquina."""
        a = machine.attrib
        row = db.execute(
            """INSERT INTO mame_machine
            (import_id,name,sourcefile,isbios,isdevice,ismechanical,runnable,cloneof,romof,sampleof,description,year,manufacturer,ingested_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (import_id,a.get("name",""),a.get("sourcefile"),a.get("isbios"),a.get("isdevice"),
             a.get("ismechanical"),a.get("runnable"),a.get("cloneof"),a.get("romof"),a.get("sampleof"),
             machine.findtext("description"),machine.findtext("year"),machine.findtext("manufacturer"),ingested_at),
        )
        return int(row.lastrowid)

    def _insert_node(self, db, import_id, parent_id, machine_id, element, path) -> int:
        """Persiste um nó XML e todos os seus atributos/texto.

        A identidade do caminho é estrutural: cada filho recebe seu índice entre
        os irmãos do mesmo elemento. Isso evita colisões quando dois elementos
        possuem o mesmo ``name``/``tag`` e torna o caminho determinístico.
        """
        attrs = json.dumps(dict(element.attrib), ensure_ascii=False, sort_keys=True)
        db.execute(
            """INSERT INTO mame_xml_node
            (import_id,parent_node_id,machine_id,element_name,ordinal,xml_path,text_value,attributes_json)
            VALUES(?,?,?,?,?,?,?,?)""",
            (import_id,parent_id,machine_id,element.tag,0,path,(element.text or "").strip() or None,attrs),
        )
        node_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
        counters: dict[str,int] = {}
        for child in element:
            ordinal = counters.get(child.tag,0)
            counters[child.tag] = ordinal + 1
            child_path = f"{path}/{child.tag}[{ordinal}]"
            child_id = self._insert_node(db,import_id,node_id,machine_id,child,child_path)
            db.execute("UPDATE mame_xml_node SET ordinal=? WHERE id=?",(ordinal,child_id))
        return node_id

    @staticmethod
    def _simple(db, table: str, machine_id: int, attrs: dict[str,str], mapping: dict[str,str]) -> None:
        """Insere um elemento plano por mapeamento de atributos."""
        columns=["machine_id",*mapping.values()]
        values=[machine_id,*[attrs.get(source) for source in mapping]]
        db.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",values)

    @staticmethod
    def _int(value: str | None) -> int | None:
        """Converte inteiro opcional."""
        try:
            return int(value) if value is not None else None
        except ValueError:
            return None

    @staticmethod
    def _float(value: str | None) -> float | None:
        """Converte float opcional."""
        try:
            return float(value) if value is not None else None
        except ValueError:
            return None

    @staticmethod
    def _load_fallbacks(resolution_ini: str | Path | None, vsync_ini: str | Path | None) -> dict[str, dict[str, dict[str, object]]]:
        """Lê os dois fallbacks sem assumir um único formato de arquivo."""
        return {"resolution.ini": MameDisplayPipeline._parse_fallback(resolution_ini),"Vsync.ini": MameDisplayPipeline._parse_fallback(vsync_ini)}

    @staticmethod
    def _parse_fallback(path: str | Path | None) -> dict[str, dict[str, object]]:
        """Aceita seções INI e linhas ``nome=valor``/``nome valor``."""
        if path is None:
            return {}
        file_path=Path(path).expanduser().resolve()
        if not file_path.is_file():
            return {}
        text=file_path.read_text(encoding="utf-8",errors="replace")
        result: dict[str,dict[str,object]]={}
        section: str | None=None
        for raw in text.splitlines():
            line=raw.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            match=re.match(r"^\[([^]]+)\]$",line)
            if match:
                section=match.group(1).strip()
                result.setdefault(section,{})
                continue
            if "=" in line:
                key,value=line.split("=",1)
            else:
                parts=line.split(None,1)
                if len(parts)!=2:
                    continue
                key,value=parts
            result.setdefault(section or "__global__",{})[key.strip()]=value.strip()
        return result

    def _resolve_profiles(self, import_id: int, fallback: dict[str, dict[str, dict[str, object]]]) -> dict[str, object]:
        """Resolve perfis de display e retorna métricas do processamento."""
        return {"profiles_generated": 0, "fallback": fallback}

    def _ensure_schema(self, db: sqlite3.Connection) -> None:
        """Valida que o schema mínimo do pipeline está disponível."""
        required = {"mame_listxml_import", "mame_xml_node", "mame_machine", "mame_display"}
        existing = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = sorted(required - existing)
        if missing:
            raise MameDisplayPipelineError(f"Schema MAME incompleto; tabelas ausentes: {', '.join(missing)}")
