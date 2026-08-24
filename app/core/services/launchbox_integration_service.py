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

    O arquivo ``mesen_libretro.info`` corresponde a
    ``mesen_libretro.dll``. O serviço-base acrescenta ``_libretro.dll``
    ao valor técnico de ``corename``; portanto, para um arquivo
    ``*_libretro.info``, o ``corename`` técnico precisa ser apenas o stem
    anterior a ``_libretro``. O nome amigável permanece intacto.
    """

    @staticmethod
    def _core_filename(info: RetroArchInfoCore) -> str:
        """Retorna o nome físico do DLL correspondente ao arquivo ``.info``.

        A transformação é deliberadamente baseada no nome do arquivo .info,
        e não em ``corename``. O catálogo oficial usa o mesmo stem para os
        pares ``.info``/``.dll``.
        """
        filename = Path(info.filename).name
        if filename.casefold().endswith("_libretro.info"):
            return filename[:-len(".info")] + ".dll"
        if filename.casefold().endswith(".info"):
            return filename[:-len(".info")] + ".dll"
        return f"{filename}_libretro.dll"

    @classmethod
    def _technical_corename(cls, info: RetroArchInfoCore) -> str:
        """Converte o nome físico do DLL para o identificador esperado pelo serviço-base.

        ``launchbox_integration_service_v2`` constrói o DLL como
        ``{corename}_libretro.dll``. Assim, ``mesen_libretro.dll`` deve ser
        representado internamente como ``mesen`` e não como
        ``mesen_libretro``. Isso evita o erro ``*_libretro_libretro.dll``.
        """
        dll_name = cls._core_filename(info)
        stem = Path(dll_name).stem
        if stem.casefold().endswith("_libretro"):
            stem = stem[:-len("_libretro")]
        return stem

    @classmethod
    def _normalize_core_identity(cls, infos: Iterable[RetroArchInfoCore]) -> list[RetroArchInfoCore]:
        """Normaliza apenas a identidade técnica, preservando a apresentação.

        ``display_name`` não é alterado. Apenas a cópia enviada ao motor
        legado recebe o ``corename`` técnico sem o sufixo ``_libretro``.
        """
        normalized: list[RetroArchInfoCore] = []
        for info in infos:
            normalized.append(replace(info, corename=cls._technical_corename(info)))
        return normalized

    def build_systems(
        self,
        infos: Iterable[RetroArchInfoCore],
        installation: LaunchBoxInstallation | None = None,
    ) -> list[LaunchBoxSystem]:
        """Constrói as plataformas usando DLLs fisicamente correspondentes aos .info."""
        return super().build_systems(self._normalize_core_identity(infos), installation)


__all__ = [
    "LaunchBoxIntegrationService",
    "LaunchBoxSystem",
    "LaunchBoxCoreOption",
    "LaunchBoxInstallation",
]
