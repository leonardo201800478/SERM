"""Fontes alternativas de arquivos de suporte MAME.

O Progetto-SNAPS permanece como fonte primária. O repositório
AntoPISA/MAME_SupportFiles é tratado como fonte alternativa e complementar,
com URLs independentes por arquivo. Nenhuma fonte substitui o ListXML
authoritative do MAME.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote


PROGETTO_SNAPS_REPOSITORY = "https://www.progettosnaps.net"
GITHUB_SUPPORT_REPOSITORY = "https://github.com/AntoPISA/MAME_SupportFiles"
GITHUB_RAW_ROOT = "https://raw.githubusercontent.com/AntoPISA/MAME_SupportFiles/main"


@dataclass(frozen=True, slots=True)
class MameSupportSource:
    """Define um arquivo de suporte e suas fontes de aquisição."""

    name: str
    path: str
    primary_url: str | None
    alternate_url: str
    category: str
    mutable_each_mame_cycle: bool = True

    @property
    def urls(self) -> tuple[str, ...]:
        """Retorna as URLs disponíveis na ordem de preferência."""
        if self.primary_url:
            return (self.primary_url, self.alternate_url)
        return (self.alternate_url,)


# Arquivos relevantes para curadoria e apresentação no SERM.
# Os nomes/path são os existentes no snapshot do repositório de suporte.
SUPPORT_SOURCES: tuple[MameSupportSource, ...] = (
    MameSupportSource(
        "category.ini", "category.ini/category.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/category.ini", "classification",
    ),
    MameSupportSource(
        "catver.ini", "catver.ini/catver.ini", None,
        f"{GITHUB_RAW_ROOT}/catver.ini/catver.ini", "classification",
    ),
    MameSupportSource(
        "genre.ini", "catver.ini/genre.ini", None,
        f"{GITHUB_RAW_ROOT}/catver.ini/genre.ini", "classification",
    ),
    MameSupportSource(
        "bestgames.ini", "bestgames.ini/bestgames.ini", None,
        f"{GITHUB_RAW_ROOT}/bestgames.ini/bestgames.ini", "quality",
        mutable_each_mame_cycle=False,
    ),
    MameSupportSource(
        "Working Arcade.ini", "category.ini/Working Arcade.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/Working%20Arcade.ini", "working",
    ),
    MameSupportSource(
        "Working Arcade Clean.ini", "category.ini/Working Arcade Clean.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/Working%20Arcade%20Clean.ini", "working",
    ),
    MameSupportSource(
        "Not Working Arcade.ini", "category.ini/Not Working Arcade.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/Not%20Working%20Arcade.ini", "working",
    ),
    MameSupportSource(
        "Parents Arcade.ini", "category.ini/Parents Arcade.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/Parents%20Arcade.ini", "sets",
    ),
    MameSupportSource(
        "Clones Arcade.ini", "category.ini/Clones Arcade.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/Clones%20Arcade.ini", "sets",
    ),
    MameSupportSource(
        "Bootlegs.ini", "category.ini/Bootlegs.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/Bootlegs.ini", "curation",
    ),
    MameSupportSource(
        "Prototype.ini", "category.ini/Prototype.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/Prototype.ini", "curation",
    ),
    MameSupportSource(
        "Mechanical Arcade.ini", "category.ini/Mechanical Arcade.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/Mechanical%20Arcade.ini", "curation",
    ),
    MameSupportSource(
        "Non Mechanical Arcade.ini", "category.ini/Non Mechanical Arcade.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/Non%20Mechanical%20Arcade.ini", "curation",
    ),
    MameSupportSource(
        "players.ini", "category.ini/players.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/players.ini", "controls",
    ),
    MameSupportSource(
        "resolution.ini", "category.ini/resolution.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/resolution.ini", "display",
    ),
    MameSupportSource(
        "monochrome.ini", "category.ini/monochrome.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/monochrome.ini", "display",
    ),
    MameSupportSource(
        "driver.ini", "category.ini/driver.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/driver.ini", "driver",
    ),
    MameSupportSource(
        "mess.ini", "category.ini/mess.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/mess.ini", "platform",
    ),
    MameSupportSource(
        "CHD Working.ini", "category.ini/CHD Working.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/CHD%20Working.ini", "chd",
    ),
    MameSupportSource(
        "CHD (no BIOS).ini", "category.ini/CHD (no BIOS).ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/CHD%20%28no%20BIOS%29.ini", "chd",
    ),
    MameSupportSource(
        "screenless.ini", "category.ini/screenless.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/screenless.ini", "display",
    ),
    MameSupportSource(
        "artwork_necessary.ini", "category.ini/artwork_necessary.ini", None,
        f"{GITHUB_RAW_ROOT}/category.ini/artwork_necessary.ini", "artwork",
    ),
)


def get_support_source(name: str) -> MameSupportSource | None:
    """Localiza uma fonte pelo nome do arquivo, ignorando maiúsculas/minúsculas."""
    normalized = name.strip().casefold()
    return next((source for source in SUPPORT_SOURCES if source.name.casefold() == normalized), None)


def github_raw_url(path: str) -> str:
    """Constrói uma URL raw segura para qualquer arquivo do repositório."""
    parts = [quote(part, safe="") for part in path.split("/")]
    return f"{GITHUB_RAW_ROOT}/{'/'.join(parts)}"


__all__ = [
    "GITHUB_SUPPORT_REPOSITORY",
    "MameSupportSource",
    "PROGETTO_SNAPS_REPOSITORY",
    "SUPPORT_SOURCES",
    "get_support_source",
    "github_raw_url",
]
