"""Layer-2 runtime capability discovery.

Layer 1 defines stable configuration concepts. Layer 2 inspects the installed
emulator and host environment so the GUI can hide options that cannot actually
be used. Discovery is best-effort and never blocks application startup.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import FrozenSet


@dataclass(frozen=True, slots=True)
class RuntimeCapabilities:
    """Capabilities detected for one installed emulator executable."""

    emulator: str
    executable: Path | None
    version: str | None
    available: bool
    features: FrozenSet[str] = field(default_factory=frozenset)
    renderers: FrozenSet[str] = field(default_factory=frozenset)
    notes: tuple[str, ...] = ()

    def supports(self, feature: str) -> bool:
        """Return whether a feature is currently available at runtime."""
        return feature in self.features


def _run_version(executable: Path) -> str | None:
    """Read an executable version without displaying a console or popup."""
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if platform.system() == "Windows" else 0
        result = subprocess.run(
            [str(executable), "-version"],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=flags,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = (result.stdout or result.stderr).strip()
    return text.splitlines()[0].strip() if text else None


def _resolve(path_or_name: str | Path | None, names: tuple[str, ...]) -> Path | None:
    """Resolve a configured executable or search PATH without raising errors."""
    if path_or_name:
        candidate = Path(path_or_name)
        if candidate.is_file():
            return candidate
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def _discover(
    emulator: str,
    executable: Path | None,
    base_features: set[str],
    renderers: set[str] | None = None,
) -> RuntimeCapabilities:
    """Build a runtime capability object from a resolved executable."""
    if executable is None:
        return RuntimeCapabilities(emulator, None, None, False, frozenset(), frozenset(), ("Executável não encontrado.",))
    version = _run_version(executable)
    return RuntimeCapabilities(
        emulator=emulator,
        executable=executable,
        version=version,
        available=True,
        features=frozenset(base_features),
        renderers=frozenset(renderers or ()),
    )


def discover_mame(path: str | Path | None = None) -> RuntimeCapabilities:
    """Discover MAME and expose the configuration domains implemented by it."""
    exe = _resolve(path, ("mame.exe", "mame"))
    features = {
        "video-backend", "fullscreen", "windowed", "vsync", "sync-refresh", "keep-aspect",
        "bgfx", "hlsl", "glsl", "sound", "samples", "mixer", "audio-latency", "keyboard",
        "joystick", "mouse", "lightgun", "multikeyboard", "multimouse", "frameskip", "throttle",
        "artwork", "plugins", "per-game-ini",
    }
    return _discover("mame", exe, features, {"bgfx", "d3d", "opengl", "none"})


def discover_flycast(path: str | Path | None = None) -> RuntimeCapabilities:
    """Discover Flycast and its common standalone configuration capabilities."""
    exe = _resolve(path, ("flycast.exe", "flycast"))
    features = {
        "renderer", "fullscreen", "integer-scaling", "filtering", "texture-filtering",
        "texture-upscaling", "vsync", "widescreen", "dynarec", "sh4-clock", "threading",
        "audio", "audio-latency", "controller", "lightgun", "wheel", "force-feedback",
        "retroachievements", "achievements-hardcore", "naomi", "naomi2", "atomiswave",
    }
    return _discover("flycast", exe, features, {"opengl", "vulkan"})


def discover_supermodel(path: str | Path | None = None) -> RuntimeCapabilities:
    """Discover Supermodel and expose its native Model 3 configuration surface."""
    exe = _resolve(path, ("supermodel.exe", "Supermodel.exe", "supermodel"))
    features = {
        "fullscreen", "vsync", "resolution", "vertex-shader", "fragment-shader", "show-fps",
        "audio", "mpeg-audio", "music-volume", "sound-volume", "stereo-swap", "keyboard",
        "gamepad", "wheel", "pedal", "force-feedback", "save-state", "nvram",
    }
    return _discover("supermodel", exe, features, {"opengl"})


def discover_fbneo(path: str | Path | None = None) -> RuntimeCapabilities:
    """Discover FBNeo executable/core and expose the common arcade controls."""
    exe = _resolve(path, ("fbneo.exe", "fbneo"))
    features = {
        "fullscreen", "vsync", "integer-scaling", "aspect-ratio", "filtering", "shaders",
        "audio", "keyboard", "gamepad", "lightgun", "wheel", "frameskip", "save-state",
        "retroachievements", "libretro",
    }
    return _discover("fbneo", exe, features, set())


def discover_all(paths: dict[str, str | Path | None] | None = None) -> dict[str, RuntimeCapabilities]:
    """Discover all supported emulators silently and return their runtime state."""
    paths = paths or {}
    return {
        "mame": discover_mame(paths.get("mame")),
        "flycast": discover_flycast(paths.get("flycast")),
        "supermodel": discover_supermodel(paths.get("supermodel")),
        "fbneo": discover_fbneo(paths.get("fbneo")),
    }
