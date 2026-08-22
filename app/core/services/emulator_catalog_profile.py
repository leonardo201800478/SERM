"""Perfis declarativos de catálogo por emulador.

Esta camada responde a uma pergunta diferente do parser:

    "Quais máquinas de uma fonte podem ser tratadas por este emulador?"

Ela não consulta a Internet, não executa emuladores e não grava no banco.
Os perfis são deliberadamente conservadores: quando a origem não permite
identificar uma plataforma com segurança, a máquina não é incluída.

Fontes atuais:
* MAME: catálogo completo é o próprio MAME.
* Supermodel: o catálogo é obtido diretamente de Config/Games.xml.
* FBNeo: o catálogo é obtido diretamente de -listinfo.
* Flycast: para o subconjunto arcade derivado do MAME, somente drivers
  explicitamente associados a Naomi/Naomi 2/Atomiswave são selecionados.

O Flycast também suporta Dreamcast, mas essa plataforma não deve ser
misturada ao catálogo arcade do projeto nesta etapa.
"""
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

        O método usa apenas metadados do LISTXML. Não executa o emulador e
        não presume compatibilidade apenas pelo nome da ROM.
        """
        if self.source is CatalogSource.MAME:
            return True

        sourcefile = str(machine.get("sourcefile") or "").replace("\\", "/").casefold()
        if not sourcefile:
            return False

        return any(fragment.casefold() in sourcefile for fragment in self.sourcefile_fragments)


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
        ),
        sourcefile_fragments=(
            "/sega/naomi.cpp",
            "/sega/dc_atomiswave.cpp",
            "/sega/atomiswave.cpp",
        ),
        description=(
            "Arcade Flycast derivado do MAME: Naomi, Naomi 2 e Atomiswave. "
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
    """Seleciona nomes de máquinas aceitos pelo perfil.

    A função mantém a ordem da fonte e elimina duplicidades preservando a
    primeira ocorrência. Máquinas sem ``name`` são ignoradas.
    """
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
