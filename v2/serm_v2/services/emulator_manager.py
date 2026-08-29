"""Functional emulator installation and RetroArch core management for SERM V2."""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EmulatorStatus:
    """Local state of one supported standalone emulator."""

    key: str
    label: str
    executable: Path | None
    root: Path | None
    version: str | None
    state: str


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Result of a standalone emulator installation."""

    emulator: str
    version: str
    executable: Path
    archive: str


@dataclass(frozen=True, slots=True)
class CoreInfo:
    """RetroArch libretro core published by the official buildbot."""

    filename: str
    core_name: str


class EmulatorManager:
    """Discover, install and update the four standalone emulators used by Home."""

    REPOSITORIES = {
        "mame": "mamedev/mame",
        "flycast": "flyinghead/flycast",
        "supermodel": "trzy/supermodel",
        "fbneo": "finalburnneo/FBNeo",
    }
    LABELS = {
        "mame": "MAME",
        "flycast": "Flycast",
        "supermodel": "Supermodel",
        "fbneo": "FBNeo",
    }
    EXECUTABLES = {
        "mame": "mame.exe",
        "flycast": "flycast.exe",
        "supermodel": "Supermodel.exe",
        "fbneo": "fbneo.exe",
    }

    def __init__(self, roots: dict[str, Path | None] | None = None) -> None:
        """Initialize the manager with optional user-configured installation roots."""
        self.roots = {
            key: Path(value).expanduser() if value else None
            for key, value in (roots or {}).items()
        }

    @staticmethod
    def find_7zip() -> Path | None:
        """Locate the command-line 7-Zip executable without launching the GUI."""
        for name in ("7z.exe", "7zz.exe", "7za.exe"):
            found = shutil.which(name)
            if found:
                return Path(found)
        candidates = (
            Path(r"C:\Program Files\7-Zip\7z.exe"),
            Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
            Path.home() / "AppData" / "Local" / "7-Zip" / "7z.exe",
        )
        return next((path for path in candidates if path.is_file()), None)

    def discover(self) -> dict[str, EmulatorStatus]:
        """Detect configured executables and common Windows installation locations."""
        result: dict[str, EmulatorStatus] = {}
        for key, label in self.LABELS.items():
            root = self.roots.get(key)
            executable = self._find_executable(key, root)
            if executable:
                root = executable.parent
            version = self._read_version(key, root, executable)
            state = "ready" if executable else "configured" if root else "not_found"
            result[key] = EmulatorStatus(
                key,
                label,
                executable,
                root,
                version,
                state,
            )
            logger.info(
                "[EMULATOR][DISCOVERY] %s state=%s exe=%s root=%s version=%s",
                key,
                state,
                executable,
                root,
                version,
            )
        return result

    def install(
        self,
        key: str,
        destination: Path,
        *,
        nightly: bool = False,
        progress=None,
        log=None,
    ) -> DownloadResult:
        """Download the official Windows x64 release, extract it and validate the executable."""
        key = key.casefold()
        if key not in self.REPOSITORIES:
            raise ValueError(f"Emulador não suportado: {key}")
        destination = Path(destination).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        release = self._release(key, nightly=nightly)
        assets = release.get("assets") or []
        asset = self._select_asset(key, assets)
        if not asset:
            raise RuntimeError(f"Nenhum pacote Windows x64 encontrado para {key}.")
        version = str(release.get("tag_name") or release.get("name") or "unknown")
        self._log(log, f"RELEASE | {key} | versão={version} | asset={asset['name']}")
        with tempfile.TemporaryDirectory(prefix="serm-emu-") as temp_name:
            temp = Path(temp_name)
            archive = temp / str(asset["name"])
            self._download(
                str(asset["browser_download_url"]),
                archive,
                int(asset.get("size") or 0),
                progress,
                log,
            )
            extracted = temp / "extracted"
            extracted.mkdir()
            self._extract(archive, extracted, log)
            self._merge(extracted, destination)
        executable = self._find_executable(key, destination)
        if executable is None:
            raise RuntimeError(
                f"Instalação concluída, mas {self.EXECUTABLES[key]} não foi encontrado em {destination}."
            )
        logger.info(
            "[EMULATOR][INSTALL] concluído %s version=%s executable=%s",
            key,
            version,
            executable,
        )
        return DownloadResult(key, version, executable, str(asset["name"]))

    def _release(self, key: str, *, nightly: bool) -> dict[str, Any]:
        """Read the current official GitHub release metadata."""
        repo = self.REPOSITORIES[key]
        url = (
            f"https://api.github.com/repos/{repo}/releases/tags/latest"
            if nightly and key == "fbneo"
            else f"https://api.github.com/repos/{repo}/releases/latest"
        )
        return self._json(url)

    @staticmethod
    def _json(url: str) -> dict[str, Any]:
        """Fetch a public JSON object with a stable User-Agent."""
        request = Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "SERM/2.0",
            },
        )
        with urlopen(request, timeout=30) as response:
            value = json.loads(response.read().decode("utf-8"))
        if not isinstance(value, dict):
            raise RuntimeError("Resposta JSON inesperada.")
        return value

    @classmethod
    def _select_asset(
        cls,
        key: str,
        assets: list[object],
    ) -> dict[str, Any] | None:
        """Select the best Windows x64 release asset using the V1 strategy."""
        candidates: list[tuple[int, dict[str, Any]]] = []
        for raw in assets:
            if not isinstance(raw, dict) or not raw.get("browser_download_url"):
                continue
            name = str(raw.get("name", "")).casefold()
            score = 0
            if any(
                token in name
                for token in ("windows", "win64", "win-x64", "win_x64", "mingw")
            ):
                score += 50
            if any(token in name for token in ("x64", "x86_64", "amd64", "64bit", "64-bit")):
                score += 35
            if any(
                token in name
                for token in (
                    "linux",
                    "ubuntu",
                    "macos",
                    "osx",
                    "android",
                    "ios",
                    "arm64",
                    "aarch64",
                    "win32",
                    "i386",
                    "source",
                    "src",
                )
            ):
                score -= 100
            if name.endswith(".zip"):
                score += 20
            elif name.endswith((".7z", ".7zip")):
                score += 10
            elif name.endswith(".exe"):
                score += 15
            if key == "mame" and re.search(r"_x64\.exe$", name):
                score += 140
            if key == "flycast" and "flycast-win64" in name:
                score += 150
            if key == "supermodel" and "supermodel" in name and "win" in name:
                score += 140
            if key == "fbneo" and name == "windows-x86_64.zip":
                score += 180
            if score >= 70:
                candidates.append((score, raw))
        candidates.sort(
            key=lambda item: (item[0], int(item[1].get("size") or 0)),
            reverse=True,
        )
        return candidates[0][1] if candidates else None

    @staticmethod
    def _download(
        url: str,
        target: Path,
        expected: int,
        progress=None,
        log=None,
    ) -> None:
        """Download an archive to a temporary file with progress and no execution."""
        request = Request(
            url,
            headers={"User-Agent": "SERM/2.0", "Accept-Encoding": "identity"},
        )
        received = 0
        with urlopen(request, timeout=120) as response, target.open("wb") as output:
            total = int(response.headers.get("Content-Length") or expected or 0)
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                received += len(chunk)
                if progress:
                    progress(received, total)
        if received <= 0:
            raise RuntimeError("Download retornou zero bytes.")
        logger.info(
            "[EMULATOR][DOWNLOAD] recebido=%d esperado=%d url=%s",
            received,
            total,
            url,
        )
        if log:
            log(f"DOWNLOAD | recebido={received:,} bytes | esperado={total:,} bytes")

    @classmethod
    def _extract(cls, archive: Path, destination: Path, log=None) -> None:
        """Extract ZIP internally or invoke local 7-Zip silently for 7z/SFX packages."""
        if archive.suffix.casefold() == ".zip":
            with zipfile.ZipFile(archive) as zf:
                base = destination.resolve()
                for member in zf.infolist():
                    target = (destination / member.filename).resolve()
                    if target != base and base not in target.parents:
                        raise RuntimeError("Pacote contém caminho de extração inseguro.")
                zf.extractall(destination)
            return
        seven_zip = cls.find_7zip()
        if seven_zip is None:
            raise RuntimeError("7z.exe não foi encontrado. Instale o 7-Zip para extrair este pacote.")
        command = [str(seven_zip), "x", "-y", f"-o{destination}", str(archive)]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            creationflags=creationflags,
            timeout=300,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"7-Zip falhou ({result.returncode}): "
                f"{(result.stderr or result.stdout).strip()}"
            )
        if log:
            log(f"7-ZIP | extração concluída | {archive.name}")

    @staticmethod
    def _merge(source: Path, destination: Path) -> None:
        """Merge extracted files into the configured emulator directory."""
        for item in source.iterdir():
            target = destination / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)

    def _find_executable(self, key: str, root: Path | None) -> Path | None:
        """Find the expected executable in the configured root or common Windows paths."""
        name = self.EXECUTABLES[key]
        candidates: list[Path] = []
        if root:
            candidates.extend((root / name, root / "bin" / name))
        for base in (
            Path.home() / "Documents",
            Path.home() / "Games",
            Path.home() / "Emulators",
            Path("C:/Emulators"),
        ):
            candidates.extend((base / self.LABELS[key] / name, base / key / name))
        candidates.append(Path(name))
        return next((path.resolve() for path in candidates if path.is_file()), None)

    @staticmethod
    def _read_version(
        key: str,
        root: Path | None,
        executable: Path | None,
    ) -> str | None:
        """Read a local version marker or the MAME executable version."""
        if root:
            for filename in (".serm-version", "VERSION", "version.txt", "build.txt"):
                path = root / filename
                if path.is_file():
                    try:
                        text = path.read_text(encoding="utf-8", errors="ignore").strip()
                    except OSError:
                        continue
                    if text:
                        return text.splitlines()[0].strip()
        if key == "mame" and executable:
            try:
                result = subprocess.run(
                    [str(executable), "-version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                first = (result.stdout or result.stderr).splitlines()
                if first:
                    match = re.search(r"MAME[: ]+([0-9.]+)", first[0], re.IGNORECASE)
                    return match.group(1) if match else first[0].strip()
            except (OSError, subprocess.SubprocessError):
                pass
        return None

    @staticmethod
    def _log(callback, message: str) -> None:
        """Send a diagnostic message to the logger and optional GUI callback."""
        logger.info("[EMULATOR] %s", message)
        if callback:
            callback(message)


class RetroArchManager:
    """Manage RetroArch Windows x64 and official libretro cores from Buildbot."""

    BUILDROOT = "https://buildbot.libretro.com/nightly/windows/x86_64/latest"
    RETROARCH_ARCHIVE = "https://buildbot.libretro.com/nightly/windows/x86_64/RetroArch.7z"
    RETROARCH_SETUP = "https://buildbot.libretro.com/nightly/windows/x86_64/RetroArch-Win64-setup.exe"

    def __init__(self, root: Path | None = None) -> None:
        """Initialize with an optional configured RetroArch directory."""
        self.root = Path(root).expanduser() if root else None

    def discover(self) -> tuple[Path | None, Path | None, Path | None]:
        """Find RetroArch executable, installation root and cores directory."""
        candidates = []
        if self.root:
            candidates.append(self.root / "retroarch.exe")
        candidates.extend(
            (
                Path.home() / "RetroArch-Win64" / "retroarch.exe",
                Path("C:/RetroArch/retroarch.exe"),
            )
        )
        executable = next((path.resolve() for path in candidates if path.is_file()), None)
        root = executable.parent if executable else self.root
        cores = root / "cores" if root else None
        return executable, root, cores

    def list_cores(self) -> tuple[CoreInfo, ...]:
        """Read the official Buildbot directory and return available Windows cores."""
        request = Request(self.BUILDROOT + "/", headers={"User-Agent": "SERM/2.0"})
        with urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8", errors="replace")
        names = sorted(
            set(
                re.findall(
                    r'href=[\"\']([^\"\']+_libretro\.dll\.zip)[\"\']',
                    html,
                    re.IGNORECASE,
                )
            )
        )
        return tuple(
            CoreInfo(name, name.removesuffix("_libretro.dll.zip")) for name in names
        )

    def install_core(self, filename: str, destination: Path, progress=None) -> Path:
        """Download one official core ZIP and extract it into RetroArch/cores."""
        destination.mkdir(parents=True, exist_ok=True)
        url = f"{self.BUILDROOT}/{filename}"
        with tempfile.TemporaryDirectory(prefix="serm-core-") as temp_name:
            archive = Path(temp_name) / filename
            EmulatorManager._download(url, archive, 0, progress)
            with zipfile.ZipFile(archive) as zf:
                dlls = [
                    member
                    for member in zf.infolist()
                    if member.filename.lower().endswith(".dll")
                ]
                if not dlls:
                    raise RuntimeError(f"Core sem DLL: {filename}")
                for member in dlls:
                    target = (destination / Path(member.filename).name).resolve()
                    if destination.resolve() not in target.parents:
                        raise RuntimeError("Caminho inseguro no core.")
                    target.write_bytes(zf.read(member))
                    return target
        raise RuntimeError(f"Core não instalado: {filename}")

    def install_retroarch(self, destination: Path, progress=None) -> Path:
        """Download and extract the official portable RetroArch build."""
        destination.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="serm-retroarch-") as temp_name:
            archive = Path(temp_name) / "RetroArch.7z"
            EmulatorManager._download(self.RETROARCH_ARCHIVE, archive, 0, progress)
            extracted = Path(temp_name) / "extracted"
            extracted.mkdir()
            EmulatorManager._extract(archive, extracted)
            EmulatorManager._merge(extracted, destination)
        executable = destination / "retroarch.exe"
        if not executable.is_file():
            raise RuntimeError(f"RetroArch não encontrado após extração: {executable}")
        return executable
