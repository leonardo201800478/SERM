"""Runtime discovery for the five supported emulator installations.

A descoberta é conservadora: nunca inicia o emulador só para descobrir se ele
está instalado e não confunde versão desconhecida com instalação ausente.
"""
from __future__ import annotations

import platform
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RuntimeCapabilities:
    """Estado detectado e recursos utilizáveis de uma instalação."""

    emulator: str
    executable: Path | None
    version: str | None
    available: bool
    features: frozenset[str] = field(default_factory=frozenset)
    renderers: frozenset[str] = field(default_factory=frozenset)
    notes: tuple[str, ...] = ()
    version_source: str | None = None

    @property
    def installed(self) -> bool:
        """Indica se o executável configurado foi encontrado."""
        return self.executable is not None and self.available

    @property
    def version_known(self) -> bool:
        """Indica se uma versão local confiável foi detectada."""
        return bool(self.version)

    @property
    def installation_state(self) -> str:
        """Retorna o estado estável consumido pela GUI."""
        if not self.installed:
            return "not_installed"
        if not self.version_known:
            return "installed_unknown_version"
        return "installed"

    def supports(self, feature: str) -> bool:
        """Indica se o recurso está disponível nesta instalação."""
        return feature in self.features


_VERSION_RE = re.compile(r"(?i)(?:version\s*)?v?([0-9]+(?:\.[0-9]+)+(?:[-+._][0-9A-Za-z.-]+)?)")


def _hidden_flags() -> int:
    """Retorna flags Windows que impedem janelas de console."""
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if platform.system() == "Windows" else 0


def _resolve(path_or_name: str | Path | None, names: tuple[str, ...]) -> Path | None:
    """Resolve executável por arquivo, diretório configurado ou PATH."""
    candidates: list[Path] = []
    if path_or_name:
        configured = Path(path_or_name).expanduser()
        if configured.is_file():
            candidates.append(configured)
        elif configured.is_dir():
            candidates.extend(configured / name for name in names)
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
    """Executa somente uma consulta CLI documentada e não interativa."""
    try:
        result = subprocess.run([str(executable), *args], capture_output=True, text=True,
                                timeout=timeout, creationflags=_hidden_flags(), check=False,
                                cwd=str(executable.parent))
    except (OSError, subprocess.SubprocessError):
        return None
    text = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    return text or None


def _extract_version(text: str | None) -> str | None:
    """Extrai somente tokens de versão presentes na saída real."""
    if not text:
        return None
    for line in text.splitlines():
        match = _VERSION_RE.search(line)
        if match:
            return match.group(1)
    return None


def _windows_file_version(executable: Path) -> str | None:
    """Lê ProductVersion/FileVersion do PE sem executar o emulador."""
    if platform.system() != "Windows" or executable.suffix.lower() != ".exe":
        return None
    script = ("$p=(Get-Item -LiteralPath $args[0] -ErrorAction Stop).VersionInfo;"
              "if($p.ProductVersion){$p.ProductVersion}else{$p.FileVersion}")
    try:
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script, str(executable)],
                                capture_output=True, text=True, timeout=3,
                                creationflags=_hidden_flags(), check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return _extract_version((result.stdout or "").strip())


def _discover_version(executable: Path, emulator: str, command_probe: tuple[str, ...] | None = None) -> tuple[str | None, str | None]:
    """Obtém versão pela fonte menos intrusiva disponível."""
    version = _windows_file_version(executable)
    if version:
        return version, "pe-version-resource"
    if emulator == "mame" and command_probe:
        version = _extract_version(_run_probe(executable, command_probe))
        if version:
            return version, "mame-help"
    return None, None


def _discover(emulator: str, executable: Path | None, features: set[str],
              renderers: set[str] | None = None, command_probe: tuple[str, ...] | None = None) -> RuntimeCapabilities:
    """Cria estado de runtime sem falsos negativos por versão desconhecida."""
    if executable is None:
        return RuntimeCapabilities(emulator, None, None, False, notes=("Executável não encontrado.",))
    version, source = _discover_version(executable, emulator, command_probe)
    notes = () if version else ("Executável encontrado; versão local não determinada com segurança.",)
    return RuntimeCapabilities(emulator, executable, version, True, frozenset(features),
                                frozenset(renderers or ()), notes, source)


