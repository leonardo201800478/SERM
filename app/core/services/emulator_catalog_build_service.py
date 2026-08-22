"""Orquestra geração e publicação dos catálogos dos emuladores.

O serviço conecta três camadas que permanecem independentes:

    descoberta/configuração -> EmulatorCatalogService -> Repository

Ele não executa instaladores, não consulta GitHub e não altera o dataset MAME
legado. A responsabilidade é somente produzir catálogos a partir das
instalações já configuradas e publicá-los atomicamente no banco.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from app.core.services.emulator_catalog_profile import select_machine_names
from app.core.services.emulator_catalog_repository import (
    CatalogPersistenceResult,
    EmulatorCatalogRepository,
)
from app.core.services.emulator_catalog_service import EmulatorCatalogService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CatalogBuildContext:
    """Instalações e versões conhecidas para uma execução de catálogo."""

    mame_executable: Path | None = None
    mame_version: str | None = None
    fbneo_executable: Path | None = None
    fbneo_version: str | None = None
    supermodel_root: Path | None = None
    supermodel_version: str | None = None
    flycast_version: str | None = None


class EmulatorCatalogBuildService:
    """Gera e publica catálogos de forma coordenada."""

    def __init__(
        self,
        catalog_service: EmulatorCatalogService,
        repository: EmulatorCatalogRepository,
    ) -> None:
        self.catalog_service = catalog_service
        self.repository = repository

    def build_mame(self, context: CatalogBuildContext) -> CatalogPersistenceResult:
        """Gera e publica o catálogo completo do MAME instalado."""
        if context.mame_executable is None:
            raise ValueError("MAME não está configurado")

        generated = self.catalog_service.generate_mame(context.mame_executable)
        return self.repository.replace_from_xml(
            emulator="mame",
            version=context.mame_version,
            source=generated.source,
            xml_path=generated.path,
        )

    def build_fbneo(self, context: CatalogBuildContext) -> CatalogPersistenceResult:
        """Gera e publica o catálogo Arcade fornecido pelo FBNeo."""
        if context.fbneo_executable is None:
            raise ValueError("FBNeo não está configurado")

        generated = self.catalog_service.generate_fbneo(context.fbneo_executable)
        return self.repository.replace_from_xml(
            emulator="fbneo",
            version=context.fbneo_version,
            source=generated.source,
            xml_path=generated.path,
        )

    def build_supermodel(self, context: CatalogBuildContext) -> CatalogPersistenceResult:
        """Gera e publica o catálogo oficial de Sega Model 3."""
        if context.supermodel_root is None:
            raise ValueError("Supermodel não está configurado")

        generated = self.catalog_service.generate_supermodel(context.supermodel_root)
        return self.repository.replace_from_xml(
            emulator="supermodel",
            version=context.supermodel_version,
            source=generated.source,
            xml_path=generated.path,
        )

    def build_flycast(
        self,
        context: CatalogBuildContext,
        *,
        mame_xml: Path | None = None,
    ) -> CatalogPersistenceResult:
        """Gera e publica o catálogo Arcade Flycast derivado do MAME.

        O MAME XML é usado somente como fonte de metadados; a seleção é feita
        pelo perfil de catálogo do Flycast, baseado em drivers explicitamente
        conhecidos. Dreamcast não entra neste catálogo.
        """
        source_xml = mame_xml or (self.catalog_service.catalog_root / "mame" / "listxml.xml")
        source_xml = Path(source_xml).expanduser().resolve()
        if not source_xml.is_file():
            raise FileNotFoundError(
                "LISTXML MAME necessário para o catálogo Flycast não encontrado: "
                f"{source_xml}"
            )

        names = self._select_flycast_names(source_xml)
        logger.info(
            "Flycast catalog: máquinas selecionadas a partir do MAME | count=%d",
            len(names),
        )
        generated = self.catalog_service.generate_flycast_from_mame(
            source_xml,
            names,
        )
        return self.repository.replace_from_xml(
            emulator="flycast",
            version=context.flycast_version,
            source=generated.source,
            xml_path=generated.path,
        )

    def build_all(
        self,
        context: CatalogBuildContext,
        *,
        include_flycast: bool = True,
    ) -> list[CatalogPersistenceResult]:
        """Gera todos os catálogos possíveis sem mascarar falhas individuais."""
        results: list[CatalogPersistenceResult] = []

        # MAME é construído primeiro porque Flycast usa seu LISTXML como
        # fonte. Os demais catálogos são independentes.
        jobs = [
            ("mame", lambda: self.build_mame(context)),
            ("fbneo", lambda: self.build_fbneo(context)),
            ("supermodel", lambda: self.build_supermodel(context)),
        ]
        if include_flycast:
            jobs.append(("flycast", lambda: self.build_flycast(context)))

        for emulator, job in jobs:
            try:
                result = job()
                results.append(result)
            except Exception:
                logger.exception(
                    "Catalog build: falha | emulator=%s",
                    emulator,
                )

        return results

    @staticmethod
    def _select_flycast_names(source_xml: Path) -> list[str]:
        """Lê metadados mínimos do MAME e aplica o perfil Flycast."""
        machines: list[dict[str, object]] = []
        context = ET.iterparse(source_xml, events=("end",))
        for _, element in context:
            if element.tag != "machine":
                continue
            machines.append(
                {
                    "name": element.get("name"),
                    "sourcefile": element.get("sourcefile"),
                }
            )
            element.clear()
        return select_machine_names("flycast", machines)
