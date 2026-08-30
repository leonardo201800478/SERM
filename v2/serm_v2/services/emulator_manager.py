"""Functional emulator installation and RetroArch management for SERM V2."""
from __future__ import annotations

import binascii
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
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
    date: str = ""
    crc32: str = ""
    channel: str = "stable"


class EmulatorManager:
    """Descobre, instala e atualiza MAME, Flycast, Supermodel e FBNeo."""

    REPOSITORIES = {
        "mame": "mamedev/mame",
        "flycast": "flyinghead/flycast",
        "supermodel": "trzy/supermodel",
        "fbneo": "finalburnneo/FBNeo",
    }
    LABELS = {"mame": "MAME", "flycast": "Flycast", "supermodel": "Supermodel", "fbneo": "FBNeo"}
    EXECUTABLES = {"mame": "mame.exe", "flycast": "flycast.exe", "supermodel": "Supermodel.exe", "fbneo": "fbneo64.exe"}

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
        for path in (Path(r"C:\Program Files\7-Zip\7z.exe"), Path(r"C:\Program Files (x86)\7-Zip\7z.exe"), Path.home() / "AppData" / "Local" / "7-Zip" / "7z.exe"):
            if path.is_file():
                return path
        return None

    def discover(self) -> dict[str, EmulatorStatus]:
        """Detecta executável, diretório e versão sem iniciar emuladores de forma destrutiva."""
        result: dict[str, EmulatorStatus] = {}
        for key, label in self.LABELS.items():
            root = self.roots.get(key)
            executable = self._find_executable(key, root)
            if executable:
                root = executable.parent
            version = self._read_version(key, root, executable)
            state = "ready" if executable else "configured" if root else "not_found"
            result[key] = EmulatorStatus(key, label, executable, root, version, state)
        return result

    def install(self, key: str, destination: Path, *, nightly: bool = False, progress=None, log=None) -> DownloadResult:
        """Baixa, extrai e valida o pacote Windows x64 oficial."""
        key = key.casefold()
        if key not in self.REPOSITORIES:
            raise ValueError(f"Emulador não suportado: {key}")
        destination = Path(destination).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        release = self._release(key, nightly=nightly)
        assets = release.get("assets") if isinstance(release.get("assets"), list) else []
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
        """Seleciona o melhor pacote Windows 64-bit."""
        candidates: list[tuple[int, dict[str, Any]]] = []
        for raw in assets:
            if not isinstance(raw, dict) or not raw.get("browser_download_url"):
                continue
            name = str(raw.get("name", "")).casefold()
            score = 0
            if any(t in name for t in ("windows", "win64", "win-x64", "win_x64", "mingw", "x86_64")): score += 50
            if any(t in name for t in ("x64", "x86_64", "amd64", "64bit", "64-bit")): score += 40
            if any(t in name for t in ("linux", "macos", "osx", "android", "ios", "arm64", "aarch64", "win32", "i386", "source", "src")): score -= 100
            if name.endswith(".zip"): score += 20
            elif name.endswith((".7z", ".7zip")): score += 10
            elif name.endswith(".exe"): score += 15
            if key == "mame" and re.search(r"_x64\.exe$", name): score += 140
            if key == "flycast" and "flycast-win64" in name: score += 150
            if key == "supermodel" and "supermodel" in name and "win" in name: score += 140
            if key == "fbneo" and name == "windows-x86_64.zip": score += 220
            if score >= 70: candidates.append((score, raw))
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
                output.write(chunk); received += len(chunk)
                if progress: progress(received, total)
        if received <= 0: raise RuntimeError("Download retornou zero bytes.")
        if log: log(f"DOWNLOAD | recebido={received:,} bytes | esperado={total:,} bytes")

    @classmethod
    def _extract(cls, archive: Path, destination: Path, log=None) -> None:
        """Extrai ZIP internamente ou usa o 7-Zip instalado."""
        if archive.suffix.casefold() == ".zip":
            with zipfile.ZipFile(archive) as zf:
                base = destination.resolve()
                for member in zf.infolist():
                    target = (destination / member.filename).resolve()
                    if target != base and base not in target.parents: raise RuntimeError("Pacote contém caminho de extração inseguro.")
                zf.extractall(destination); return
        seven_zip = cls.find_7zip()
        if seven_zip is None: raise RuntimeError("7z.exe não foi encontrado.")
        result = subprocess.run([str(seven_zip), "x", "-y", f"-o{destination}", str(archive)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=300, check=False)
        if result.returncode != 0: raise RuntimeError(f"7-Zip falhou ({result.returncode}): {(result.stdout or '').strip()}")
        if log: log(f"7-ZIP | extração concluída | {archive.name}")

    @staticmethod
    def _merge(source: Path, destination: Path) -> None:
        """Mescla a árvore extraída no diretório de instalação."""
        for item in source.iterdir():
            target = destination / item.name
            shutil.copytree(item, target, dirs_exist_ok=True) if item.is_dir() else shutil.copy2(item, target)

    def _find_executable(self, key: str, root: Path | None) -> Path | None:
        """Procura somente o executável oficial esperado."""
        name = self.EXECUTABLES[key]; candidates: list[Path] = []
        if root: candidates.extend((root / name, root / "bin" / name))
        for base in (Path.home() / "Documents", Path.home() / "Games", Path.home() / "Emulators", Path("C:/Emulators")): candidates.extend((base / self.LABELS[key] / name, base / key / name))
        return next((path.resolve() for path in candidates if path.is_file()), None)

    @staticmethod
    def _read_version(key: str, root: Path | None, executable: Path | None) -> str | None:
        """Detecta a versão instalada."""
        if root:
            for filename in (".serm-version", "VERSION", "version.txt", "build.txt"):
                path = root / filename
                if path.is_file():
                    try: text = path.read_text(encoding="utf-8-sig", errors="ignore").strip()
                    except OSError: continue
                    match = re.search(r"(?:v|version\s*)?([0-9]+\.[0-9]+(?:\.[0-9]+)?(?:[a-z]-[0-9]{8})?)", text, re.I)
                    if match: return match.group(1)
        if key == "fbneo" and root:
            ini = root / "config" / "fbneo64.ini"
            if ini.is_file():
                try:
                    match = re.search(r"FinalBurn\s+Neo\s+v([0-9]+(?:\.[0-9]+)+)", ini.read_text(encoding="utf-8-sig", errors="ignore"), re.I)
                    if match: return match.group(1)
                except OSError: pass
        if key == "mame" and executable: return EmulatorManager._probe_mame_version(executable)
        return None

    @staticmethod
    def _probe_mame_version(executable: Path) -> str | None:
        """Consulta a versão do MAME com uma CLI conhecida."""
        try:
            result = subprocess.run([str(executable), "-noreadconfig", "-version"], cwd=str(executable.parent), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=4, check=False)
            match = re.search(r"\b(?:v)?([0-9]+\.[0-9]+)\b", (result.stdout or "").strip())
            return match.group(1) if match else None
        except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired): return None

    @staticmethod
    def _log(callback, message: str) -> None:
        """Envia diagnóstico ao logger e ao callback da GUI."""
        logger.info("[EMULATOR] %s", message)
        if callback: callback(message)


