"""Audio settings for all registered emulators."""

from __future__ import annotations

from .emulator_settings_page import EmulatorSettingsPage


class SoundSettingsPage(EmulatorSettingsPage):
    """Expose supported emulator audio settings, without SERM UI audio controls."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent, section="audio")


__all__ = ["SoundSettingsPage"]
