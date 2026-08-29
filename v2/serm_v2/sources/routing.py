"""Source routing rules shared by external system adapters."""
from __future__ import annotations

from enum import StrEnum


class SourceFamily(StrEnum):
    """Canonical source family responsible for a platform."""

    NO_INTRO = "no_intro"
    REDUMP = "redump"
    UNSUPPORTED = "unsupported"


class SystemSourceRouter:
    """Route LaunchBox platform names to the appropriate preservation source.

    The router is intentionally conservative: known optical-disc platforms go to
    Redump and are never presented as No-Intro candidates. Unknown platforms are
    left unsupported until an explicit source rule is added, preventing an
    incorrect No-Intro download from silently replacing a Redump source.
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