class RetroArchManager:
    """Gerencia RetroArch x64 e os cores libretro pelo Buildbot oficial."""

    BUILD_ROOT = "https://buildbot.libretro.com"
    WINDOWS_ARCH = "x86_64"
    NIGHTLY_ROOT = f"{BUILD_ROOT}/nightly/windows/{WINDOWS_ARCH}/latest/"
    RETROARCH_ARCHIVE = "RetroArch.7z"
    VERSION_MARKER = ".serm-version"
    CHUNK_SIZE = 1024 * 1024
    TIMEOUT = 60
    RETRIES = 3

    LEGACY_CORE_NAMES = frozenset({
        "bnes2014", "desmume2015", "puae2021", "stella2014", "stella2023",
        "snes9x2002", "snes9x2005", "snes9x2005plus", "snes9x2010",
        "mame2000", "mame2003", "mame2003plus", "mame2003midway", "mame2009", "mame2010",
        "fbalpha2012", "fbalpha2012cps1", "fbalpha2012cps2", "fbalpha2012neogeo",
        "citra2018", "melonds2021",
    })
    LEGACY_CORE_PATTERNS = (
        re.compile(r"^bsnes2014(?:accuracy|balanced|performance)?$", re.I),
        re.compile(r"^snes9x20(?:0[25]|10)(?:plus)?$", re.I),
        re.compile(r"^mame(?:2000|2003|2003plus|2003midway|2009|2010)$", re.I),
    )
    GAME_ENGINE_CORE_PATTERNS = (
        re.compile(r"^(?:2048|anarch|boom|boom3|boom3xp|craft|cruzes|gong|jumpnbump|mrboom|opentyrian|puzzlescript|superbroswar)$", re.I),
        re.compile(r"^(?:openlara|prboom|prboomplus|nxengine|cannonball|chailove|lutro|lowresnx|retro8|reminiscence|scummvm|mkxpz)$", re.I),
        re.compile(r"^vita(?:quake|quake2|quake3|voyager).*$", re.I),
        re.compile(r"^(?:xrick|pascalpong|vircon32|wasm4|3dengine|imageviewer|mpv|pocketcdg)$", re.I),
    )

    def __init__(self, root: Path | None = None) -> None:
        """Inicializa o gerenciador."""
        self.root = Path(root).expanduser() if root else None

    @staticmethod
    def _version_key(value: str) -> tuple[int, ...]:
        """Converte uma versão Stable em uma chave ordenável."""
        return tuple(int(part) for part in value.split("."))

    @classmethod
    def _download_text(cls, url: str) -> str:
        """Baixa texto UTF-8 do Buildbot com retry."""
        last: Exception | None = None
        for _ in range(1, cls.RETRIES + 1):
            try:
                request = Request(url, headers={"User-Agent": "SERM/2.0", "Accept-Encoding": "identity"})
                with urlopen(request, timeout=cls.TIMEOUT) as response: return response.read().decode("utf-8", errors="replace")
            except (HTTPError, URLError, TimeoutError, OSError) as exc: last = exc
        raise RuntimeError(f"Falha ao consultar Buildbot: {url} | {last}") from last

    @classmethod
    def discover_stable_versions(cls) -> list[str]:
        """Consulta o diretório Stable oficial e retorna versões em ordem decrescente."""
        html = cls._download_text(f"{cls.BUILD_ROOT}/stable/"); versions: set[str] = set()
        for href in re.findall(r'href=["\']([^"\']+)["\']', html, re.I):
            match = re.search(r"(?:^|/)v?(\d+\.\d+(?:\.\d+)*)$", href.strip().strip("/"))
            if match: versions.add(match.group(1))
        return sorted(versions, key=cls._version_key, reverse=True)

    @classmethod
    def latest_stable_version(cls) -> str:
        """Retorna a versão Stable mais recente publicada pelo Buildbot."""
        versions = cls.discover_stable_versions()
        if not versions: raise RuntimeError("Nenhuma versão Stable do RetroArch foi encontrada no Buildbot.")
        return versions[0]

    @classmethod
    def discover_nightly_archive(cls) -> tuple[str, str]:
        """Localiza o pacote Nightly Windows x64 mais recente publicado."""
        base = f"{cls.BUILD_ROOT}/nightly/windows/{cls.WINDOWS_ARCH}/"; html = cls._download_text(base); filenames = []
        for href in re.findall(r'href=["\']([^"\']+)["\']', html, re.I):
            name = href.rsplit("/", 1)[-1]
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}_RetroArch\.7z", name, re.I): filenames.append(name)
        if not filenames: raise RuntimeError("Nenhum pacote Nightly datado do RetroArch foi encontrado.")
        filename = max(filenames, key=lambda value: value[:10]); return filename, base + filename

    @classmethod
    def buildroot(cls, channel: str, stable_version: str | None = None) -> tuple[str, str]:
        """Resolve URL e versão lógica para Stable ou Nightly."""
        normalized = channel.strip().casefold()
        if normalized == "stable":
            version = stable_version or cls.latest_stable_version(); return f"{cls.BUILD_ROOT}/stable/{version}/windows/{cls.WINDOWS_ARCH}/", version
        if normalized == "nightly": return cls.NIGHTLY_ROOT, "nightly"
        raise ValueError(f"Canal RetroArch inválido: {channel!r}")

    def discover(self) -> tuple[Path | None, Path | None, Path | None]:
        """Localiza retroarch.exe, raiz e diretório de cores."""
        candidates = [self.root / "retroarch.exe"] if self.root else []
        candidates += [Path.home() / "RetroArch-Win64" / "retroarch.exe", Path("C:/RetroArch/retroarch.exe")]
        executable = next((p.resolve() for p in candidates if p.is_file()), None); root = executable.parent if executable else self.root
        return executable, root, root / "cores" if root else None

    def detect_version(self, executable: Path | None) -> str | None:
        """Lê a versão persistida pelo SERM sem iniciar o RetroArch."""
        if not executable or not executable.is_file(): return None
        marker = executable.parent / self.VERSION_MARKER
        if marker.is_file():
            try: value = marker.read_text(encoding="utf-8-sig", errors="ignore").strip()
            except OSError: value = ""
            if value: return value.splitlines()[0].strip()
        return None

    @classmethod
    def detect_7zip(cls) -> Path | None:
        """Localiza 7-Zip no PATH ou nas instalações padrão do Windows."""
        candidates: list[Path] = []
        for command in ("7z.exe", "7z", "7za.exe", "7za"):
            found = shutil.which(command)
            if found: candidates.append(Path(found))
        roots = [os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA")]
        for root in filter(None, roots):
            base = Path(root); candidates.extend((base / "7-Zip" / "7z.exe", base / "7-Zip" / "7za.exe"))
        seen: set[str] = set()
        for candidate in candidates:
            try: resolved = candidate.expanduser().resolve()
            except OSError: continue
            key = str(resolved).casefold()
            if key in seen or not resolved.is_file(): continue
            seen.add(key); return resolved
        return None

    @classmethod
    def _download_file(cls, url: str, target: Path, progress=None, log=None) -> None:
        """Baixa um arquivo em blocos com retry e progresso."""
        last: Exception | None = None
        for attempt in range(1, cls.RETRIES + 1):
            received = 0
            try:
                request = Request(url, headers={"User-Agent": "SERM/2.0", "Accept-Encoding": "identity"})
                with urlopen(request, timeout=cls.TIMEOUT) as response, target.open("wb") as output:
                    total = int(response.headers.get("Content-Length") or 0)
                    while chunk := response.read(cls.CHUNK_SIZE): output.write(chunk); received += len(chunk); progress and progress(received, total)
                if received <= 0: raise RuntimeError("Download retornou zero bytes.")
                if log: log(f"DOWNLOAD | {received:,} bytes | tentativa={attempt}")
                return
            except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
                last = exc
                try: target.unlink(missing_ok=True)
                except OSError: pass
                if log: log(f"DOWNLOAD ERRO | tentativa={attempt}/{cls.RETRIES} | {exc}")
        raise RuntimeError(f"Falha no download: {url} | {last}") from last

    @classmethod
    def _extract_archive(cls, archive: Path, destination: Path, log=None) -> None:
        """Extrai ZIP internamente ou 7z/7zz para pacotes 7z."""
        destination.mkdir(parents=True, exist_ok=True)
        if archive.suffix.casefold() == ".zip":
            with zipfile.ZipFile(archive) as package:
                base = destination.resolve()
                for member in package.infolist():
                    target = (destination / member.filename).resolve()
                    if target != base and base not in target.parents: raise RuntimeError("Pacote contém caminho de extração inseguro.")
                package.extractall(destination); return
        seven_zip = cls.detect_7zip()
        if seven_zip is None: raise RuntimeError("7-Zip não foi encontrado para extrair o pacote RetroArch .7z.")
        result = subprocess.run([str(seven_zip), "x", "-y", f"-o{destination}", str(archive)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=300, check=False)
        if result.returncode != 0: raise RuntimeError(f"7-Zip falhou ({result.returncode}): {(result.stdout or '').strip()}")
        if log: log(f"7-ZIP | extração concluída | {archive.name}")

    @staticmethod
    def _flatten_single_root(source: Path) -> Path:
        """Remove o nível único RetroArch-Win64 quando o pacote o contém."""
        entries = [item for item in source.iterdir() if item.name != "__MACOSX"]
        return entries[0] if len(entries) == 1 and entries[0].is_dir() and (entries[0] / "retroarch.exe").is_file() else source

    @staticmethod
    def _merge_preserving(source: Path, destination: Path, excluded: set[str]) -> None:
        """Mescla a instalação preservando configurações, saves e states."""
        excluded_lower = {value.casefold() for value in excluded}
        for item in source.iterdir():
            if item.name.casefold() in excluded_lower: continue
            target = destination / item.name
            shutil.copytree(item, target, dirs_exist_ok=True) if item.is_dir() else shutil.copy2(item, target)

    def install_retroarch(self, destination: Path, *, channel: str = "nightly", stable_version: str | None = None, progress=None, log=None) -> Path:
        """Baixa e instala RetroArch x64 preservando dados do usuário."""
        destination = Path(destination).expanduser().resolve(); destination.mkdir(parents=True, exist_ok=True)
        buildroot, version = self.buildroot(channel, stable_version)
        filename, url = self.discover_nightly_archive() if channel.casefold() == "nightly" else (self.RETROARCH_ARCHIVE, f"{buildroot}{self.RETROARCH_ARCHIVE}")
        if log: log(f"RETROARCH | canal={channel} | versão={version}"); log(f"RETROARCH | download={url}")
        with tempfile.TemporaryDirectory(prefix="serm-retroarch-") as temp_name:
            temp = Path(temp_name); archive = temp / filename; self._download_file(url, archive, progress, log); extracted = temp / "extracted"; self._extract_archive(archive, extracted, log); source = self._flatten_single_root(extracted); self._merge_preserving(source, destination, {"config", "saves", "states", "retroarch.cfg", "retroarch.default.cfg"})
        executable = destination / "retroarch.exe"
        if not executable.is_file(): raise RuntimeError(f"retroarch.exe não encontrado após instalação: {destination}")
        try: (destination / self.VERSION_MARKER).write_text(version + "\n", encoding="utf-8")
        except OSError: logger.warning("Não foi possível gravar marcador de versão: %s", destination / self.VERSION_MARKER)
        if log: log(f"RETROARCH OK | executável={executable} | versão={version}")
        return executable

    @classmethod
    def is_legacy_core(cls, core: CoreInfo) -> bool:
        """Retorna True para snapshots históricos que não devem aparecer no modo atual."""
        normalized = re.sub(r"[^a-z0-9]", "", core.core_name.casefold())
        return normalized in cls.LEGACY_CORE_NAMES or any(pattern.fullmatch(normalized) for pattern in cls.LEGACY_CORE_PATTERNS)

    @classmethod
    def is_game_or_engine_core(cls, core: CoreInfo) -> bool:
        """Classifica ports de jogos e game engines que não são emuladores de sistemas."""
        normalized = re.sub(r"[^a-z0-9]", "", core.core_name.casefold())
        return any(pattern.fullmatch(normalized) for pattern in cls.GAME_ENGINE_CORE_PATTERNS)

    @classmethod
    def filter_cores(cls, cores: tuple[CoreInfo, ...], *, current_only: bool = True, hide_games: bool = True) -> tuple[CoreInfo, ...]:
        """Aplica os filtros de cores atuais e de jogos/engines."""
        return tuple(core for core in cores if (not current_only or not cls.is_legacy_core(core)) and (not hide_games or not cls.is_game_or_engine_core(core)))

    def list_cores(self, channel: str = "nightly", stable_version: str | None = None, *, current_only: bool = False, hide_games: bool = False) -> tuple[CoreInfo, ...]:
        """Lê .index-extended e retorna cores Windows x64, com filtros opcionais."""
        buildroot, _ = self.buildroot(channel, stable_version); text = self._download_text(buildroot + ".index-extended"); result: list[CoreInfo] = []
        for line in text.splitlines():
            parts = line.strip().split()
            if len(parts) < 3: continue
            date, crc, filename = parts[0], parts[1], parts[2]
            if not filename.casefold().endswith("_libretro.dll.zip"): continue
            result.append(CoreInfo(filename=filename, core_name=re.sub(r"_libretro\.dll$", "", filename.removesuffix(".zip"), flags=re.I), date=date, crc32=crc.lower().removeprefix("0x").zfill(8), channel=channel))
        result.sort(key=lambda item: item.core_name.casefold()); filtered = self.filter_cores(tuple(result), current_only=current_only, hide_games=hide_games)
        if not filtered: raise RuntimeError(f"Nenhum core corresponde aos filtros: {buildroot}.index-extended")
        return filtered

    def list_filtered_cores(self, *, include_beta: bool = False, current_only: bool = True, hide_games: bool = True, stable_version: str | None = None) -> tuple[CoreInfo, ...]:
        """Retorna Stable ou Stable+Beta/Nightly e aplica os filtros escolhidos."""
        channels = ["stable", "nightly"] if include_beta else ["stable"]; merged: dict[str, CoreInfo] = {}
        for channel in channels:
            for core in self.list_cores(channel, stable_version, current_only=False, hide_games=False):
                key = core.core_name.casefold()
                if key not in merged or channel == "stable": merged[key] = core
        return self.filter_cores(tuple(merged.values()), current_only=current_only, hide_games=hide_games)

    @staticmethod
    def _crc32(path: Path) -> str:
        """Calcula CRC32 de uma DLL local em blocos."""
        checksum = 0
        with Path(path).open("rb") as handle:
            while chunk := handle.read(1024 * 1024): checksum = binascii.crc32(chunk, checksum)
        return f"{checksum & 0xFFFFFFFF:08x}"

    @classmethod
    def crc32(cls, path: Path) -> str:
        """Calcula e retorna o CRC32 hexadecimal de um core instalado."""
        return cls._crc32(path)

    @staticmethod
    def installed_cores(cores_dir: Path | None) -> tuple[Path, ...]:
        """Lista somente DLLs libretro instaladas no diretório real."""
        if cores_dir is None: return ()
        path = Path(cores_dir).expanduser().resolve()
        if not path.is_dir(): return ()
        return tuple(sorted(path.glob("*_libretro.dll"), key=lambda item: item.name.casefold()))

    def compare_installed_cores(self, cores: tuple[CoreInfo, ...], cores_dir: Path | None) -> list[tuple[Path, CoreInfo | None, str]]:
        """Compara CRC32 local com o índice oficial; retorna estado por DLL."""
        remote = {core.filename.removesuffix(".zip").casefold(): core for core in cores}; result: list[tuple[Path, CoreInfo | None, str]] = []
        for path in self.installed_cores(cores_dir):
            local_crc = self._crc32(path); remote_core = remote.get(path.name.casefold()); state = "unknown" if remote_core is None else "current" if local_crc == remote_core.crc32 else "update"; result.append((path, remote_core, state))
        return result

    def install_core(self, filename: str, destination: Path, *, channel: str = "nightly", stable_version: str | None = None, progress=None, log=None) -> Path:
        """Baixa, valida CRC32 e instala uma única DLL libretro."""
        buildroot, version = self.buildroot(channel, stable_version); url = f"{buildroot}{filename}"; destination = Path(destination).expanduser().resolve(); destination.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="serm-core-") as temp_name:
            temp = Path(temp_name); archive = temp / Path(filename).name
            if log: log(f"RETROARCH | canal={channel} | versão={version} | core={filename}"); log(f"CORE | download={url}")
            self._download_file(url, archive, progress, log)
            with zipfile.ZipFile(archive) as package:
                bad = package.testzip()
                if bad: raise RuntimeError(f"ZIP corrompido do core: {bad}")
                dll_names = [name for name in package.namelist() if name.casefold().endswith("_libretro.dll")]
                if not dll_names: raise RuntimeError(f"ZIP sem DLL libretro: {filename}")
                data = package.read(dll_names[0])
            target_name = Path(dll_names[0]).name; target = (destination / target_name).resolve()
            if destination not in target.parents: raise RuntimeError("Caminho inseguro no core.")
            temp_dll = target.with_suffix(target.suffix + ".tmp"); temp_dll.write_bytes(data); actual_crc = self._crc32(temp_dll); remote_cores = self.list_cores(channel, stable_version); remote = next((core for core in remote_cores if core.filename.casefold() == filename.casefold()), None)
            if remote is None: temp_dll.unlink(missing_ok=True); raise RuntimeError(f"Core não encontrado no índice oficial: {filename}")
            if remote.crc32 != actual_crc: temp_dll.unlink(missing_ok=True); raise RuntimeError(f"CRC32 inválido para {target_name}: recebido={actual_crc}, esperado={remote.crc32}")
            temp_dll.replace(target)
        if log: log(f"CORE INSTALADO | {target} | CRC32={actual_crc}")
        return target
