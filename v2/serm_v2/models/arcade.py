"""Modelos de domínio agnósticos para o Arcade Studio."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum


class ArcadePlatform(StrEnum):
    """Plataformas de arcade suportadas ou previstas pelo Studio."""

    MAME = "mame"
    SUPERMODEL = "supermodel"
    FLYCAST_ARCADE = "flycast_arcade"
    FBNEO = "fbneo"
    SEGA_MODEL_2 = "sega_model_2"
    SEGA_MODEL_1 = "sega_model_1"
    NEOGEO_64 = "neogeo_64"


class ArcadeSetType(StrEnum):
    """Estratégias de organização física de um conjunto."""

    SPLIT = "split"
    NON_MERGED = "non_merged"
    FULL_MERGED = "full_merged"


class RomStatus(StrEnum):
    """Estado físico da ROM em relação à definição do catálogo."""

    OK = "ok"
    REPAIRABLE = "repairable"
    INCOMPLETE = "incomplete"
    MISSING = "missing"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class PlayabilityStatus(StrEnum):
    """Estado de execução do título no alvo avaliado."""

    FULLY_PLAYABLE = "fully_playable"
    FUNCTIONAL = "functional"
    PARTIALLY_PLAYABLE = "partially_playable"
    IN_DEVELOPMENT = "in_development"
    PLAYABLE_ELSEWHERE = "playable_elsewhere"
    UNPLAYABLE = "unplayable"
    UNKNOWN = "unknown"


@dataclass(slots=True, frozen=True)
class ArcadeRom:
    """Uma ROM/elemento de set catalogado."""

    machine_name: str
    display_name: str
    platform: ArcadePlatform
    parent_name: str | None = None
    rom_status: RomStatus = RomStatus.UNKNOWN
    playability: PlayabilityStatus = PlayabilityStatus.UNKNOWN
    icon_path: str | None = None
    is_bios: bool = False
    is_device: bool = False
    has_chd: bool = False
    working: bool | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def is_clone(self) -> bool:
        return bool(self.parent_name)


@dataclass(slots=True, frozen=True)
class ArcadeDisk:
    """Um disco CHD catalogado pelo MAME.

    Os hashes representam o conteúdo lógico do disco definido pelo MAME, não o
    hash bruto do arquivo ``.chd``. O SERM deve comparar esses hashes com a
    identidade lógica extraída do CHD durante o inventário físico.
    """

    name: str
    sha1: str | None = None
    md5: str | None = None
    merge: str | None = None
    region: str | None = None
    index: str | None = None
    writable: str | None = None
    status: str | None = None
    optional: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ArcadeGame:
    """Representação de um título lógico no catálogo."""

    machine_name: str
    display_name: str
    platform: ArcadePlatform
    parent_name: str | None = None
    category: str | None = None
    subcategory: str | None = None
    roms: tuple[ArcadeRom, ...] = ()
    disks: tuple[ArcadeDisk, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def is_clone(self) -> bool:
        return bool(self.parent_name)

    @property
    def rom_status(self) -> RomStatus:
        """Consolida o pior estado físico entre os componentes do título."""

        statuses = {rom.rom_status for rom in self.roms}
        if not statuses:
            return RomStatus.UNKNOWN
        priority = (
            RomStatus.INVALID,
            RomStatus.MISSING,
            RomStatus.INCOMPLETE,
            RomStatus.REPAIRABLE,
            RomStatus.OK,
            RomStatus.UNKNOWN,
        )
        for status in priority:
            if status in statuses:
                return status
        return RomStatus.UNKNOWN


@dataclass(slots=True)
class ArcadeSet:
    """Set lógico que será posteriormente materializado pelo Set Builder."""

    name: str
    platform: ArcadePlatform
    set_type: ArcadeSetType = ArcadeSetType.SPLIT
    games: list[ArcadeGame] = field(default_factory=list)
    include_bios: bool = False
    include_devices: bool = False
    include_chd: bool = True
    metadata: dict[str, object] = field(default_factory=dict)

    def add_games(self, games: Iterable[ArcadeGame]) -> None:
        self.games.extend(games)

    @property
    def game_count(self) -> int:
        return len(self.games)


__all__ = [
    "ArcadeDisk",
    "ArcadeGame",
    "ArcadePlatform",
    "ArcadeRom",
    "ArcadeSet",
    "ArcadeSetType",
    "PlayabilityStatus",
    "RomStatus",
]
