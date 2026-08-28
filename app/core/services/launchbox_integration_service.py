"""Compatibilidade pública da integração LaunchBox.

A implementação foi separada para permitir evolução do catálogo sem alterar
os imports existentes da GUI.
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
    """Integração LaunchBox com identidade física correta dos cores RetroArch."""

    EXCLUDED_SYSTEMS = frozenset({"microsoft xbox 360"})

    @staticmethod
    def _core_filename(info: RetroArchInfoCore) -> str:
        """Retorna o DLL correspondente ao arquivo ``.info``."""
        filename = Path(info.filename).name
        if filename.casefold().endswith("_libretro.info"):
            return filename[:-5] + ".dll"
        if filename.casefold().endswith(".info"):
            return filename[:-5] + ".dll"
        return f"{filename}_libretro.dll"

    @classmethod
    def _technical_corename(cls, info: RetroArchInfoCore) -> str:
        """Obtém o stem técnico esperado pelo serviço-base."""
        stem = Path(cls._core_filename(info)).stem
        if stem.casefold().endswith("_libretro"):
            stem = stem[:-9]
        return stem

    @classmethod
    def _normalize_core_identity(cls, infos: Iterable[RetroArchInfoCore]) -> list[RetroArchInfoCore]:
        """Normaliza somente a identidade técnica do core."""
        return [replace(info, corename=cls._technical_corename(info)) for info in infos]

    @staticmethod
    def _is_excluded_system(name: str) -> bool:
        """Indica plataformas explicitamente excluídas do catálogo canônico."""
        normalized = " ".join(str(name or "").casefold().split())
        return normalized in LaunchBoxIntegrationService.EXCLUDED_SYSTEMS

    @classmethod
    def _matching_system_names(cls, info: RetroArchInfoCore) -> tuple[str, ...]:
        """Mapeia todas as plataformas suportadas pelo metadata do core.

        O método considera ``system_name``, IDs e databases declarados no
        arquivo .info. Para cores multi-sistema, todas as plataformas
        relevantes são retornadas; nenhuma é descartada apenas por não ser a
        primeira correspondência.
        """
        candidates: list[str] = []
        tokens = [info.system_name, info.system_id, *info.databases]
        normalized_tokens = {" ".join(str(v or "").casefold().split()) for v in tokens if str(v or "").strip()}
        for canonical, (_name, _group, _generation, aliases) in cls.PLATFORM_ALIASES.items():
            aliases_norm = {" ".join(str(v).casefold().split()) for v in aliases}
            if canonical in normalized_tokens or normalized_tokens.intersection(aliases_norm):
                candidates.append(_name)
        core = str(info.corename or "").casefold()
        for platform in cls.CORE_PLATFORM_OVERRIDES.get(core, ()):
            if platform not in candidates:
                candidates.append(platform)
        # PUAE/Amiga AGA é uma variante do mesmo core e precisa ser explicitamente
        # criada quando a metadata aponta para Amiga/AGA.
        if core in {"puae", "puae2021"} and any("amiga" in token for token in normalized_tokens):
            if "Commodore Amiga" not in candidates:
                candidates.insert(0, "Commodore Amiga")
            if "Commodore Amiga AGA" not in candidates:
                candidates.insert(1, "Commodore Amiga AGA")
        if core == "picodrive" and ("sega 32x" in normalized_tokens or "32x" in normalized_tokens or "32x" in core):
            for platform in ("Sega 32X", "Sega CD 32X"):
                if platform not in candidates:
                    candidates.append(platform)
        return tuple(name for name in candidates if not cls._is_excluded_system(name))

    def build_systems(
        self,
        infos: Iterable[RetroArchInfoCore],
        installation: LaunchBoxInstallation | None = None,
    ) -> list[LaunchBoxSystem]:
        """Constrói as plataformas usando DLLs fisicamente correspondentes aos .info."""
        return super().build_systems(self._normalize_core_identity(infos), installation)


__all__ = ["LaunchBoxIntegrationService", "LaunchBoxSystem", "LaunchBoxCoreOption", "LaunchBoxInstallation"]
