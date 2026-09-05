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
    """Descobre, instala e atualiza os emuladores suportados pelo SERM."""
    REPOSITORIES = {"mame": "mamedev/mame", "flycast": "flyinghead/flycast", "supermodel": "trzy/supermodel", "fbneo": "finalburnneo/FBNeo"}
    LABELS = {"mame": "MAME", "flycast": "Flycast", "supermodel": "Supermodel", "fbneo": "FBNeo"}
    EXECUTABLES = {"mame": "mame.exe", "flycast": "flycast.exe", "supermodel": "Supermodel.exe", "fbneo": "fbneo64.exe"}

    def __init__(self, roots: dict[str, Path | None] | None = None) -> None:
        """Inicializa com as raízes persistidas."""
        self.roots = {k: Path(v).expanduser() if v else None for k, v in (roots or {}).items()}

    @staticmethod
    def find_7zip() -> Path | None:
        """Localiza 7-Zip no PATH ou em instalações padrão."""
        for name in ("7z.exe", "7zz.exe", "7za.exe"):
            found = shutil.which(name)
            if found: return Path(found)
        for path in (Path(r"C:\Program Files\7-Zip\7z.exe"), Path(r"C:\Program Files (x86)\7-Zip\7z.exe"), Path.home() / "AppData/Local/7-Zip/7z.exe"):
            if path.is_file(): return path
        return None

    def discover(self) -> dict[str, EmulatorStatus]:
        """Detecta executável, raiz e versão dos emuladores."""
        result: dict[str, EmulatorStatus] = {}
        for key, label in self.LABELS.items():
            root = self.roots.get(key); executable = self._find_executable(key, root)
            if executable: root = executable.parent
            version = self._read_version(key, root, executable); state = "ready" if executable else "configured" if root else "not_found"
            result[key] = EmulatorStatus(key, label, executable, root, version, state)
        return result

    def install(self, key: str, destination: Path, *, nightly: bool = False, progress=None, log=None) -> DownloadResult:
        """Baixa e instala o pacote Windows x64 oficial."""
        key = key.casefold()
        if key not in self.REPOSITORIES: raise ValueError(f"Emulador não suportado: {key}")
        destination = Path(destination).expanduser().resolve(); destination.mkdir(parents=True, exist_ok=True)
        release = self._release(key, nightly=nightly); assets_value = release.get("assets"); assets: list[object] = assets_value if isinstance(assets_value, list) else []
        asset = self._select_asset(key, assets)
        if not asset: raise RuntimeError(f"Nenhum pacote Windows x64 encontrado para {key}.")
        version = str(release.get("tag_name") or release.get("name") or "unknown")
        with tempfile.TemporaryDirectory(prefix="serm-emu-") as temp_name:
            temp = Path(temp_name); archive = temp / str(asset["name"]); self._download(str(asset["browser_download_url"]), archive, int(asset.get("size") or 0), progress, log); extracted = temp / "extracted"; extracted.mkdir(); self._extract(archive, extracted, log); self._merge(extracted, destination)
        executable = self._find_executable(key, destination)
        if executable is None: raise RuntimeError(f"Instalação concluída, mas {self.EXECUTABLES[key]} não foi encontrado em {destination}.")
        return DownloadResult(key, version, executable, str(asset["name"]))

    def _release(self, key: str, *, nightly: bool) -> dict[str, Any]:
        """Consulta o release oficial do GitHub."""
        return self._json(f"https://api.github.com/repos/{self.REPOSITORIES[key]}/releases/latest")

    @staticmethod
    def _json(url: str) -> dict[str, Any]:
        """Obtém um objeto JSON público."""
        request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "SERM/2.0"})
        with urlopen(request, timeout=30) as response: value = json.loads(response.read().decode("utf-8"))
        if not isinstance(value, dict): raise RuntimeError("Resposta JSON inesperada.")
        return value

    @classmethod
    def _select_asset(cls, key: str, assets: list[object]) -> dict[str, Any] | None:
        """Seleciona o melhor pacote Windows 64-bit."""
        candidates: list[tuple[int, dict[str, Any]]] = []
        for raw in assets:
            if not isinstance(raw, dict) or not raw.get("browser_download_url"): continue
            name = str(raw.get("name", "")).casefold(); score = 0
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
        request = Request(url, headers={"User-Agent": "SERM/2.0", "Accept-Encoding": "identity"}); received = 0
        with urlopen(request, timeout=120) as response, target.open("wb") as output:
            total = int(response.headers.get("Content-Length") or expected or 0)
            while chunk := response.read(1024 * 1024): output.write(chunk); received += len(chunk); progress and progress(received, total)
        if received <= 0: raise RuntimeError("Download retornou zero bytes.")
        if log: log(f"DOWNLOAD | recebido={received:,} bytes | esperado={total:,} bytes")

    @classmethod
    def _extract(cls, archive: Path, destination: Path, log=None) -> None:
        """Extrai ZIP internamente ou usa 7-Zip."""
        if archive.suffix.casefold() == ".zip":
            with zipfile.ZipFile(archive) as zf: zf.extractall(destination)
            return
        seven_zip = cls.find_7zip()
        if seven_zip is None: raise RuntimeError("7z.exe não foi encontrado.")
        result = subprocess.run([str(seven_zip), "x", "-y", f"-o{destination}", str(archive)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=300, check=False)
        if result.returncode != 0: raise RuntimeError(f"7-Zip falhou ({result.returncode}): {(result.stdout or '').strip()}")

    @staticmethod
    def _merge(source: Path, destination: Path) -> None:
        """Mescla a árvore extraída no diretório de instalação."""
        for item in source.iterdir():
            target = destination / item.name; shutil.copytree(item, target, dirs_exist_ok=True) if item.is_dir() else shutil.copy2(item, target)

    def _find_executable(self, key: str, root: Path | None) -> Path | None:
        """Procura somente o executável oficial esperado."""
        name = self.EXECUTABLES[key]; candidates: list[Path] = []
        if root: candidates.extend((root / name, root / "bin" / name))
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
        if key == "mame" and executable: return EmulatorManager._probe_mame_version(executable)
        return None

    @staticmethod
    def _probe_mame_version(executable: Path) -> str | None:
        """Consulta a versão do MAME."""
        try:
            result = subprocess.run([str(executable), "-noreadconfig", "-version"], cwd=str(executable.parent), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=4, check=False)
            match = re.search(r"\b(?:v)?([0-9]+\.[0-9]+)\b", (result.stdout or "").strip()); return match.group(1) if match else None
        except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired): return None

