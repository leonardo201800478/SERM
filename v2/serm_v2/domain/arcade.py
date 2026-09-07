"""Modelo de domínio canônico para o catálogo Arcade da V2.

O domínio não conhece SQLite, MAME ou a GUI. Ele representa somente a
identidade e os artefatos necessários para seleção, auditoria e construção de
sets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class RomStatus(StrEnum):
    """Estado de uma ROM em relação ao conjunto esperado."""

    OK = "ok"
    FIXABLE = "fixable"
    MISSING = "missing"
    UNKNOWN = "unknown"


class MachineKind(StrEnum):
    """Classificação operacional de uma entrada do catálogo MAME."""

    SYSTEM = "system"
    DEVICE = "device"
    MECHANICAL = "mechanical"
    BIOS = "bios"
    NON_RUNNABLE = "non_runnable"


@dataclass(frozen=True, slots=True)
class ArcadeRom:
    """Representa uma ROM esperada por uma máquina."""

    name: str
    size: int | None = None
    crc: str | None = None
    sha1: str | None = None
    md5: str | None = None
    merge: str | None = None
    region: str | None = None
    status: RomStatus = RomStatus.UNKNOWN


@dataclass(frozen=True, slots=True)
class ArcadeDisplay:
    """Representa um display descrito pelo ListXML."""

    tag: str | None
    display_type: str | None
    width: int | None
    height: int | None
    refresh_hz: float | None
    rotate: str | None = None
    flipx: str | None = None


@dataclass(frozen=True, slots=True)
class ArcadeGame:
    """Identidade de uma máquina jogável ou de suporte do catálogo."""

    name: str
    description: str | None = None
    year: str | None = None
    manufacturer: str | None = None
    sourcefile: str | None = None
    cloneof: str | None = None
    romof: str | None = None
    machine_kind: MachineKind = MachineKind.SYSTEM
    runnable: bool = True
    roms: tuple[ArcadeRom, ...] = field(default_factory=tuple)
    displays: tuple[ArcadeDisplay, ...] = field(default_factory=tuple)

    @property
    def is_clone(self) -> bool:
        """Indica se a máquina é clone de outra entrada do catálogo."""
        return bool(self.cloneof)

    @property
    def is_parent(self) -> bool:
        """Indica se a máquina não referencia um parent diretamente."""
        return not self.cloneof

    @property
    def playable(self) -> bool:
        """Indica se a entrada pode ser considerada sistema executável."""
        return self.runnable and self.machine_kind is MachineKind.SYSTEM


@dataclass(frozen=True, slots=True)
class ArcadeSet:
    """Conjunto selecionado para construção/exportação."""

    name: str
    games: tuple[ArcadeGame, ...] = field(default_factory=tuple)

    @property
    def game_count(self) -> int:
        """Retorna a quantidade de jogos no conjunto."""
        return len(self.games)

    @property
    def rom_count(self) -> int:
        """Retorna a quantidade total de ROMs esperadas pelo conjunto."""
        return sum(len(game.roms) for game in self.games)

    def contains(self, name: str) -> bool:
        """Retorna se uma máquina pelo nome está presente no conjunto."""
        return any(game.name == name for game in self.games)


__all__ = [
    "ArcadeDisplay",
    "ArcadeGame",
    "ArcadeRom",
    "ArcadeSet",
    "MachineKind",
    "RomStatus",
]
