"""Compatibilidade pública da integração LaunchBox.

A implementação foi separada para permitir evolução do catálogo sem alterar
os imports existentes da GUI.

Regra importante para RetroArch:
    o nome técnico do core carregado pelo LaunchBox é derivado do nome do
    arquivo ``*_libretro.info`` e não de ``corename``. O campo ``corename``
    é um nome amigável/metadado e pode conter espaços, pontuação ou outras
    diferenças em relação ao nome físico do DLL.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable

from app.core.services.launchbox_integration_service_v2 import (
    LaunchBoxCoreOption,
    LaunchBoxInstallation,
    LaunchBoxIntegrationService as _LaunchBoxIntegrationService,
    LaunchBoxSystem,
)
from app.core.services.retroarch_info_service import RetroArchInfoCore


class LaunchBoxIntegrationService(_LaunchBoxIntegrationService):
    """Integração LaunchBox usando o nome físico correto dos cores RetroArch.

    O arquivo ``mesen_libretro.info`` sempre corresponde a
    ``mesen_libretro.dll``; o valor ``corename = "Mesen"`` não é usado para
    reconstruir o nome do DLL. Isso evita associações quebradas como
    ``VICE x64sc_libretro.dll``.
    """

    @staticmethod
    def _core_filename(info: RetroArchInfoCore) -> str:
        """Retorna o nome exato do DLL correspondente ao ``.info``.

        A transformação é deliberadamente baseada no nome do arquivo .info.
        O catálogo oficial usa o mesmo stem para os pares ``.info``/``.dll``.
        """
        filename = Path(info.filename).name
        if filename.casefold().endswith("_libretro.info"):
            return filename[:-len(".info")] + ".dll"
        if filename.casefold().endswith(".info"):
            return filename[:-len(".info")] + ".dll"
        return f"{filename}_libretro.dll"

    @classmethod
    def _normalize_core_identity(cls, infos: Iterable[RetroArchInfoCore]) -> list[RetroArchInfoCore]:
        """Normaliza o identificador técnico do core sem alterar sua exibição.

        ``display_name`` permanece intacto para a interface; ``corename`` é
        substituído apenas na cópia enviada ao motor legado para que ele gere
        o DLL a partir do stem físico do .info.
        """
        normalized: list[RetroArchInfoCore] = []
        for info in infos:
            filename = cls._core_filename(info)
            stem = filename[:-len(".dll")] if filename.casefold().endswith(".dll") else Path(filename).stem
            normalized.append(replace(info, corename=stem))
        return normalized

    def build_systems(self, infos: Iterable[RetroArchInfoCore], installation: LaunchBoxInstallation | None = None) -> list[LaunchBoxSystem]:
        """Constrói as plataformas usando DLLs fisicamente correspondentes aos .info."""
        return super().build_systems(self._normalize_core_identity(infos), installation)


__all__ = [
    "LaunchBoxIntegrationService",
    "LaunchBoxSystem",
    "LaunchBoxCoreOption",
    "LaunchBoxInstallation",
]
