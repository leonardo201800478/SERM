"""Map canonical settings to physical emulator configuration keys.

The schema remains emulator-agnostic. This module is the only place where a
canonical GUI key is translated to a key stored by a specific emulator.

Mappings are deliberately limited to keys whose semantics are identical on
both sides. Settings requiring value transformation (for example MAME's
``window`` versus a canonical ``fullscreen`` boolean) are intentionally not
mapped here until a transformation-aware mapping is available.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfigMapping:
    """Physical representation of one canonical configuration setting."""

    emulator: str
    canonical_key: str
    physical_key: str


_MAPPINGS: tuple[ConfigMapping, ...] = (
    # MAME
    ConfigMapping("mame", "window", "window"),
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
    # Flycast
    ConfigMapping("flycast", "fullscreen", "fullscreen"),
    ConfigMapping("flycast", "vsync", "vsync"),
    ConfigMapping("flycast", "audio_latency", "audio_latency"),
    ConfigMapping("flycast", "retroachievements", "retroachievements"),
    # Supermodel
    ConfigMapping("supermodel", "fullscreen", "FullScreen"),
    ConfigMapping("supermodel", "vsync", "VSync"),
    ConfigMapping("supermodel", "show_fps", "ShowFPS"),
    ConfigMapping("supermodel", "music_volume", "MusicVolume"),
    ConfigMapping("supermodel", "sound_volume", "SoundVolume"),
    ConfigMapping("supermodel", "stereo_swap", "StereoSwap"),
    # RetroArch: native retroarch.cfg keys, not core .opt keys.
    ConfigMapping("retroarch", "fullscreen", "video_fullscreen"),
    ConfigMapping("retroarch", "vsync", "video_vsync"),
    ConfigMapping("retroarch", "video_threaded", "video_threaded"),
    ConfigMapping("retroarch", "audio_enable", "audio_enable"),
    ConfigMapping("retroarch", "audio_out_rate", "audio_out_rate"),
    ConfigMapping("retroarch", "audio_latency", "audio_latency"),
    ConfigMapping("retroarch", "input_joypad_driver", "input_joypad_driver"),
    ConfigMapping("retroarch", "input_autodetect_enable", "input_autodetect_enable"),
    ConfigMapping("retroarch", "video_shader", "video_shader"),
    ConfigMapping("retroarch", "video_shader_enable", "video_shader_enable"),
)

_INDEX = {(item.emulator, item.canonical_key): item for item in _MAPPINGS}


def get_mapping(emulator: str, canonical_key: str) -> ConfigMapping | None:
    """Return a physical mapping or ``None`` when no verified mapping exists."""
    return _INDEX.get((emulator.strip().lower(), canonical_key.strip()))


def physical_key(emulator: str, canonical_key: str) -> str | None:
    """Return the physical key for a canonical setting."""
    mapping = get_mapping(emulator, canonical_key)
    return mapping.physical_key if mapping else None
