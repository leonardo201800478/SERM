"""Aquisição e persistência do ListXML do MAME.

Fase atual do SERM: ingestão *lossless*. O ListXML inteiro é a fonte de verdade
antes de qualquer normalização. Isso evita transformar a aquisição de 320+ MB em
milhões de INSERTs e permite que o schema analítico seja construído posteriormente
sem perder nenhum dado do XML original.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Callable
import xml.etree.ElementTree as ET

from ..runtime.paths import data_root, database_path


class MameCatalogError(RuntimeError):
    """Erro de configuração, captura ou persistência do catálogo MAME."""


class MameCatalogService:
    """Captura o ListXML e persiste o documento completo de forma atômica."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    DB_FILE = database_path()
    RAW_FILE = data_root() / "mame" / "metadata" / "listxml.xml"
    RAW_ROOT = data_root() / "mame" / "listxml"
    LOG_INTERVAL = 5 * 1024 * 1024

    def __init__(self, logger: Callable[[str], None] | None = None) -> None:
        """Cria o serviço e conecta o logger opcional da GUI."""
        self.logger = logger or (lambda message: logging.getLogger(__name__).info(message))

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
        """Captura e grava o ListXML completo sem normalizá-lo nesta etapa."""
        executable = self.configured_executable()
        started = perf_counter()
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self._log(f"MAME | [{run_id}] | START | aquisição lossless do ListXML")
        self._log(f"MAME | [{run_id}] | EXECUTÁVEL | {executable}")
        self._log("MAME | [CAPTURE] | comando=mame.exe -listxml")

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
        self._log(f"MAME | [{run_id}] | RAW FILE OK | {source}")

        db_started = perf_counter()
        with sqlite3.connect(self.DB_FILE, timeout=60.0) as db:
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
                return self._result(existing[0], existing[1], existing[2], source, source_hash, started, True, run_id)

            now = datetime.now(timezone.utc).isoformat()
            self._log(f"MAME | [{run_id}] | DB | criando importação | tamanho={self._human_bytes(raw_bytes)}")
            cur = db.execute(
                "INSERT INTO mame_listxml_import (emulator_id,executable,mame_build,mame_config,debug,imported_at,source_hash,xml_path,machine_count,parser_version) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (int(emulator[0]), str(executable), build, root.attrib.get("mameconfig"), root.attrib.get("debug"), now, source_hash, str(source), machine_count, "lossless-1.0"),
            )
            import_id = int(cur.lastrowid)
            self._log(f"MAME | [{run_id}] | DB | import_id={import_id} | gravando documento completo")
            db.execute(
                "INSERT INTO mame_listxml_document (import_id,source_hash,encoding,xml_text,byte_length,stored_at) VALUES (?,?,?,?,?,?)",
                (import_id, source_hash, "utf-8", xml_text, raw_bytes, now),
            )
            db.commit()
            db_size = self.DB_FILE.stat().st_size if self.DB_FILE.exists() else 0

        db_elapsed = perf_counter() - db_started
        elapsed = perf_counter() - started
        self._log(f"MAME | [{run_id}] | DB OK | documento lossless persistido | banco={self._human_bytes(db_size)} | tempo={db_elapsed:.2f}s")
        self._log(f"MAME | [{run_id}] | AUDITORIA | máquinas={machine_count:,} | XML={self._human_bytes(raw_bytes)} | hash={source_hash[:16]}")
        self._log(f"MAME | [{run_id}] | DONE | ingestão lossless concluída | tempo_total={elapsed:.2f}s")
        return self._result(import_id, build, machine_count, source, source_hash, started, False, run_id)

    @staticmethod
    def _run_mame(executable: Path, timeout: float) -> str:
        """Executa MAME de modo seguro e retorna o XML completo."""
        try:
            result = subprocess.run(
                [str(executable), "-listxml"], cwd=executable.parent, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=timeout, check=False, shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
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
        """Verifica somente as tabelas necessárias para a ingestão lossless."""
        required = {"emulator_definition", "mame_listxml_import", "mame_listxml_document"}
        existing = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = sorted(required - existing)
        if missing:
            raise MameCatalogError("Schema insuficiente para ingestão lossless: " + ", ".join(missing))

    def _result(self, import_id: int, build: str | None, machines: int, source: Path, source_hash: str,
                started: float, deduplicated: bool, run_id: str) -> dict[str, object]:
        """Monta o resultado padronizado da operação."""
        return {
            "import_id": import_id, "mame_build": build, "machine_count": int(machines),
            "display_count": 0, "raw_xml": self.RAW_FILE, "xml_path": source,
            "database": self.DB_FILE, "source_hash": source_hash,
            "elapsed_seconds": perf_counter() - started, "deduplicated": deduplicated,
            "lossless": True, "run_id": run_id,
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
