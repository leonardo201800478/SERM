"""Map canonical settings to physical emulator configuration keys.

The schema remains emulator-agnostic. This module is the only place where a
canonical GUI key is translated to a key stored by a specific emulator.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfigMapping:
    """Physical representation of one canonical configuration setting."""
    emulator: str
    canonical_key: str
    physical_key: str


# These mappings intentionally start with keys whose physical representation
# is stable. Unsupported/unknown mappings are not guessed: they remain absent.
_MAPPINGS: tuple[ConfigMapping, ...] = (
    ConfigMapping("mame", "fullscreen", "window"),
    ConfigMapping("mame", "vsync", "waitvsync"),
    ConfigMapping("mame", "sync_refresh", "syncrefresh"),
    ConfigMapping("mame", "keep_aspect", "keepaspect"),
    ConfigMapping("mame", "frameskip", "frameskip"),
    ConfigMapping("mame", "throttle", "throttle"),
    ConfigMapping("mame", "samplerate", "samplerate"),
    ConfigMapping("mame", "audio_latency", "audio_latency"),
    ConfigMapping("mame", "joystick", "joystick"),
    ConfigMapping("mame", "mouse", "mouse"),
    ConfigMapping("mame", "lightgun", "lightgun"),
    ConfigMapping("flycast", "fullscreen", "fullscreen"),
    ConfigMapping("flycast", "vsync", "vsync"),
    ConfigMapping("flycast", "audio_latency", "audio_latency"),
    ConfigMapping("flycast", "retroachievements", "retroachievements"),
    ConfigMapping("supermodel", "fullscreen", "FullScreen"),
    ConfigMapping("supermodel", "vsync", "VSync"),
    ConfigMapping("supermodel", "show_fps", "ShowFPS"),
    ConfigMapping("supermodel", "music_volume", "MusicVolume"),
    ConfigMapping("supermodel", "sound_volume", "SoundVolume"),
    ConfigMapping("supermodel", "stereo_swap", "StereoSwap"),
)

_INDEX = {(item.emulator, item.canonical_key): item for item in _MAPPINGS}


def get_mapping(emulator: str, canonical_key: str) -> ConfigMapping | None:
    """Return a physical mapping or ``None`` when no verified mapping exists."""
    return _INDEX.get((emulator.strip().lower(), canonical_key.strip()))


def physical_key(emulator: str, canonical_key: str) -> str | None:
    """Return the physical key for a canonical setting."""
    mapping = get_mapping(emulator, canonical_key)
    return mapping.physical_key if mapping else None
