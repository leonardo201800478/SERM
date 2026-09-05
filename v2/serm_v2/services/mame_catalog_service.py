"""Aquisição e persistência do catálogo completo do ListXML do MAME."""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from ..runtime.paths import data_root, database_path
from .mame_catalog_normalizer import MameCatalogNormalizer
from .mame_classification_service import MameClassificationService
from .mame_resolution_service import MameResolutionService
from .mame_vsync_service import MameVsyncService


class MameCatalogError(RuntimeError):
    """Erro de configuração, captura ou persistência do catálogo MAME."""


class MameCatalogService:
    """Captura ListXML, preserva a fonte e cria o catálogo relacional completo."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    DB_FILE = database_path()
    RAW_FILE = data_root() / "mame" / "metadata" / "listxml.xml"
    RAW_ROOT = data_root() / "mame" / "listxml"
    PARSER_VERSION = "catalog-2.0"

    def __init__(self, logger: Callable[[str], None] | None = None) -> None:
        """Cria o serviço e conecta o logger opcional da GUI."""
        self.logger = logger or (lambda message: logging.getLogger(__name__).info(message))
        self.normalizer = MameCatalogNormalizer(logger=self.logger)

    def _log(self, message: str) -> None:
        """Envia uma mensagem para a GUI e para o logging do aplicativo."""
        self.logger(message)

    def configured_executable(self) -> Path:
        """Retorna o executável MAME explicitamente escolhido em Diretórios."""
        try:
            data = json.loads(self.PATHS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise MameCatalogError("Não foi possível ler emulator_paths.json.") from exc
        raw = data.get("mame_executable")
        if not isinstance(raw, str) or not raw.strip():
            raise MameCatalogError("Nenhum executável MAME foi configurado em Diretórios.")
        executable = Path(raw).expanduser().resolve()
        if not executable.is_file():
            raise MameCatalogError(f"Executável MAME configurado não encontrado: {executable}")
        return executable

    def ingest(self, *, timeout: float = 180.0, force: bool = False) -> dict[str, object]:
        """Captura o ListXML e, após sucesso, importa CATLIST, Resolution e Vsync."""
        executable = self.configured_executable()
        started = perf_counter()
        run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        self._log(f"MAME | [{run_id}] | START | aquisição do catálogo ListXML")
        self._log(f"MAME | [{run_id}] | EXECUTÁVEL | {executable}")
        self._log(f"MAME | [{run_id}] | CAPTURE | comando=mame.exe -listxml")

        xml_text = self._run_mame(executable, timeout)
        raw_bytes = len(xml_text.encode("utf-8"))
        source_hash = hashlib.sha256(xml_text.encode("utf-8")).hexdigest()
        self._log(f"MAME | [{run_id}] | CAPTURE OK | tamanho={self._human_bytes(raw_bytes)} | sha256={source_hash[:16]}")

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise MameCatalogError(f"ListXML inválido: {exc}") from exc
        if root.tag != "mame":
            raise MameCatalogError(f"Raiz inesperada no ListXML: {root.tag}")
        machine_count = len(root.findall("machine"))
        build = root.attrib.get("build")
        self._log(f"MAME | [{run_id}] | PARSE OK | build={build or 'desconhecido'} | máquinas={machine_count:,}")

        self.RAW_ROOT.mkdir(parents=True, exist_ok=True)
        source = self.RAW_ROOT / f"listxml-{source_hash[:16]}.xml"
        source.write_text(xml_text, encoding="utf-8", newline="\n")
        self.RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.RAW_FILE.write_text(xml_text, encoding="utf-8", newline="\n")
        self._log(f"MAME | [{run_id}] | RAW FILE OK | {source}")

        db_started = perf_counter()
        with sqlite3.connect(self.DB_FILE, timeout=120.0) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=NORMAL")
            db.execute("PRAGMA temp_store=MEMORY")
            self._validate_schema(db)
            emulator = db.execute("SELECT id FROM emulator_definition WHERE slug='mame'").fetchone()
            if emulator is None:
                raise MameCatalogError("Emulador MAME não está cadastrado no banco.")

            existing = db.execute(
                "SELECT id,mame_build,machine_count,xml_path FROM mame_listxml_import WHERE source_hash=? ORDER BY id DESC LIMIT 1",
                (source_hash,),
            ).fetchone()
            if existing and not force:
                self._log(f"MAME | [{run_id}] | DEDUP | import_id={existing[0]} | hash já persistido")
                result = self._result(existing[0], existing[1], existing[2], Path(existing[3]) if existing[3] else source, source_hash, started, True, run_id)
                db.commit()
                result["ini_results"] = self._ingest_inis(executable.parent)
                return result

            now = datetime.now(UTC).isoformat()
            self._log(f"MAME | [{run_id}] | DB | criando importação | tamanho={self._human_bytes(raw_bytes)}")
            cur = db.execute(
                """INSERT INTO mame_listxml_import
                (emulator_id,executable,mame_build,mame_config,debug,imported_at,source_hash,xml_path,machine_count,byte_length,parser_version,status)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,'captured')""",
                (int(emulator[0]), str(executable), build, root.attrib.get("mameconfig"), root.attrib.get("debug"), now, source_hash, str(source), machine_count, raw_bytes, self.PARSER_VERSION),
            )
            import_id = int(cur.lastrowid)
            self._log(f"MAME | [{run_id}] | DB | import_id={import_id} | salvando documento lossless")
            db.execute(
                """INSERT INTO mame_listxml_document
                (import_id,source_hash,encoding,xml_text,byte_length,stored_at)
                VALUES(?,?,?,?,?,?)""",
                (import_id, source_hash, "utf-8", xml_text, raw_bytes, now),
            )
            self._log(f"MAME | [{run_id}] | CATALOG | iniciando normalização relacional")
            totals = self.normalizer.normalize(db, import_id, root)
            db.execute("UPDATE mame_listxml_import SET status='completed' WHERE id=?", (import_id,))
            db.commit()
            db_size = self.DB_FILE.stat().st_size if self.DB_FILE.exists() else 0

        db_elapsed = perf_counter() - db_started
        elapsed = perf_counter() - started
        self._log(
            f"MAME | [{run_id}] | CATALOG OK | máquinas={totals['machines']:,} | ROMs={totals['roms']:,} | "
            f"disks={totals['disks']:,} | displays={totals['displays']:,} | samples={totals['samples']:,} | "
            f"chips={totals['chips']:,} | dispositivos={totals['devices']:,} | tempo={float(totals['elapsed_seconds']):.2f}s"
        )
        self._log(f"MAME | [{run_id}] | DB OK | banco={self._human_bytes(db_size)} | tempo_db={db_elapsed:.2f}s")
        self._log(f"MAME | [{run_id}] | AUDITORIA | XML={self._human_bytes(raw_bytes)} | hash={source_hash[:16]} | máquinas={machine_count:,}")
        self._log(f"MAME | [{run_id}] | DONE | catálogo completo ingerido | tempo_total={elapsed:.2f}s")
        result = self._result(import_id, build, machine_count, source, source_hash, started, False, run_id, totals)
        result["ini_results"] = self._ingest_inis(executable.parent)
        return result

    def _ingest_inis(self, mame_root: Path) -> list[tuple[str, dict[str, object]]]:
        """Importa os INIs dependentes somente depois que o catálogo ListXML terminou."""
        stages = (
            ("CATLIST", MameClassificationService),
            ("RESOLUTION", MameResolutionService),
            ("VSYNC", MameVsyncService),
        )
        results: list[tuple[str, dict[str, object]]] = []
        total = len(stages)
        self._log(f"MAME | INIS | QUEUE | 1/{total} CATLIST → 2/{total} RESOLUTION → 3/{total} VSYNC")
        for index, (name, service_class) in enumerate(stages, 1):
            self._log(f"MAME | INIS | QUEUE | {index}/{total} | {name}")
            service = service_class(self.DB_FILE, mame_root)
            results.append((name, service.ingest(logger=self._log)))
        self._log("MAME | INIS | DONE | todas as fontes concluídas")
        return results

    @staticmethod
    def _run_mame(executable: Path, timeout: float) -> str:
        """Executa MAME de modo seguro e retorna o XML completo."""
        try:
            result = subprocess.run(
                [str(executable), "-listxml"], cwd=executable.parent, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False,
                shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MameCatalogError(f"Falha ao executar MAME -listxml: {exc}") from exc
        if result.returncode != 0:
            raise MameCatalogError(f"MAME -listxml retornou {result.returncode}: {result.stderr.strip()}")
        if not result.stdout.strip():
            raise MameCatalogError("MAME -listxml retornou XML vazio.")
        return result.stdout

    @staticmethod
    def _validate_schema(db: sqlite3.Connection) -> None:
        """Verifica o conjunto mínimo do catálogo relacional."""
        required = {
            "emulator_definition", "mame_listxml_import", "mame_listxml_document", "mame_machine",
            "mame_machine_metadata", "mame_rom", "mame_disk", "mame_display", "mame_sample",
            "mame_chip", "mame_device", "mame_device_ref", "mame_input", "mame_control",
            "mame_driver", "mame_feature", "mame_slot", "mame_slot_option", "mame_softwarelist",
            "mame_ramoption", "mame_dipswitch", "mame_dipvalue", "mame_configuration",
            "mame_confsetting", "mame_port", "mame_adjuster", "mame_biosset",
        }
        existing = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = sorted(required - existing)
        if missing:
            raise MameCatalogError("Schema MAME incompleto; migrations necessárias: " + ", ".join(missing))

    def _result(self, import_id: int, build: str | None, machines: int, source: Path, source_hash: str,
                started: float, deduplicated: bool, run_id: str, totals: dict[str, int | float] | None = None) -> dict[str, object]:
        """Monta o resultado padronizado da operação."""
        totals = totals or {}
        return {
            "import_id": import_id, "mame_build": build, "machine_count": int(machines),
            "display_count": int(totals.get("displays", 0)), "rom_count": int(totals.get("roms", 0)),
            "disk_count": int(totals.get("disks", 0)), "raw_xml": self.RAW_FILE, "xml_path": source,
            "database": self.DB_FILE, "source_hash": source_hash,
            "elapsed_seconds": perf_counter() - started, "deduplicated": deduplicated,
            "lossless": True, "catalog_complete": True, "profiles_generated": 0, "run_id": run_id,
        }

    @staticmethod
    def _human_bytes(value: int) -> str:
        """Converte bytes para uma unidade legível."""
        size = float(value)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{value} B"


__all__ = ["MameCatalogError", "MameCatalogService"]
