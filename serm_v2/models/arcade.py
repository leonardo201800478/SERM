"""Modelos de domínio agnósticos para o Arcade Studio."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum


class ArcadePlatform(StrEnum):
    MAME = "mame"
    SUPERMODEL = "supermodel"
    FLYCAST_ARCADE = "flycast_arcade"
    FBNEO = "fbneo"
    SEGA_MODEL_2 = "sega_model_2"
    SEGA_MODEL_1 = "sega_model_1"
    NEOGEO_64 = "neogeo_64"


class ArcadeSetType(StrEnum):
    SPLIT = "split"
    NON_MERGED = "non_merged"
    FULL_MERGED = "full_merged"


class RomStatus(StrEnum):
    OK = "ok"
    REPAIRABLE = "repairable"
    INCOMPLETE = "incomplete"
    MISSING = "missing"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class PlayabilityStatus(StrEnum):
    FULLY_PLAYABLE = "fully_playable"
    FUNCTIONAL = "functional"
    PARTIALLY_PLAYABLE = "partially_playable"
    IN_DEVELOPMENT = "in_development"
    PLAYABLE_ELSEWHERE = "playable_elsewhere"
    UNPLAYABLE = "unplayable"
    UNKNOWN = "unknown"


@dataclass(slots=True, frozen=True)
class ArcadeRom:
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
    def is_bios(self) -> bool:
        return self._metadata_flag("is_bios", "bios")

    @property
    def is_device(self) -> bool:
        return self._metadata_flag("is_device", "device")

    @property
    def working(self) -> bool | None:
        value = self.metadata.get("working")
        if value is None:
            value = self.metadata.get("runnable")
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        normalized = str(value).strip().casefold()
        if normalized in {"yes", "true", "1", "working", "good"}:
            return True
        if normalized in {"no", "false", "0", "not working", "bad"}:
            return False
        return None

    @property
    def playability(self) -> PlayabilityStatus:
        """Estado de jogabilidade normalizado para o motor de filtros V2."""
        value = self.metadata.get("playability") or self.metadata.get("playability_status")
        if isinstance(value, PlayabilityStatus):
            return value
        if value is None:
            return PlayabilityStatus.UNKNOWN
        try:
            return PlayabilityStatus(str(value))
        except ValueError:
            return PlayabilityStatus.UNKNOWN

    def _metadata_flag(self, *keys: str) -> bool:
        for key in keys:
            if key in self.metadata:
                value = self.metadata[key]
                if isinstance(value, bool):
                    return value
                if str(value).strip().casefold() in {"yes", "true", "1"}:
                    return True
                if str(value).strip().casefold() in {"no", "false", "0"}:
                    return False
        return False

    @property
    def rom_status(self) -> RomStatus:
        statuses = {rom.rom_status for rom in self.roms}
        if not statuses:
            return RomStatus.UNKNOWN
        priority = (RomStatus.INVALID, RomStatus.MISSING, RomStatus.INCOMPLETE, RomStatus.REPAIRABLE, RomStatus.OK, RomStatus.UNKNOWN)
        for status in priority:
            if status in statuses:
                return status
        return RomStatus.UNKNOWN


@dataclass(slots=True)
class ArcadeSet:
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


__all__ = ["ArcadeDisk", "ArcadeGame", "ArcadePlatform", "ArcadeRom", "ArcadeSet", "ArcadeSetType", "PlayabilityStatus", "RomStatus"]