class RetroArchManager:
    """Gerencia RetroArch x64 e catálogo de cores libretro."""
    BUILD_ROOT = "https://buildbot.libretro.com"
    WINDOWS_ARCH = "x86_64"
    NIGHTLY_ROOT = f"{BUILD_ROOT}/nightly/windows/{WINDOWS_ARCH}/latest/"
    RETROARCH_ARCHIVE = "RetroArch.7z"
    VERSION_MARKER = ".serm-version"
    CHUNK_SIZE = 1024 * 1024
    TIMEOUT = 60
    RETRIES = 3
    LEGACY_CORE_NAMES = frozenset({"bnes2014", "desmume2015", "puae2021", "stella2014", "stella2023", "snes9x2002", "snes9x2005", "snes9x2005plus", "snes9x2010", "mame2000", "mame2003", "mame2003plus", "mame2003midway", "mame2009", "mame2010", "fbalpha2012", "fbalpha2012cps1", "fbalpha2012cps2", "fbalpha2012cps3", "fbalpha2012neogeo", "citra2018", "melonds2021", "bsnes2014accuracy", "bsnes2014balanced", "bsnes2014performance"})
    LEGACY_CORE_PATTERNS = (re.compile(r"^snes9x20(?:0[25]|10)(?:plus)?$", re.I), re.compile(r"^mame(?:2000|2003|2003plus|2003midway|2009|2010)$", re.I), re.compile(r"^(?:bnes|desmume|puae|stella)20(?:14|15|21|23)$", re.I))
    GAME_ENGINE_CORE_PATTERNS = (re.compile(r"^(?:2048|anarch|boom|boom3|boom3xp|craft|cruzes|gong|jumpnbump|mrboom|opentyrian|puzzlescript|superbroswar)$", re.I), re.compile(r"^(?:openlara|prboom|prboomplus|nxengine|cannonball|chailove|lutro|lowresnx|retro8|reminiscence|scummvm|mkxpz)$", re.I), re.compile(r"^vita(?:quake|quake2|quake3|voyager).*$", re.I), re.compile(r"^(?:xrick|pascalpong|vircon32|wasm4|3dengine|imageviewer|mpv|pocketcdg)$", re.I))

    def __init__(self, root: Path | None = None) -> None:
        """Inicializa o gerenciador."""
        self.root = Path(root).expanduser() if root else None

    def discover(self) -> tuple[Path | None, Path | None, Path | None]:
        """Localiza retroarch.exe, raiz e diretório de cores."""
        candidates = [self.root / "retroarch.exe"] if self.root else []
        candidates.extend((Path.home() / "RetroArch-Win64/retroarch.exe", Path("C:/RetroArch/retroarch.exe")))
        executable = next((path.resolve() for path in candidates if path.is_file()), None)
        root = executable.parent if executable else self.root
        cores = root / "cores" if root else None
        return executable, root, cores

    @staticmethod
    def detect_version(executable: Path | None) -> str | None:
        """Detecta a versão do RetroArch sem abrir janela."""
        if executable is None or not executable.is_file(): return None
        marker = executable.parent / ".serm-version"
        if marker.is_file():
            try: return marker.read_text(encoding="utf-8-sig", errors="ignore").strip() or None
            except OSError: pass
        try:
            result = subprocess.run([str(executable), "--version"], cwd=str(executable.parent), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=4, check=False)
            match = re.search(r"RetroArch\s+([0-9]+\.[0-9]+(?:\.[0-9]+)?)", result.stdout or "", re.I)
            return match.group(1) if match else None
        except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired): return None

    @classmethod
    def _download_text(cls, url: str) -> str:
        """Baixa texto UTF-8 do Buildbot com retry."""
        last: Exception | None = None
        for _ in range(cls.RETRIES):
            try:
                request = Request(url, headers={"User-Agent": "SERM/2.0", "Accept-Encoding": "identity"})
                with urlopen(request, timeout=cls.TIMEOUT) as response: return response.read().decode("utf-8", errors="replace")
            except (HTTPError, URLError, TimeoutError, OSError) as exc: last = exc
        raise RuntimeError(f"Falha ao consultar Buildbot: {url} | {last}") from last

    @classmethod
    def discover_stable_versions(cls) -> list[str]:
        """Descobre versões Stable publicadas."""
        html = cls._download_text(f"{cls.BUILD_ROOT}/stable/"); versions: set[str] = set()
        for href in re.findall(r'href=["\']([^"\']+)["\']', html, re.I):
            match = re.search(r"(?:^|/)v?(\d+\.\d+(?:\.\d+)*)/?$", href.strip())
            if match: versions.add(match.group(1))
        return sorted(versions, key=lambda value: tuple(map(int, value.split("."))), reverse=True)

    @classmethod
    def latest_stable_version(cls) -> str:
        """Retorna a Stable mais recente."""
        versions = cls.discover_stable_versions()
        if not versions: raise RuntimeError("Nenhuma versão Stable encontrada.")
        return versions[0]

    @classmethod
    def discover_nightly_archive(cls) -> tuple[str, str]:
        """Localiza o pacote Nightly x64 mais recente."""
        base = f"{cls.BUILD_ROOT}/nightly/windows/{cls.WINDOWS_ARCH}/"; html = cls._download_text(base); filenames = [href.rsplit("/", 1)[-1] for href in re.findall(r'href=["\']([^"\']+)["\']', html, re.I)]; filenames = [name for name in filenames if re.fullmatch(r"\d{4}-\d{2}-\d{2}_RetroArch\.7z", name, re.I)]
        if not filenames: raise RuntimeError("Nenhum pacote Nightly encontrado.")
        filename = max(filenames, key=lambda value: value[:10]); return filename, base + filename

    @classmethod
    def buildroot(cls, channel: str, stable_version: str | None = None) -> tuple[str, str]:
        """Resolve a raiz do frontend RetroArch."""
        if channel.casefold() == "stable":
            version = stable_version or cls.latest_stable_version(); return f"{cls.BUILD_ROOT}/stable/{version}/windows/{cls.WINDOWS_ARCH}/", version
        if channel.casefold() == "nightly": return cls.NIGHTLY_ROOT, "nightly"
        raise ValueError(f"Canal RetroArch inválido: {channel!r}")

    @classmethod
    def _core_catalog_url(cls, channel: str) -> str:
        """Retorna o índice de cores disponível para o catálogo."""
        if channel.casefold() == "nightly": return f"{cls.NIGHTLY_ROOT}.index-extended"
        if channel.casefold() == "stable": return f"{cls.NIGHTLY_ROOT}.index-extended"
        raise ValueError(f"Canal de cores inválido: {channel!r}")

    @staticmethod
    def _parse_core_index(text: str, channel: str) -> tuple[CoreInfo, ...]:
        """Converte .index-extended em CoreInfo."""
        result: list[CoreInfo] = []
        for line in text.splitlines():
            parts = line.strip().split()
            if len(parts) < 3: continue
            date, crc, filename = parts[0], parts[1], parts[-1]
            if not filename.casefold().endswith("_libretro.dll.zip"): continue
            name = re.sub(r"_libretro\.dll$", "", filename.removesuffix(".zip"), flags=re.I)
            result.append(CoreInfo(filename=filename, core_name=name, date=date, crc32=crc.lower().removeprefix("0x").zfill(8), channel=channel))
        return tuple(sorted(result, key=lambda item: item.core_name.casefold()))

    @classmethod
    def is_legacy_core(cls, core: CoreInfo) -> bool:
        """Identifica snapshots históricos."""
        normalized = re.sub(r"[^a-z0-9]", "", core.core_name.casefold())
        return normalized in cls.LEGACY_CORE_NAMES or any(pattern.fullmatch(normalized) for pattern in cls.LEGACY_CORE_PATTERNS)

    @classmethod
    def is_game_or_engine_core(cls, core: CoreInfo) -> bool:
        """Identifica ports, jogos e game engines."""
        normalized = re.sub(r"[^a-z0-9]", "", core.core_name.casefold())
        return any(pattern.fullmatch(normalized) for pattern in cls.GAME_ENGINE_CORE_PATTERNS)

    @classmethod
    def filter_cores(cls, cores: tuple[CoreInfo, ...], *, current_only: bool = True, hide_games: bool = True) -> tuple[CoreInfo, ...]:
        """Aplica os filtros solicitados para o catálogo."""
        return tuple(core for core in cores if (not current_only or not cls.is_legacy_core(core)) and (not hide_games or not cls.is_game_or_engine_core(core)))

    def list_cores(self, channel: str = "nightly", stable_version: str | None = None, *, current_only: bool = False, hide_games: bool = False) -> tuple[CoreInfo, ...]:
        """Lê o catálogo oficial sem gerar 404 no caminho Stable."""
        _ = stable_version
        result = self._parse_core_index(self._download_text(self._core_catalog_url(channel)), channel)
        filtered = self.filter_cores(result, current_only=current_only, hide_games=hide_games)
        if not filtered: raise RuntimeError(f"Nenhum core corresponde aos filtros no catálogo {channel}.")
        return filtered

    def list_filtered_cores(self, *, include_beta: bool = False, current_only: bool = True, hide_games: bool = True, stable_version: str | None = None) -> tuple[CoreInfo, ...]:
        """Monta Stable ou Stable+Nightly sem consultar uma URL Stable inexistente."""
        channels = ("stable", "nightly") if include_beta else ("stable",); merged: dict[str, CoreInfo] = {}
        for channel in channels:
            for core in self.list_cores(channel, stable_version, current_only=False, hide_games=False):
                key = core.core_name.casefold()
                if key not in merged or channel == "stable": merged[key] = core
        return self.filter_cores(tuple(merged.values()), current_only=current_only, hide_games=hide_games)

    @staticmethod
    def _crc32(path: Path) -> str:
        """Calcula CRC32 em blocos."""
        checksum = 0
        with Path(path).open("rb") as handle:
            while chunk := handle.read(1024 * 1024): checksum = binascii.crc32(chunk, checksum)
        return f"{checksum & 0xFFFFFFFF:08x}"

    @classmethod
    def crc32(cls, path: Path) -> str:
        """Calcula CRC32 hexadecimal."""
        return cls._crc32(path)

    @staticmethod
    def installed_cores(cores_dir: Path | None) -> tuple[Path, ...]:
        """Lista cores instalados."""
        if cores_dir is None: return ()
        path = Path(cores_dir).expanduser().resolve()
        return tuple(sorted(path.glob("*_libretro.dll"), key=lambda item: item.name.casefold())) if path.is_dir() else ()

    def compare_installed_cores(self, cores: tuple[CoreInfo, ...], cores_dir: Path | None) -> list[tuple[Path, CoreInfo | None, str]]:
        """Compara CRC32 local com o catálogo."""
        remote = {core.filename.removesuffix(".zip").casefold(): core for core in cores}; result: list[tuple[Path, CoreInfo | None, str]] = []
        for path in self.installed_cores(cores_dir):
            remote_core = remote.get(path.name.casefold()); local_crc = self._crc32(path); state = "unknown" if remote_core is None else "current" if local_crc == remote_core.crc32 else "update"; result.append((path, remote_core, state))
        return result

    def install_core(self, filename: str, destination: Path, *, channel: str = "nightly", stable_version: str | None = None, progress=None, log=None) -> Path:
        """Baixa e instala um core individual do Buildbot Nightly."""
        if channel.casefold() == "stable":
            raise RuntimeError("O Buildbot Stable não publica cores individuais; o snapshot Stable é RetroArch_cores.7z. Use Nightly para instalação individual.")
        filename = Path(filename).name
        if not filename or not filename.casefold().endswith("_libretro.dll.zip"):
            raise ValueError(f"Nome de core inválido para download: {filename!r}")
        url = f"{self.NIGHTLY_ROOT}{filename}"
        destination = Path(destination).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        temp_dir = Path(tempfile.mkdtemp(prefix="serm-core-"))
        archive: Path | None = None
        try:
            fd, temp_name = tempfile.mkstemp(prefix="core-", suffix=".zip", dir=temp_dir)
            os.close(fd)
            archive = Path(temp_name)
            if log: log(f"DOWNLOAD | core={filename} | temporário={archive}")
            self._download_file(url, archive, progress, log)
            with zipfile.ZipFile(archive) as package:
                bad = package.testzip()
                if bad: raise RuntimeError(f"ZIP corrompido do core: {bad}")
                dll_names = [name for name in package.namelist() if name.casefold().endswith("_libretro.dll")]
                if not dll_names: raise RuntimeError(f"ZIP sem DLL libretro: {filename}")
                data = package.read(dll_names[0])
            target = (destination / Path(dll_names[0]).name).resolve()
            if destination not in target.parents: raise RuntimeError("Caminho inseguro no core.")
            temp_dll = target.with_suffix(target.suffix + ".tmp")
            temp_dll.write_bytes(data)
            actual_crc = self._crc32(temp_dll)
            remote = next((core for core in self.list_cores("nightly", stable_version) if core.filename.casefold() == filename.casefold()), None)
            if remote is None or remote.crc32 != actual_crc:
                temp_dll.unlink(missing_ok=True)
                raise RuntimeError(f"CRC32 inválido para {target.name}: recebido={actual_crc}, esperado={remote.crc32 if remote else 'desconhecido'}")
            temp_dll.replace(target)
        finally:
            if archive is not None:
                try: archive.unlink(missing_ok=True)
                except OSError: pass
            try: temp_dir.rmdir()
            except OSError: pass
        if log: log(f"CORE INSTALADO | {target} | CRC32={actual_crc}")
        return target

    @classmethod
    def detect_7zip(cls) -> Path | None:
        """Localiza 7-Zip."""
        for command in ("7z.exe", "7z", "7za.exe", "7za"):
            found = shutil.which(command)
            if found: return Path(found).resolve()
        for root in filter(None, (os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA"))):
            path = Path(root) / "7-Zip/7z.exe"
            if path.is_file(): return path.resolve()
        return None

    @classmethod
    def _download_file(cls, url: str, target: Path, progress=None, log=None) -> None:
        """Baixa um arquivo em blocos com retry."""
        target = Path(target)
        if target.exists() and target.is_dir():
            raise IsADirectoryError(f"Destino do download é um diretório, não um arquivo: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        last: Exception | None = None
        for attempt in range(1, cls.RETRIES + 1):
            try:
                if target.exists(): target.unlink()
                request = Request(url, headers={"User-Agent": "SERM/2.0", "Accept-Encoding": "identity"})
                with urlopen(request, timeout=cls.TIMEOUT) as response, target.open("wb") as output:
                    total = int(response.headers.get("Content-Length") or 0); received = 0
                    while chunk := response.read(cls.CHUNK_SIZE):
                        output.write(chunk); received += len(chunk)
                        if progress: progress(received, total)
                if received <= 0: raise RuntimeError("Download retornou zero bytes.")
                if log: log(f"DOWNLOAD | {received:,} bytes | tentativa={attempt}")
                return
            except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
                last = exc
                try: target.unlink(missing_ok=True)
                except OSError: pass
                if log: log(f"DOWNLOAD ERRO | tentativa={attempt}/{cls.RETRIES} | {exc}")
        raise RuntimeError(f"Falha no download: {url} | {last}") from last
