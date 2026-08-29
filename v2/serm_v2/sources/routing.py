"""Source routing rules shared by external system adapters."""
from __future__ import annotations

from enum import StrEnum


class SourceFamily(StrEnum):
    """Canonical source family responsible for a platform."""

    NO_INTRO = "no_intro"
    REDUMP = "redump"
    UNSUPPORTED = "unsupported"


class SystemSourceRouter:
    """Route platform names to the appropriate preservation source.

    The rules are deliberately conservative. Known optical-disc platforms are
    owned by Redump and are never admitted to the No-Intro candidate list.
    Unknown platforms remain unsupported until an explicit rule is added.
    """

    _REDUMP_NAMES = frozenset(
        {
            "3DO",
            "Bandai Playdia",
            "Commodore Amiga CD32",
            "Dreamcast",
            "GameCube",
            "Jaguar CD",
            "Neo Geo CD",
            "Nintendo Wii",
            "Nintendo Wii U",
            "PC Engine CD",
            "PlayStation",
            "PlayStation 2",
            "PlayStation 3",
            "PlayStation 4",
            "PlayStation Portable",
            "PlayStation Vita",
            "Sega CD",
            "Sega Saturn",
            "TurboGrafx-CD",
        }
    )

    _NO_INTRO_NAMES = frozenset(
        {
            "Atari 2600",
            "Atari 5200",
            "Atari 7800",
            "Game Boy",
            "Game Boy Advance",
            "Game Boy Color",
            "Master System",
            "Mega Drive",
            "Nintendo 64",
            "Nintendo Entertainment System",
            "Nintendo DS",
            "Nintendo 3DS",
            "Super Nintendo Entertainment System",
            "Virtual Boy",
        }
    )

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().replace("-", " ").split())

    @staticmethod
    def _platform_tail(value: str) -> str:
        """Return the platform portion after a LaunchBox/DAT-o-MATIC vendor prefix."""
        normalized = SystemSourceRouter._normalize(value)
        return normalized.split(" ", 1)[-1] if " " in normalized else normalized

    def route(self, platform_name: str) -> SourceFamily:
        """Return the preservation source assigned to a LaunchBox platform."""
        normalized = self._normalize(platform_name)
        redump = {self._normalize(name) for name in self._REDUMP_NAMES}
        no_intro = {self._normalize(name) for name in self._NO_INTRO_NAMES}
        if normalized in redump:
            return SourceFamily.REDUMP
        if normalized in no_intro:
            return SourceFamily.NO_INTRO
        return SourceFamily.UNSUPPORTED

    def allows_no_intro(self, platform_name: str) -> bool:
        """Return whether a LaunchBox platform may participate in No-Intro matching."""
        return self.route(platform_name) is SourceFamily.NO_INTRO

    def is_redump_system(self, source_name: str) -> bool:
        """Return whether a DAT-o-MATIC system belongs to the Redump domain."""
        redump = {self._normalize(name) for name in self._REDUMP_NAMES}
        normalized = self._normalize(source_name)
        candidates = {normalized, self._platform_tail(source_name)}
        if " - " in source_name:
            candidates.add(self._normalize(source_name.rsplit(" - ", 1)[-1]))
        return any(candidate in redump or any(candidate.startswith(f"{name} ") for name in redump) for candidate in candidates)