def discover_mame(path: str | Path | None = None) -> RuntimeCapabilities:
    """Descobre MAME por caminho configurado ou PATH."""
    exe = _resolve(path, ("mame.exe", "mame"))
    features = {"video-backend", "fullscreen", "windowed", "vsync", "sync-refresh", "keep-aspect", "bgfx", "hlsl", "glsl", "sound", "samples", "mixer", "audio-latency", "keyboard", "joystick", "mouse", "lightgun", "multikeyboard", "multimouse", "frameskip", "throttle", "artwork", "plugins", "per-game-ini"}
    return _discover("mame", exe, features, {"bgfx", "d3d", "opengl", "none"}, ("-help",))


def discover_flycast(path: str | Path | None = None) -> RuntimeCapabilities:
    """Descobre Flycast sem executar o emulador para versionamento."""
    exe = _resolve(path, ("flycast.exe", "flycast"))
    features = {"renderer", "fullscreen", "integer-scaling", "filtering", "texture-filtering", "texture-upscaling", "vsync", "widescreen", "dynarec", "sh4-clock", "threading", "audio", "audio-latency", "controller", "lightgun", "wheel", "force-feedback", "retroachievements", "achievements-hardcore", "naomi", "naomi2", "atomiswave"}
    return _discover("flycast", exe, features, {"opengl", "vulkan"})


def discover_supermodel(path: str | Path | None = None) -> RuntimeCapabilities:
    """Descobre Supermodel e os recursos conhecidos de Model 3."""
    exe = _resolve(path, ("supermodel.exe", "Supermodel.exe", "supermodel"))
    features = {"fullscreen", "vsync", "resolution", "vertex-shader", "fragment-shader", "show-fps", "audio", "mpeg-audio", "music-volume", "sound-volume", "stereo-swap", "keyboard", "gamepad", "wheel", "pedal", "force-feedback", "save-state", "nvram"}
    return _discover("supermodel", exe, features, {"opengl"})


def discover_fbneo(path: str | Path | None = None) -> RuntimeCapabilities:
    """Descobre FBNeo sem tentar switches de versão não documentados."""
    exe = _resolve(path, ("fbneo64.exe", "fbneo.exe", "fbneo64", "fbneo"))
    features = {"fullscreen", "vsync", "integer-scaling", "aspect-ratio", "filtering", "shaders", "audio", "keyboard", "gamepad", "lightgun", "wheel", "frameskip", "save-state", "retroachievements", "libretro"}
    return _discover("fbneo", exe, features)


def discover_retroarch(path: str | Path | None = None) -> RuntimeCapabilities:
    """Descobre RetroArch pela instalação local sem abrir a interface."""
    exe = _resolve(path, ("retroarch.exe", "retroarch"))
    features = {"video-driver", "fullscreen", "vsync", "threaded-video", "hdr", "audio", "audio-latency", "audio-sync", "input", "joypad", "input-autodetect", "deadzone", "analog-sensitivity", "remapping", "shader", "shader-directory", "core-directory", "system-directory", "content-directory", "save-directory", "state-directory"}
    return _discover("retroarch", exe, features, {"gl", "vulkan", "d3d11", "d3d12"})


def discover_all(paths: dict[str, str | Path | None] | None = None) -> dict[str, RuntimeCapabilities]:
    """Descobre os cinco emuladores de forma isolada e silenciosa."""
    paths = paths or {}
    detectors: tuple[tuple[str, Callable[[str | Path | None], RuntimeCapabilities]], ...] = (
        ("mame", discover_mame), ("flycast", discover_flycast),
        ("supermodel", discover_supermodel), ("fbneo", discover_fbneo),
        ("retroarch", discover_retroarch),
    )
    result: dict[str, RuntimeCapabilities] = {}
    for name, detector in detectors:
        try:
            result[name] = detector(paths.get(name))
        except Exception as exc:
            result[name] = RuntimeCapabilities(name, None, None, False,
                                                notes=(f"Falha isolada na detecção: {type(exc).__name__}.",))
    return result
