"""Compatibilidade para o ingestor oficial do catálogo MAME."""

from __future__ import annotations

from pathlib import Path

from ..runtime.paths import database_path
from .mame_catalog_service import MameCatalogService


class MameCatalogIngestor:
    """Encaminha a ingestão para o serviço lossless + catálogo relacional."""

    def __init__(self, db_path: Path | None = None, logger=None) -> None:
        """Cria o ingestor usando o serviço canônico da V2."""
        self.db_path = db_path or database_path()
        self.service = MameCatalogService(logger=logger)

    def ingest(self, **kwargs) -> dict[str, object]:
        """Importa o ListXML completo sem gerar profiles."""
        return self.service.ingest(
            timeout=float(kwargs.get("timeout", 180.0)), force=bool(kwargs.get("force", False))
        )


__all__ = ["MameCatalogIngestor"]
