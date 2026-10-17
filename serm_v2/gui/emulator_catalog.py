"""Catálogo central de plataformas e grupos de emuladores do SERM V2.

A classificação é compartilhada pelas telas que apresentam emuladores:
Home, Diretórios, Configurações e Vídeo. O catálogo descreve organização de
interface, não altera a responsabilidade técnica de cada emulador.
"""

from __future__ import annotations

from collections.abc import Iterable

EMULATOR_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Arcade", ("mame", "fbneo", "supermodel")),
    (
        "Nintendo",
        ("super_zsnes", "rmg", "dolphin", "cemu", "azaharplus", "azahar", "ryujinx_nextendo"),
    ),
    ("Sony", ("duckstation", "pcsx2", "rpcs3", "shadps4")),
    ("Sega", ("blastem", "ymir", "yabasanshiro", "flycast")),
    ("Microsoft", ("xemu", "xenia_canary")),
    ("Portáteis", ("sameboy", "mgba", "melonds", "ppsspp")),
    (
        "Computadores",
        (
            "vice",
            "altirra",
            "dosbox_staging",
            "dosbox_pure",
            "dosbox_x",
            "winuae",
            "xm6pro68k",
            "scummvm",
            "amiberry",
            "stella",
            "bigpemu",
        ),
    ),
    ("Multi-sistema", ("mesence", "ares", "bizhawk")),
)

ALL_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    *EMULATOR_GROUPS[:-1],
    ("Multi-sistema", (*EMULATOR_GROUPS[-1][1], "retroarch")),
)


def grouped_emulators(
    keys: Iterable[str], *, include_retroarch: bool = True
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Retorna os grupos na ordem da interface, filtrando pelos emuladores disponíveis."""
    available = {str(key) for key in keys}
    groups = ALL_GROUPS if include_retroarch else EMULATOR_GROUPS
    grouped: list[tuple[str, tuple[str, ...]]] = []
    for title, members in groups:
        selected = tuple(key for key in members if key in available)
        if selected:
            grouped.append((title, selected))
    return tuple(grouped)


def group_for(emulator: str) -> str:
    """Retorna o grupo principal de um emulador ou 'Outros' quando desconhecido."""
    key = str(emulator).casefold()
    for title, members in ALL_GROUPS:
        if key in members:
            return title
    return "Outros"


__all__ = ["EMULATOR_GROUPS", "ALL_GROUPS", "grouped_emulators", "group_for"]
