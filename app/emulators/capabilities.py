"""Capability descriptors used by the emulator configuration layer.

The layer intentionally describes verified configuration concepts rather than
inventing settings. GUI code consumes these descriptors without knowing how
a specific emulator stores its configuration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet


@dataclass(frozen=True, slots=True)
class EmulatorCapabilities:
    """Declares the configuration domains supported by an emulator."""

    emulator: str
    domains: FrozenSet[str] = field(default_factory=frozenset)
    features: FrozenSet[str] = field(default_factory=frozenset)

    def supports(self, feature: str) -> bool:
        """Return whether the emulator exposes a given feature."""
        return feature in self.features


MAME_CAPABILITIES = EmulatorCapabilities(
    emulator="mame",
    domains=frozenset({"general", "video", "audio", "input", "performance", "artwork", "paths", "plugins"}),
    features=frozenset({
        "video-backend", "bgfx", "hlsl", "glsl", "fullscreen", "windowed",
        "integer-scaling", "keep-aspect", "vsync", "sync-refresh", "frameskip",
        "throttle", "sound", "samples", "audio-latency", "mixer", "keyboard",
        "joystick", "mouse", "lightgun", "multikeyboard", "multimouse", "artwork",
        "plugins", "per-game-ini",
    }),
)

FLYCAST_CAPABILITIES = EmulatorCapabilities(
    emulator="flycast",
    domains=frozenset({"general", "video", "audio", "input", "performance", "arcade", "paths", "achievements"}),
    features=frozenset({
        "renderer", "fullscreen", "integer-scaling", "filtering", "texture-filtering",
        "texture-upscaling", "vsync", "widescreen", "framebuffer-effects", "dynarec",
        "sh4-clock", "threading", "audio", "audio-latency", "controller", "lightgun",
        "wheel", "force-feedback", "naomi", "naomi2", "atomiswave", "retroachievements",
        "achievements-hardcore",
    }),
)

SUPERMODEL_CAPABILITIES = EmulatorCapabilities(
    emulator="supermodel",
    domains=frozenset({"general", "video", "audio", "input", "force_feedback", "performance", "paths"}),
    features=frozenset({
        "fullscreen", "vsync", "resolution", "vertex-shader", "fragment-shader",
        "show-fps", "audio", "mpeg-audio", "music-volume", "sound-volume", "stereo-swap",
        "keyboard", "gamepad", "wheel", "pedal", "force-feedback", "save-state", "nvram",
    }),
)

FBNEO_CAPABILITIES = EmulatorCapabilities(
    emulator="fbneo",
    domains=frozenset({"general", "video", "audio", "input", "performance", "arcade", "paths", "achievements"}),
    features=frozenset({
        "fullscreen", "vsync", "integer-scaling", "aspect-ratio", "filtering", "shaders",
        "audio", "keyboard", "gamepad", "lightgun", "wheel", "frameskip", "save-state",
        "retroachievements", "libretro",
    }),
)

RETROARCH_CAPABILITIES = EmulatorCapabilities(
    emulator="retroarch",
    domains=frozenset({"general", "video", "audio", "input", "latency", "shaders", "paths", "cores"}),
    features=frozenset({
        "video-driver", "fullscreen", "vsync", "threaded-video", "hdr", "audio",
        "audio-latency", "audio-sync", "input", "joypad", "input-autodetect",
        "deadzone", "analog-sensitivity", "remapping", "shader", "shader-directory",
        "core-directory", "system-directory", "content-directory", "save-directory",
        "state-directory",
    }),
)

CAPABILITIES = {
    "mame": MAME_CAPABILITIES,
    "flycast": FLYCAST_CAPABILITIES,
    "supermodel": SUPERMODEL_CAPABILITIES,
    "fbneo": FBNEO_CAPABILITIES,
    "retroarch": RETROARCH_CAPABILITIES,
}


def get_capabilities(emulator: str) -> EmulatorCapabilities:
    """Return capabilities for an emulator, raising for unknown identifiers."""
    key = emulator.strip().lower()
    try:
        return CAPABILITIES[key]
    except KeyError as exc:
        raise ValueError(f"Emulador não suportado: {emulator}") from exc
