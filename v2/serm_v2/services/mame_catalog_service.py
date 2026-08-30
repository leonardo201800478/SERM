"""Serviço de catálogo MAME baseado no pipeline canônico da V2."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from time import perf_counter
from typing import Callable

from ..runtime.paths import data_root, database_path
from .mame_display_pipeline import MameDisplayPipeline, MameDisplayPipelineError


class MameCatalogError(RuntimeError):
    """Erro de configuração, extração ou persistência do catálogo MAME."""


class MameCatalogService:
    """Conecta o executável MAME configurado ao pipeline canônico do catálogo."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    DB_FILE = database_path()
    RAW_FILE = data_root() / "mame" / "metadata" / "listxml.xml"
    RAW_ROOT = data_root() / "mame" / "listxml"

    def __init__(self, logger: Callable[[str], None] | None = None) -> None:
        """Cria o serviço e conecta o logger opcional da GUI ao pipeline."""
        self.logger = logger or (lambda message: logging.getLogger(__name__).info(message))

    def _log(self, message: str) -> None:
        """Encaminha uma mensagem para a GUI ou para o logging padrão."""
        self.logger(message)

    def configured_executable(self) -> Path:
        """Retorna o mame.exe explicitamente escolhido na guia Diretórios."""
        try:
            data = json.loads(self.PATHS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise MameCatalogError("Não foi possível ler emulator_paths.json.") from exc
        raw = data.get("mame_executable")
        if not isinstance(raw, str) or not raw.strip():
            raise MameCatalogError("Nenhum executável MAME foi configurado em Diretórios. Selecione o mame.exe que deve produzir o catálogo.")
        executable = Path(raw).expanduser().resolve()
        if not executable.is_file():
            raise MameCatalogError(f"Executável MAME configurado não encontrado: {executable}")
        self._log(f"MAME | INFO | Executável validado: {executable}")
        return executable

    def ingest(self, *, timeout: float = 180.0, force: bool = False) -> dict[str, object]:
        """Executa -listxml e persiste importação, XML lossless e perfis de display."""
        executable = self.configured_executable()
        started = perf_counter()
        self._log("MAME | START | Iniciando captura do ListXML pelo executável configurado")
        self.RAW_ROOT.mkdir(parents=True, exist_ok=True)
        previous_raw_files = set(self.RAW_ROOT.glob("listxml-*.xml"))
        try:
            result = MameDisplayPipeline(self.DB_FILE, logger=self._log).run(
                executable, timeout=timeout, force=force
            )
        except MameDisplayPipelineError as exc:
            self._log(f"MAME | ERROR | {type(exc).__name__}: {exc}")
            self._log("MAME | DONE | Ingestão encerrada com erro; dados anteriores foram preservados")
            raise MameCatalogError(str(exc)) from exc

        self.RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
        source = Path(str(result["xml_path"]))
        if source.is_file() and source != self.RAW_FILE:
            self.RAW_FILE.write_bytes(source.read_bytes())
        elapsed = perf_counter() - started
        source_was_known = source in previous_raw_files
        self._log(f"MAME | DONE | máquinas={int(result['machine_count']):,} | displays={int(result['display_count']):,} | tempo={elapsed:.2f}s")
        return {
            "executable": executable,
            "machine_count": int(result["machine_count"]),
            "display_count": int(result["display_count"]),
            "mame_build": result.get("mame_build"),
            "raw_xml": self.RAW_FILE,
            "xml_path": source,
            "database": self.DB_FILE,
            "source_hash": result.get("source_hash"),
            "elapsed_seconds": elapsed,
            "source_was_known": source_was_known,
            "deduplicated": source_was_known and not force,
            "force": force,
        }


__all__ = ["MameCatalogError", "MameCatalogService"]
