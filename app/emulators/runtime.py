"""Runtime discovery for the supported emulator installations.

The runtime layer is intentionally conservative.  It must never start an
emulator merely to discover whether it is installed, and it must never mark an
installation as missing only because a version probe is unavailable.

Version discovery is emulator-specific:
- MAME: ``-help`` is an official, non-game command and prints the version.
- Supermodel: Windows executable metadata is preferred; the executable itself
  is never launched just to obtain a version.
- FBNeo: Windows executable metadata is preferred.  FBNeo's documented CLI
  does not provide a generic ``-version`` command, so an unsupported probe is
  deliberately not attempted.
- Flycast: Windows executable metadata is preferred; no generic probe is
  required for installation detection.

A missing version therefore means ``installed_unknown_version``, not
``not_installed``.  This distinction is important for the Home page and for the
update/download workflow.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, FrozenSet


@dataclass(frozen=True, slots=True)
class RuntimeCapabilities:
    """Runtime state and usable features for one emulator installation."""

    emulator: str
    executable: Path | None
    version: str | None
    available: bool
    features: FrozenSet[str] = field(default_factory=frozenset)
    renderers: FrozenSet[str] = field(default_factory=frozenset)
    notes: tuple[str, ...] = ()
    version_source: str | None = None

    @property
    def installed(self) -> bool:
        """Return ``True`` when the configured emulator executable exists."""
        return self.executable is not None and self.available

    @property
    def version_known(self) -> bool:
        """Return whether a trustworthy local version was detected."""
        return bool(self.version)

    @property
    def installation_state(self) -> str:
        """Return the stable state consumed by the Home/update GUI."""
        if not self.installed:
            return "not_installed"
        if not self.version_known:
            return "installed_unknown_version"
        return "installed"

    def supports(self, feature: str) -> bool:
        """Return whether a feature is available for this runtime."""
        return feature in self.features


_VERSION_RE = re.compile(r"(?i)(?:version\s*)?v?([0-9]+(?:\.[0-9]+)+(?:[-+._][0-9A-Za-z.-]+)?)")


def _hidden_flags() -> int:
    """Return Windows flags that prevent console windows during probes."""
    if platform.system() != "Windows":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _resolve(path_or_name: str | Path | None, names: tuple[str, ...]) -> Path | None:
    """Resolve an executable from a configured file, configured directory, or PATH."""
    candidates: list[Path] = []

    if path_or_name:
        configured = Path(path_or_name).expanduser()
        if configured.is_file():
            candidates.append(configured)
        elif configured.is_dir():
            for name in names:
                candidates.append(configured / name)

    for name in names:
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))

    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    return None


def _run_probe(executable: Path, args: tuple[str, ...], timeout: float = 3.0) -> str | None:
    """Run a documented, non-game CLI probe without creating a console window."""
    try:
        result = subprocess.run(
            [str(executable), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=_hidden_flags(),
            check=False,
            cwd=str(executable.parent),
        )
    except (OSError, subprocess.SubprocessError):
        return None

    text = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    return text or None


def _extract_version(text: str | None) -> str | None:
    """Extract a version token from command output without inventing one."""
    if not text:
        return None
    for line in text.splitlines():
        match = _VERSION_RE.search(line)
        if match:
            return match.group(1)
    return None


def _windows_file_version(executable: Path) -> str | None:
    """Read the PE ProductVersion/FileVersion using Windows PowerShell metadata."""
    if platform.system() != "Windows" or executable.suffix.lower() != ".exe":
        return None

    # PowerShell is used only for Windows' native PE version resource.  It does
    # not execute the emulator and CREATE_NO_WINDOW keeps this operation silent.
    script = (
        "$p=(Get-Item -LiteralPath $args[0] -ErrorAction Stop).VersionInfo;"
        "if($p.ProductVersion){$p.ProductVersion}else{$p.FileVersion}"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script, str(executable)],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=_hidden_flags(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    value = (result.stdout or "").strip()
    return _extract_version(value)


def _discover_version(
    executable: Path,
    emulator: str,
    command_probe: tuple[str, ...] | None = None,
) -> tuple[str | None, str | None]:
    """Discover a local version using the safest source available."""
    version = _windows_file_version(executable)
    if version:
        return version, "pe-version-resource"

    # Only MAME has a documented probe in the official command-line manual that
    # is safe for this purpose.  Other emulators are intentionally not probed
    # with guessed flags such as '-version'.
    if emulator == "mame" and command_probe:
        version = _extract_version(_run_probe(executable, command_probe))
        if version:
            return version, "mame-help"

    return None, None


def _discover(
    emulator: str,
    executable: Path | None,
    base_features: set[str],
    renderers: set[str] | None = None,
    command_probe: tuple[str, ...] | None = None,
) -> RuntimeCapabilities:
    """Build runtime state without treating an unknown version as absence."""
    if executable is None:
        return RuntimeCapabilities(
            emulator=emulator,
            executable=None,
            version=None,
            available=False,
            features=frozenset(),
            renderers=frozenset(),
            notes=("Executável não encontrado no diretório configurado nem no PATH.",),
        )

    version, source = _discover_version(executable, emulator, command_probe)
    notes: list[str] = []
    if version is None:
        notes.append("Executável encontrado; versão local não pôde ser determinada com segurança.")

    return RuntimeCapabilities(
        emulator=emulator,
        executable=executable,
        version=version,
        available=True,
        features=frozenset(base_features),
        renderers=frozenset(renderers or ()),
        notes=tuple(notes),
        version_source=source,
    )


def discover_mame(path: str | Path | None = None) -> RuntimeCapabilities:
    """Discover MAME from a file, installation directory, or PATH."""
    exe = _resolve(path, ("mame.exe", "mame"))
    features = {
        "video-backend", "fullscreen", "windowed", "vsync", "sync-refresh", "keep-aspect",
        "bgfx", "hlsl", "glsl", "sound", "samples", "mixer", "audio-latency", "keyboard",
        "joystick", "mouse", "lightgun", "multikeyboard", "multimouse", "frameskip", "throttle",
        "artwork", "plugins", "per-game-ini",
    }
    return _discover("mame", exe, features, {"bgfx", "d3d", "opengl", "none"}, ("-help",))


def discover_flycast(path: str | Path | None = None) -> RuntimeCapabilities:
    """Discover Flycast without executing the emulator during version checks."""
    exe = _resolve(path, ("flycast.exe", "flycast"))
    features = {
        "renderer", "fullscreen", "integer-scaling", "filtering", "texture-filtering",
        "texture-upscaling", "vsync", "widescreen", "dynarec", "sh4-clock", "threading",
        "audio", "audio-latency", "controller", "lightgun", "wheel", "force-feedback",
        "retroachievements", "achievements-hardcore", "naomi", "naomi2", "atomiswave",
    }
    return _discover("flycast", exe, features, {"opengl", "vulkan"})


def discover_supermodel(path: str | Path | None = None) -> RuntimeCapabilities:
    """Discover Supermodel and its native Model 3 configuration surface."""
    exe = _resolve(path, ("supermodel.exe", "Supermodel.exe", "supermodel"))
    features = {
        "fullscreen", "vsync", "resolution", "vertex-shader", "fragment-shader", "show-fps",
        "audio", "mpeg-audio", "music-volume", "sound-volume", "stereo-swap", "keyboard",
        "gamepad", "wheel", "pedal", "force-feedback", "save-state", "nvram",
    }
    return _discover("supermodel", exe, features, {"opengl"})


def discover_fbneo(path: str | Path | None = None) -> RuntimeCapabilities:
    """Discover FBNeo without calling undocumented version switches."""
    exe = _resolve(path, ("fbneo.exe", "fbneo"))
    features = {
        "fullscreen", "vsync", "integer-scaling", "aspect-ratio", "filtering", "shaders",
        "audio", "keyboard", "gamepad", "lightgun", "wheel", "frameskip", "save-state",
        "retroachievements", "libretro",
    }
    return _discover("fbneo", exe, features, set())


def discover_all(paths: dict[str, str | Path | None] | None = None) -> dict[str, RuntimeCapabilities]:
    """Discover all supported emulators silently and independently."""
    paths = paths or {}
    detectors: tuple[tuple[str, Callable[[str | Path | None], RuntimeCapabilities]], ...] = (
        ("mame", discover_mame),
        ("flycast", discover_flycast),
        ("supermodel", discover_supermodel),
        ("fbneo", discover_fbneo),
    )
    result: dict[str, RuntimeCapabilities] = {}
    for name, detector in detectors:
        try:
            result[name] = detector(paths.get(name))
        except Exception as exc:  # discovery must never prevent application startup
            result[name] = RuntimeCapabilities(
                emulator=name,
                executable=None,
                version=None,
                available=False,
                notes=(f"Falha isolada na detecção: {type(exc).__name__}.",),
            )
    return result
