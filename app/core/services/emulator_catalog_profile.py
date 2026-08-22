"""Perfis declarativos de catálogo por emulador."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping


class CatalogSource(StrEnum):
    """Fontes normalizadas utilizadas pelo projeto."""

    MAME = "mame"
    FBNEO = "fbneo"
    SUPERMODEL = "supermodel"
    FLYCAST = "flycast"


class MachinePlatform(StrEnum):
    """Plataformas arcade relevantes para os catálogos atuais."""

    ARCADE = "arcade"
    SEGA_NAOMI = "sega_naomi"
    SEGA_NAOMI_2 = "sega_naomi_2"
    SAMMY_ATOMISWAVE = "sammy_atomiswave"
    SEGA_SYSTEM_SP = "sega_system_sp"
    SEGA_MODEL_3 = "sega_model_3"


@dataclass(frozen=True, slots=True)
class CatalogProfile:
    """Define a política de seleção de máquinas de uma fonte."""

    emulator: str
    source: CatalogSource
    platforms: tuple[MachinePlatform, ...]
    sourcefile_fragments: tuple[str, ...] = ()
    description: str = ""

    def accepts(self, machine: Mapping[str, object]) -> bool:
        """Retorna ``True`` somente quando a máquina pertence ao perfil.

        A decisão utiliza o ``sourcefile`` informado pelo próprio MAME.
        """
        if self.source is CatalogSource.MAME:
            return True

        sourcefile = str(machine.get("sourcefile") or "").replace("\\", "/").casefold()
        if not sourcefile:
            return False

        normalized = sourcefile.removeprefix("src/mame/")
        return any(
            fragment.casefold().lstrip("/") in sourcefile
            or fragment.casefold().lstrip("/") in normalized
            for fragment in self.sourcefile_fragments
        )


PROFILES: dict[str, CatalogProfile] = {
    "mame": CatalogProfile(
        emulator="mame",
        source=CatalogSource.MAME,
        platforms=(MachinePlatform.ARCADE,),
        description="Catálogo completo produzido pelo próprio MAME.",
    ),
    "supermodel": CatalogProfile(
        emulator="supermodel",
        source=CatalogSource.SUPERMODEL,
        platforms=(MachinePlatform.SEGA_MODEL_3,),
        description="Sega Model 3; origem oficial Config/Games.xml.",
    ),
    "fbneo": CatalogProfile(
        emulator="fbneo",
        source=CatalogSource.FBNEO,
        platforms=(MachinePlatform.ARCADE,),
        description="Arcade suportado diretamente pelo FBNeo -listinfo.",
    ),
    "flycast": CatalogProfile(
        emulator="flycast",
        source=CatalogSource.FLYCAST,
        platforms=(
            MachinePlatform.SEGA_NAOMI,
            MachinePlatform.SEGA_NAOMI_2,
            MachinePlatform.SAMMY_ATOMISWAVE,
            MachinePlatform.SEGA_SYSTEM_SP,
        ),
        # MAME atual:
        #   sega/naomi.cpp          -> NAOMI / NAOMI 2, incluindo GD-ROM
        #   sega/dc_atomiswave.cpp  -> Sammy Atomiswave
        #   sega/segasp.cpp         -> Sega System SP
        # NAOMI/NAOMI 2 GD-ROM são modalidades do driver naomi.cpp.
        sourcefile_fragments=(
            "sega/naomi.cpp",
            "sega/dc_atomiswave.cpp",
            "sega/segasp.cpp",
            "naomi.cpp",
            "dc_atomiswave.cpp",
            "segasp.cpp",
        ),
        description=(
            "Arcade Flycast derivado do MAME: Sega NAOMI, NAOMI 2, "
            "NAOMI/NAOMI 2 GD-ROM, Sammy Atomiswave e Sega System SP. "
            "Dreamcast permanece fora deste catálogo arcade."
        ),
    ),
}


def get_catalog_profile(emulator: str) -> CatalogProfile:
    """Retorna o perfil normalizado do emulador informado."""
    key = emulator.strip().casefold()
    try:
        return PROFILES[key]
    except KeyError as exc:
        raise ValueError(f"Perfil de catálogo não suportado: {emulator}") from exc


def select_machine_names(emulator: str, machines: list[Mapping[str, object]]) -> list[str]:
    """Seleciona nomes de máquinas aceitos pelo perfil."""
    profile = get_catalog_profile(emulator)
    selected: list[str] = []
    seen: set[str] = set()
    for machine in machines:
        name = str(machine.get("name") or "").strip()
        if not name or name in seen or not profile.accepts(machine):
            continue
        seen.add(name)
        selected.append(name)
    return selected


def profile_summary(emulator: str) -> dict[str, object]:
    """Retorna uma representação simples do perfil para GUI/logs."""
    profile = get_catalog_profile(emulator)
    return {
        "emulator": profile.emulator,
        "source": profile.source.value,
        "platforms": [platform.value for platform in profile.platforms],
        "sourcefile_fragments": list(profile.sourcefile_fragments),
        "description": profile.description,
    }
