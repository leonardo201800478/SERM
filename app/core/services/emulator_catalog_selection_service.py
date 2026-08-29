"""Seleção segura de máquinas para catálogos derivados.

Este serviço conecta o LISTXML do MAME aos perfis declarativos de catálogo
sem alterar o parser, o banco ou a reconstrução. A separação permite testar
a política de seleção independentemente da aquisição física do catálogo.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

from app.core.services.emulator_catalog_profile import (
    get_catalog_profile,
    select_machine_names,
)
from app.core.services.emulator_catalog_service import (
    CatalogResult,
    EmulatorCatalogService,
)

logger = logging.getLogger(__name__)


class EmulatorCatalogSelectionService:
    """Seleciona máquinas de uma fonte XML e delega a publicação ao catálogo."""

    def __init__(self, catalog_service: EmulatorCatalogService | None = None) -> None:
        self.catalog_service = catalog_service or EmulatorCatalogService()

    def generate_flycast_from_mame_profile(self, source_xml: Path) -> CatalogResult:
        """Gera o catálogo arcade do Flycast usando o perfil oficial interno.

        A seleção é baseada no ``sourcefile`` do LISTXML. Para o estado atual
        do projeto, isso limita o catálogo a Naomi/Naomi 2/Atomiswave, que são
        as plataformas arcade declaradas pelo Flycast. Dreamcast não entra
        nesta seleção.
        """
        source = Path(source_xml).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"LISTXML MAME não encontrado: {source}")

        profile = get_catalog_profile("flycast")
        machines: list[dict[str, object]] = []
        context = ET.iterparse(source, events=("end",))
        for _, element in context:
            if element.tag != "machine":
                continue
            machines.append({
                "name": element.get("name", ""),
                "sourcefile": element.get("sourcefile", ""),
            })
            element.clear()

        names = select_machine_names("flycast", machines)
        logger.info(
            "Emulator catalog selection: Flycast | profile=%s | machines=%d",
            profile.description,
            len(names),
        )
        return self.catalog_service.generate_flycast_from_mame(source, names)

    def select_names_from_mame(self, emulator: str, source_xml: Path) -> list[str]:
        """Retorna somente os nomes aceitos pelo perfil sem gerar arquivo."""
        source = Path(source_xml).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"LISTXML MAME não encontrado: {source}")

        machines: list[dict[str, object]] = []
        context = ET.iterparse(source, events=("end",))
        for _, element in context:
            if element.tag != "machine":
                continue
            machines.append({
                "name": element.get("name", ""),
                "sourcefile": element.get("sourcefile", ""),
            })
            element.clear()
        return select_machine_names(emulator, machines)
