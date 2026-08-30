"""Functional emulator installation and RetroArch management for SERM V2."""
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
    """Estado local de um emulador suportado."""
    key: str
    label: str
    executable: Path | None
    root: Path | None
    version: str | None
    state: str


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Resultado de uma instalação/atualização."""
    emulator: str
    version: str
    executable: Path
    archive: str


@dataclass(frozen=True, slots=True)
class CoreInfo:
    """Core libretro publicado pelo Buildbot oficial."""
    filename: str
    core_name: str


class EmulatorManager:
    """Descobre, instala e atualiza MAME, Flycast, Supermodel e FBNeo."""

    REPOSITORIES = {
        "mame": "mamedev/mame",
        "flycast": "flyinghead/flycast",
        "supermodel": "trzy/supermodel",
        "fbneo": "finalburnneo/FBNeo",
    }
    LABELS = {"mame": "MAME", "flycast": "Flycast", "supermodel": "Supermodel", "fbneo": "FBNeo"}
    EXECUTABLES = {
        "mame": "mame.exe",
        "flycast": "flycast.exe",
        "supermodel": "Supermodel.exe",
        "fbneo": "fbneo64.exe",
    }

    def __init__(self, roots: dict[str, Path | None] | None = None) -> None:
        """Inicializa o gerenciador com as raízes persistidas."""
        self.roots = {k: Path(v).expanduser() if v else None for k, v in (roots or {}).items()}

    @staticmethod
    def find_7zip() -> Path | None:
        """Localiza o executável de linha de comando do 7-Zip."""
        for name in ("7z.exe", "7zz.exe", "7za.exe"):
            found = shutil.which(name)
            if found:
                return Path(found)
        for path in (
            Path(r"C:\Program Files\7-Zip\7z.exe"),
            Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
            Path.home() / "AppData" / "Local" / "7-Zip" / "7z.exe",
        ):
            if path.is_file():
                return path
        return None

    def discover(self) -> dict[str, EmulatorStatus]:
        """Detecta executável, diretório e versão instalada sem download."""
        result: dict[str, EmulatorStatus] = {}
        for key, label in self.LABELS.items():
            root = self.roots.get(key)
            executable = self._find_executable(key, root)
            if executable:
                root = executable.parent
            version = self._read_version(key, root, executable)
            state = "ready" if executable else "configured" if root else "not_found"
            result[key] = EmulatorStatus(key, label, executable, root, version, state)
            logger.info(
                "[EMULATOR][DISCOVERY] %s state=%s exe=%s root=%s version=%s",
                key, state, executable, root, version,
            )
        return result

    def install(self, key: str, destination: Path, *, nightly: bool = False, progress=None, log=None) -> DownloadResult:
        """Baixa, extrai e valida o pacote Windows x64 oficial."""
        key = key.casefold()
        if key not in self.REPOSITORIES:
            raise ValueError(f"Emulador não suportado: {key}")
        destination = Path(destination).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        release = self._release(key, nightly=nightly)
        assets = release.get("assets")
        if not isinstance(assets, list):
            assets = []
        asset = self._select_asset(key, assets)
        if not asset:
            raise RuntimeError(f"Nenhum pacote Windows x64 encontrado para {key}.")
        version = str(release.get("tag_name") or release.get("name") or "unknown")
        self._log(log, f"RELEASE | {key} | versão={version} | asset={asset['name']}")
        with tempfile.TemporaryDirectory(prefix="serm-emu-") as temp_name:
            temp = Path(temp_name)
            archive = temp / str(asset["name"])
            self._download(str(asset["browser_download_url"]), archive, int(asset.get("size") or 0), progress, log)
            extracted = temp / "extracted"
            extracted.mkdir()
            self._extract(archive, extracted, log)
            self._merge(extracted, destination)
        executable = self._find_executable(key, destination)
        if executable is None:
            raise RuntimeError(f"Instalação concluída, mas {self.EXECUTABLES[key]} não foi encontrado em {destination}.")
        return DownloadResult(key, version, executable, str(asset["name"]))

    def _release(self, key: str, *, nightly: bool) -> dict[str, Any]:
        """Consulta o release oficial do GitHub."""
        return self._json(f"https://api.github.com/repos/{self.REPOSITORIES[key]}/releases/latest")

    @staticmethod
    def _json(url: str) -> dict[str, Any]:
        """Obtém um objeto JSON público."""
        request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "SERM/2.0"})
        with urlopen(request, timeout=30) as response:
            value = json.loads(response.read().decode("utf-8"))
        if not isinstance(value, dict):
            raise RuntimeError("Resposta JSON inesperada.")
        return value

    @classmethod
    def _select_asset(cls, key: str, assets: list[object]) -> dict[str, Any] | None:
        """Seleciona o melhor pacote Windows 64-bit; FBNeo exige Windows x86_64."""
        candidates: list[tuple[int, dict[str, Any]]] = []
        for raw in assets:
            if not isinstance(raw, dict) or not raw.get("browser_download_url"):
                continue
            name = str(raw.get("name", "")).casefold()
            score = 0
            if any(t in name for t in ("windows", "win64", "win-x64", "win_x64", "mingw", "x86_64")):
                score += 50
            if any(t in name for t in ("x64", "x86_64", "amd64", "64bit", "64-bit")):
                score += 40
            if any(t in name for t in ("linux", "macos", "osx", "android", "ios", "arm64", "aarch64", "win32", "i386", "source", "src")):
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
                score += 220
            if score >= 70:
                candidates.append((score, raw))
        candidates.sort(key=lambda item: (item[0], int(item[1].get("size") or 0)), reverse=True)
        return candidates[0][1] if candidates else None

    @staticmethod
    def _download(url: str, target: Path, expected: int, progress=None, log=None) -> None:
        """Baixa um arquivo com progresso."""
        request = Request(url, headers={"User-Agent": "SERM/2.0", "Accept-Encoding": "identity"})
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
        if log:
            log(f"DOWNLOAD | recebido={received:,} bytes | esperado={total:,} bytes")

    @classmethod
    def _extract(cls, archive: Path, destination: Path, log=None) -> None:
        """Extrai ZIP internamente ou usa o 7-Zip instalado."""
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
            raise RuntimeError("7z.exe não foi encontrado.")
        result = subprocess.run(
            [str(seven_zip), "x", "-y", f"-o{destination}", str(archive)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=300, check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"7-Zip falhou ({result.returncode}): {(result.stderr or result.stdout).strip()}")
        if log:
            log(f"7-ZIP | extração concluída | {archive.name}")

    @staticmethod
    def _merge(source: Path, destination: Path) -> None:
        """Mescla a árvore extraída no diretório de instalação."""
        for item in source.iterdir():
            target = destination / item.name
            shutil.copytree(item, target, dirs_exist_ok=True) if item.is_dir() else shutil.copy2(item, target)

    def _find_executable(self, key: str, root: Path | None) -> Path | None:
        """Procura somente o executável oficial esperado."""
        name = self.EXECUTABLES[key]
        candidates: list[Path] = []
        if root:
            candidates.extend((root / name, root / "bin" / name))
        for base in (Path.home() / "Documents", Path.home() / "Games", Path.home() / "Emulators", Path("C:/Emulators")):
            candidates.extend((base / self.LABELS[key] / name, base / key / name))
        return next((path.resolve() for path in candidates if path.is_file()), None)

    @staticmethod
    def _read_version(key: str, root: Path | None, executable: Path | None) -> str | None:
        """Detecta a versão por metadados oficiais e, quando seguro, pela CLI do executável."""
        if root:
            for filename in (".serm-version", "VERSION", "version.txt", "build.txt"):
                path = root / filename
                if path.is_file():
                    try:
                        text = path.read_text(encoding="utf-8-sig", errors="ignore").strip()
                    except OSError:
                        continue
                    match = re.search(r"(?:v|version\s*)?([0-9]+\.[0-9]+(?:\.[0-9]+)?(?:[a-z]-[0-9]{8})?)", text, re.I)
                    if match:
                        return match.group(1)
        if key == "fbneo" and root:
            ini = root / "config" / "fbneo64.ini"
            if ini.is_file():
                try:
                    text = ini.read_text(encoding="utf-8-sig", errors="ignore")
                    match = re.search(r"FinalBurn\s+Neo\s+v([0-9]+(?:\.[0-9]+)+)", text, re.I)
                    if match:
                        return match.group(1)
                except OSError:
                    pass
        if executable:
            return EmulatorManager._probe_executable_version(key, executable)
        return None

    @staticmethod
    def _probe_executable_version(key: str, executable: Path) -> str | None:
        """Consulta versões por CLI sem shell e sem criar janela visível."""
        argument_sets = {
            "mame": (("-noreadconfig", "-version"),),
            "flycast": (("--version",), ("-version",)),
            "supermodel": (("--version",), ("-version",)),
            "fbneo": (("--version",), ("-version",)),
        }
        for args in argument_sets.get(key, ()):
            try:
                result = subprocess.run(
                    [str(executable), *args], cwd=str(executable.parent), stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                    errors="replace", shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    timeout=4, check=False,
                )
                text = (result.stdout or "").strip()
                match = re.search(r"\b(?:v(?:ersion)?\s*)?([0-9]+\.[0-9]+(?:\.[0-9]+)?(?:[a-z]-[0-9]{8})?)\b", text, re.I)
                if match:
                    return match.group(1)
            except (OSError, subprocess.SubprocessError):
                continue
        return None

    @staticmethod
    def _log(callback, message: str) -> None:
        """Envia diagnóstico ao logger e ao callback da GUI."""
        logger.info("[EMULATOR] %s", message)
        if callback:
            callback(message)


class RetroArchManager:
    """Gerencia RetroArch x64 estável/nightly e cores do Buildbot oficial."""

    NIGHTLY_ROOT = "https://buildbot.libretro.com/nightly/windows/x86_64/latest"
    STABLE_ROOT_TEMPLATE = "https://buildbot.libretro.com/stable/{version}/windows/x86_64"
    RETROARCH_ARCHIVE = "RetroArch.7z"

    def __init__(self, root: Path | None = None) -> None:
        """Inicializa o gerenciador."""
        self.root = Path(root).expanduser() if root else None

    @staticmethod
    def latest_stable_version() -> str:
        """Obtém a tag estável atual do RetroArch no GitHub."""
        request = Request(
            "https://api.github.com/repos/libretro/RetroArch/releases/latest",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "SERM/2.0"},
        )
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        tag = str(payload.get("tag_name") or "")
        match = re.search(r"(\d+\.\d+(?:\.\d+)*)", tag)
        if not match:
            raise RuntimeError("Não foi possível determinar a versão estável do RetroArch.")
        return match.group(1)

    @classmethod
    def buildroot(cls, channel: str) -> tuple[str, str]:
        """Resolve URL e versão lógica para stable ou nightly."""
        if channel == "stable":
            version = cls.latest_stable_version()
            return cls.STABLE_ROOT_TEMPLATE.format(version=version), version
        return cls.NIGHTLY_ROOT, "nightly"

    def discover(self) -> tuple[Path | None, Path | None, Path | None]:
        """Localiza retroarch.exe, raiz e diretório de cores."""
        candidates = [self.root / "retroarch.exe"] if self.root else []
        candidates += [Path.home() / "RetroArch-Win64" / "retroarch.exe", Path("C:/RetroArch/retroarch.exe")]
        executable = next((p.resolve() for p in candidates if p.is_file()), None)
        root = executable.parent if executable else self.root
        cores = root / "cores" if root else None
        return executable, root, cores

    def detect_version(self, executable: Path | None) -> str | None:
        """Detecta a versão local do RetroArch."""
        if not executable or not executable.is_file():
            return None
        try:
            result = subprocess.run(
                [str(executable), "--version"], capture_output=True, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=4, check=False,
            )
            match = re.search(r"RetroArch\s+v?([0-9]+\.[0-9]+(?:\.[0-9]+)?)", result.stdout or "", re.I)
            return match.group(1) if match else None
        except (OSError, subprocess.SubprocessError):
            return None

    def list_cores(self, channel: str = "nightly") -> tuple[CoreInfo, ...]:
        """Lê o catálogo de cores correspondente ao canal selecionado."""
        buildroot, _ = self.buildroot(channel)
        request = Request(buildroot + "/", headers={"User-Agent": "SERM/2.0"})
        with urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8", errors="replace")
        names = sorted(set(re.findall(r'href=["\']([^"\']+_libretro\.dll\.zip)["\']', html, re.I)))
        return tuple(CoreInfo(name, name.removesuffix("_libretro.dll.zip")) for name in names)

    def install_core(self, filename: str, destination: Path, *, channel: str = "nightly", progress=None, log=None) -> Path:
        """Baixa e instala um core do canal selecionado."""
        destination.mkdir(parents=True, exist_ok=True)
        buildroot, version = self.buildroot(channel)
        url = f"{buildroot}/{filename}"
        if log:
            log(f"RETROARCH | canal={channel} | versão={version} | core={filename}")
        with tempfile.TemporaryDirectory(prefix="serm-core-") as temp_name:
            archive = Path(temp_name) / filename
            EmulatorManager._download(url, archive, 0, progress, log)
            with zipfile.ZipFile(archive) as zf:
                dlls = [m for m in zf.infolist() if m.filename.lower().endswith(".dll")]
                if not dlls:
                    raise RuntimeError(f"Core sem DLL: {filename}")
                target = (destination / Path(dlls[0].filename).name).resolve()
                if destination.resolve() not in target.parents:
                    raise RuntimeError("Caminho inseguro no core.")
                target.write_bytes(zf.read(dlls[0]))
                return target
        raise RuntimeError(f"Core não instalado: {filename}")

    def install_retroarch(self, destination: Path, *, channel: str = "nightly", progress=None, log=None) -> Path:
        """Baixa e extrai RetroArch x64 no canal estável ou nightly."""
        destination.mkdir(parents=True, exist_ok=True)
        buildroot, version = self.buildroot(channel)
        url = f"{buildroot}/{self.RETROARCH_ARCHIVE}"
        if log:
            log(f"RETROARCH | canal={channel} | versão={version}")
            log(f"RETROARCH | download={url}")
        with tempfile.TemporaryDirectory(prefix="serm-retroarch-") as temp_name:
            archive = Path(temp_name) / self.RETROARCH_ARCHIVE
            EmulatorManager._download(url, archive, 0, progress, log)
            extracted = Path(temp_name) / "extracted"
            extracted.mkdir()
            EmulatorManager._extract(archive, extracted, log)
            EmulatorManager._merge(extracted, destination)
        executable = destination / "retroarch.exe"
        if not executable.is_file():
            raise RuntimeError(f"RetroArch não encontrado após extração: {executable}")
        if log:
            log(f"RETROARCH OK | executável={executable} | versão={version}")
        return executable
