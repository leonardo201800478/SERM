"""Serviço de catálogo MAME baseado no pipeline canônico da V2."""
from __future__ import annotations

import json
from pathlib import Path

from ..runtime.paths import data_root, database_path
from .mame_display_pipeline import MameDisplayPipeline, MameDisplayPipelineError


class MameCatalogError(RuntimeError):
    """Erro de configuração, extração ou persistência do catálogo MAME."""


class MameCatalogService:
    """Conecta o executável MAME configurado ao pipeline canônico do catálogo."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    DB_FILE = database_path()
    RAW_FILE = data_root() / "mame" / "metadata" / "listxml.xml"

    def configured_executable(self) -> Path:
        """Retorna o mame.exe explicitamente escolhido na guia Diretórios."""
        try:
            data = json.loads(self.PATHS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise MameCatalogError("Não foi possível ler emulator_paths.json.") from exc
        raw = data.get("mame_executable")
        if not isinstance(raw, str) or not raw.strip():
            raise MameCatalogError(
                "Nenhum executável MAME foi configurado em Diretórios. "
                "Selecione o mame.exe que deve produzir o catálogo."
            )
        executable = Path(raw).expanduser().resolve()
        if not executable.is_file():
            raise MameCatalogError(f"Executável MAME configurado não encontrado: {executable}")
        return executable

    def ingest(self, *, timeout: float = 180.0, force: bool = False) -> dict[str, object]:
        """Executa -listxml e persiste import_id, máquinas, XML lossless e displays."""
        executable = self.configured_executable()
        try:
            result = MameDisplayPipeline(self.DB_FILE).run(
                executable,
                timeout=timeout,
                force=force,
            )
        except MameDisplayPipelineError as exc:
            raise MameCatalogError(str(exc)) from exc

        # Compatibilidade com a GUI existente do Scraper de DATs.
        self.RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
        source = Path(str(result["xml_path"]))
        if source.is_file() and source != self.RAW_FILE:
            self.RAW_FILE.write_bytes(source.read_bytes())

        return {
            "executable": executable,
            "machine_count": int(result["machine_count"]),
            "display_count": int(result["display_count"]),
            "mame_build": result.get("mame_build"),
            "raw_xml": self.RAW_FILE,
            "xml_path": source,
            "database": self.DB_FILE,
            "source_hash": result.get("source_hash"),
        }


__all__ = ["MameCatalogError", "MameCatalogService"]
