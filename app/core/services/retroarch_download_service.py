"""Downloader oficial do RetroArch e dos cores libretro para Windows.

O Buildbot oficial é a fonte de verdade. Pacotes do RetroArch são baixados
para TEMP, extraídos e mesclados na raiz escolhida pelo usuário. Os cores
libretro são arquivos ZIP; o CRC publicado no .index-extended é validado
contra a DLL contida no ZIP, não contra o contêiner ZIP.
"""
from __future__ import annotations

import binascii
import logging
import re
import shutil
import ssl
import subprocess
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class RetroArchDownloadError(RuntimeError):
    """Erro controlado do downloader do RetroArch."""


@dataclass(frozen=True, slots=True)
class RetroArchChannel:
    """Canal de distribuição selecionado pelo usuário."""

    name: str
    base_url: str
    version: str | None


@dataclass(frozen=True, slots=True)
class RetroArchCoreInfo:
    """Metadados publicados pelo ``.index-extended`` de um core."""

    filename: str
    date: str
    crc32: str

    @property
    def core_name(self) -> str:
        """Retorna o nome lógico do core sem sufixo libretro e compactação."""
        name = self.filename.removesuffix(".zip")
        return re.sub(r"_libretro(?:_[^.]+)?$", "", name)


@dataclass(frozen=True, slots=True)
class InstalledCoreInfo:
    """Estado local de um core comparado ao índice oficial."""

    path: Path
    core_name: str
    local_crc32: str
    remote_crc32: str | None

    @property
    def needs_update(self) -> bool:
        """Indica se o core local difere do CRC publicado."""
        return self.remote_crc32 is not None and self.local_crc32 != self.remote_crc32

    @property
    def is_current(self) -> bool:
        """Indica se o CRC local é exatamente o publicado pelo Buildbot."""
        return self.remote_crc32 is not None and self.local_crc32 == self.remote_crc32


class RetroArchDownloadService:
    """Consulta o Buildbot, baixa e instala RetroArch/cores com segurança."""

    BUILD_ROOT = "https://buildbot.libretro.com"
    WINDOWS_ARCH = "x86_64"
    CHUNK_SIZE = 1024 * 1024
    TIMEOUT = 60
    RETRIES = 3

    def __init__(self, log_callback=None) -> None:
        """Inicializa o serviço com callback opcional de diagnóstico."""
        self._log_callback = log_callback

    def _log(self, message: str) -> None:
        """Registra a etapa e encaminha a mensagem à GUI quando disponível."""
        logger.info("RetroArch downloader: %s", message)
        if self._log_callback is not None:
            self._log_callback(message)

    @classmethod
    def channel(cls, mode: str, stable_version: str | None = None) -> RetroArchChannel:
        """Resolve a URL oficial do canal Stable ou Nightly."""
        normalized = mode.strip().casefold()
        if normalized == "stable":
            if not stable_version:
                raise RetroArchDownloadError("A versão Stable do RetroArch não foi informada.")
            base = f"{cls.BUILD_ROOT}/stable/{stable_version}/windows/{cls.WINDOWS_ARCH}/"
            return RetroArchChannel("Stable", base, stable_version)
        if normalized == "nightly":
            base = f"{cls.BUILD_ROOT}/nightly/windows/{cls.WINDOWS_ARCH}/latest/"
            return RetroArchChannel("Nightly", base, None)
        raise RetroArchDownloadError(f"Canal RetroArch inválido: {mode!r}")

    @classmethod
    def discover_stable_versions(cls) -> list[str]:
        """Consulta o diretório Stable oficial e retorna versões em ordem decrescente."""
        html = cls._download_text(f"{cls.BUILD_ROOT}/stable/")
        versions: set[str] = set()
        for href in re.findall(r"href=[\"']([^\"']+)[\"']", html, re.IGNORECASE):
            value = href.strip().strip("/")
            match = re.search(r"(?:^|/)v?(\d+\.\d+(?:\.\d+)*)$", value)
            if match:
                versions.add(match.group(1))
        if not versions:
            for match in re.findall(r"(?:^|/)v?(\d+\.\d+(?:\.\d+)*)(?:/|\\|\"|')", html):
                versions.add(match)
        return sorted(versions, key=cls._version_key, reverse=True)

    @staticmethod
    def _version_key(value: str) -> tuple[int, ...]:
        """Converte versão semântica simples em chave ordenável."""
        return tuple(int(part) for part in value.split("."))

    @classmethod
    def discover_nightly_archive(cls) -> tuple[str, int, str]:
        """Localiza o último pacote RetroArch datado no Nightly Windows x64."""
        base = f"{cls.BUILD_ROOT}/nightly/windows/{cls.WINDOWS_ARCH}/"
        html = cls._download_text(base)
        filenames = []
        for href in re.findall(r"href=[\"']([^\"']+)[\"']", html, re.IGNORECASE):
            name = href.rsplit("/", 1)[-1]
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}_RetroArch\.7z", name, re.IGNORECASE):
                filenames.append(name)
        if not filenames:
            raise RetroArchDownloadError("Não foi possível localizar um pacote RetroArch.7z datado no Buildbot Nightly Windows x64.")
        filename = max(filenames, key=lambda value: value[:10])
        return filename, 0, base + filename

    @classmethod
    def detect_installed_version(cls, executable: Path) -> str | None:
        """Obtém a versão real do RetroArch executando o próprio executável."""
        executable = Path(executable).expanduser().resolve()
        if not executable.is_file():
            return None
        for args in (("--version",), ("-v",)):
            try:
                result = subprocess.run([str(executable), *args], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=15, check=False, cwd=str(executable.parent))
            except (OSError, subprocess.SubprocessError):
                continue
            match = re.search(r"\b(\d+\.\d+(?:\.\d+)*)\b", (result.stdout or "").strip())
            if match:
                return match.group(1)
        return None

    def list_cores(self, channel: RetroArchChannel) -> list[RetroArchCoreInfo]:
        """Lê .index-extended e retorna todos os cores Windows x64 publicados."""
        index_url = channel.base_url + ".index-extended"
        self._log(f"CONSULTANDO ÍNDICE DE CORES | {index_url}")
        text = self._download_text(index_url)
        result: list[RetroArchCoreInfo] = []
        for line in text.splitlines():
            parts = line.strip().split()
            if len(parts) < 3:
                continue
            date, crc, filename = parts[0], parts[1], parts[2]
            if not filename.endswith("_libretro.dll.zip"):
                continue
            result.append(RetroArchCoreInfo(filename=filename, date=date, crc32=crc.lower().removeprefix("0x").zfill(8)))
        result.sort(key=lambda item: item.core_name.casefold())
        if not result:
            raise RetroArchDownloadError(f"O índice de cores não contém DLLs válidas: {index_url}")
        self._log(f"ÍNDICE DE CORES CARREGADO | cores={len(result)}")
        return result

    def core_url(self, channel: RetroArchChannel, core: RetroArchCoreInfo) -> str:
        """Monta a URL oficial do ZIP de um core."""
        return channel.base_url + core.filename

    def download_retroarch(self, channel: RetroArchChannel, destination: Path, progress=None) -> Path:
        """Baixa o pacote RetroArch para TEMP e retorna o arquivo temporário."""
        if channel.name.casefold() == "nightly":
            filename, _, url = self.discover_nightly_archive()
        else:
            filename = "RetroArch.7z"
            url = channel.base_url + filename
        temp = Path(tempfile.mkdtemp(prefix="mame-set-builder-retroarch-"))
        archive = temp / filename
        self._log(f"DOWNLOAD RETROARCH | canal={channel.name} | url={url}")
        self._download(url, archive, progress)
        return archive

    def install_retroarch(self, archive: Path, destination: Path, preserve_config: bool = True) -> Path:
        """Extrai RetroArch e achata uma pasta raiz do pacote antes de mesclar."""
        destination = Path(destination).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        temp_extract = archive.parent / "extracted"
        temp_extract.mkdir(parents=True, exist_ok=True)
        self._extract_7z(archive, temp_extract)
        source = self._flatten_single_root(temp_extract)
        excluded = {"config", "saves", "states", "retroarch.cfg", "retroarch.default.cfg"} if preserve_config else set()
        self._merge(source, destination, excluded)
        executable = destination / "retroarch.exe"
        if not executable.is_file():
            raise RetroArchDownloadError(f"retroarch.exe não encontrado após instalação na raiz: {destination}")
        return executable

    @staticmethod
    def _flatten_single_root(source: Path) -> Path:
        """Retorna a árvore útil, removendo o nível único RetroArch-Win64 quando existir."""
        entries = [item for item in source.iterdir() if item.name != "__MACOSX"]
        if len(entries) == 1 and entries[0].is_dir() and (entries[0] / "retroarch.exe").is_file():
            return entries[0]
        return source

    def download_core(self, channel: RetroArchChannel, core: RetroArchCoreInfo, cores_dir: Path, progress=None) -> Path:
        """Baixa um core, valida a DLL contra o CRC do índice e instala somente a DLL."""
        cores_dir = Path(cores_dir).expanduser().resolve()
        cores_dir.mkdir(parents=True, exist_ok=True)
        temp = Path(tempfile.mkdtemp(prefix="mame-set-builder-core-"))
        archive = temp / core.filename
        try:
            self._log(f"DOWNLOAD CORE | {core.filename} | url={self.core_url(channel, core)}")
            self._download(self.core_url(channel, core), archive, progress)
            dll = self._extract_core_to_temp(archive, temp / "core")
            expected = core.crc32.lower().removeprefix("0x").zfill(8)
            actual = f"{self._crc32(dll):08x}"
            self._log(f"CRC CORE | {dll.name} | recebido={actual} | índice={expected}")
            if expected and expected != actual:
                raise RetroArchDownloadError(f"CRC32 inválido para {dll.name}: recebido={actual}, índice={expected}")
            target = cores_dir / dll.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dll, target)
            self._log(f"CORE INSTALADO | {target}")
            return target
        finally:
            shutil.rmtree(temp, ignore_errors=True)

    @staticmethod
    def _extract_core_to_temp(archive: Path, destination: Path) -> Path:
        """Extrai o ZIP em área temporária e retorna a DLL do core."""
        destination.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(archive, "r") as package:
                bad = package.testzip()
                if bad:
                    raise RetroArchDownloadError(f"ZIP corrompido do core: {bad}")
                dll_names = [name for name in package.namelist() if name.lower().endswith("_libretro.dll")]
                if not dll_names:
                    raise RetroArchDownloadError(f"ZIP sem DLL libretro: {archive.name}")
                package.extract(dll_names[0], destination)
                extracted = destination / dll_names[0]
                if not extracted.is_file():
                    raise RetroArchDownloadError(f"DLL não encontrada após extração: {dll_names[0]}")
                return extracted
        except zipfile.BadZipFile as exc:
            raise RetroArchDownloadError(f"Arquivo de core não é um ZIP válido: {archive.name}") from exc

    @staticmethod
    def installed_cores(cores_dir: Path) -> list[Path]:
        """Lista somente DLLs libretro presentes no diretório real configurado."""
        path = Path(cores_dir).expanduser().resolve()
        if not path.is_dir():
            return []
        return sorted(path.glob("*_libretro.dll"), key=lambda item: item.name.casefold())

    @classmethod
    def compare_installed_cores(cls, cores: list[RetroArchCoreInfo], cores_dir: Path) -> list[InstalledCoreInfo]:
        """Calcula CRC32 local e compara cada DLL instalada ao índice oficial.

        Cores sem correspondência no índice também são retornados, mas com
        ``remote_crc32=None`` para que nunca sejam substituídos automaticamente.
        """
        remote = {core.filename.removesuffix(".zip").casefold(): core for core in cores}
        result: list[InstalledCoreInfo] = []
        for path in cls.installed_cores(cores_dir):
            local_crc = f"{cls._crc32(path):08x}"
            core = remote.get(path.name.casefold())
            result.append(
                InstalledCoreInfo(
                    path=path,
                    core_name=path.stem.removesuffix("_libretro"),
                    local_crc32=local_crc,
                    remote_crc32=core.crc32.lower().removeprefix("0x").zfill(8) if core else None,
                )
            )
        return result

    @classmethod
    def match_installed_cores(cls, cores: list[RetroArchCoreInfo], cores_dir: Path) -> list[RetroArchCoreInfo]:
        """Retorna cores instalados que realmente precisam de atualização por CRC."""
        remote = {core.filename.removesuffix(".zip").casefold(): core for core in cores}
        comparisons = cls.compare_installed_cores(cores, cores_dir)
        return [remote[item.path.name.casefold()] for item in comparisons if item.needs_update]

    @staticmethod
    def _download(url: str, target: Path, progress=None) -> None:
        """Baixa em blocos com retry e valida tamanho quando informado."""
        last: Exception | None = None
        for attempt in range(1, 4):
            received = 0
            try:
                request = Request(url, headers={"User-Agent": "mame-set-builder RetroArch downloader", "Accept": "application/octet-stream,*/*", "Accept-Encoding": "identity"})
                with urlopen(request, timeout=60, context=ssl.create_default_context()) as response:
                    total_header = response.headers.get("Content-Length")
                    total = int(total_header) if total_header and total_header.isdigit() else 0
                    with target.open("wb") as output:
                        while True:
                            chunk = response.read(1024 * 1024)
                            if not chunk:
                                break
                            output.write(chunk)
                            received += len(chunk)
                            if progress:
                                progress(received, total)
                if received <= 0:
                    raise RetroArchDownloadError(f"Download vazio: {url}")
                if total and received != total:
                    raise RetroArchDownloadError(f"Download incompleto: recebido={received}, esperado={total}")
                return
            except (HTTPError, URLError, TimeoutError, OSError, RetroArchDownloadError) as exc:
                last = exc
                target.unlink(missing_ok=True)
                if attempt < 3:
                    time.sleep(attempt * 2)
        raise RetroArchDownloadError(f"Falha no download após 3 tentativa(s): {type(last).__name__}: {last}") from last

    @staticmethod
    def _download_text(url: str) -> str:
        """Obtém texto UTF-8 do Buildbot usando HTTPS."""
        request = Request(url, headers={"User-Agent": "mame-set-builder RetroArch downloader", "Accept": "text/html,text/plain,*/*"})
        with urlopen(request, timeout=60, context=ssl.create_default_context()) as response:
            return response.read().decode("utf-8", errors="replace")

    @staticmethod
    def _crc32(path: Path) -> int:
        """Calcula CRC32 sem carregar o arquivo inteiro na memória."""
        value = 0
        with Path(path).open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                value = binascii.crc32(chunk, value)
        return value & 0xFFFFFFFF

    @staticmethod
    def _find_7zip() -> str:
        """Localiza 7z.exe/7zz.exe/7za.exe no PATH ou instalações padrão."""
        for name in ("7z.exe", "7zz.exe", "7za.exe"):
            found = shutil.which(name)
            if found:
                return found
        for path in (Path(r"C:\Program Files\7-Zip\7z.exe"), Path(r"C:\Program Files\7-Zip\7zz.exe"), Path(r"C:\Program Files\7-Zip\7za.exe")):
            if path.is_file():
                return str(path)
        raise RetroArchDownloadError("7-Zip não encontrado. Instale o 7-Zip ou adicione 7z.exe ao PATH.")

    @classmethod
    def _extract_7z(cls, archive: Path, destination: Path) -> None:
        """Extrai um pacote 7z com 7-Zip sem executar shell."""
        seven_zip = cls._find_7zip()
        result = subprocess.run([seven_zip, "x", str(archive), f"-o{destination}", "-y"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", shell=False, check=False)
        if result.returncode != 0:
            raise RetroArchDownloadError(f"Falha ao extrair {archive.name}: {result.stdout[-4000:]}")

    @staticmethod
    def _merge(source: Path, destination: Path, excluded: set[str]) -> None:
        """Mescla uma árvore de instalação preservando entradas excluídas."""
        for item in source.iterdir():
            if item.name.casefold() in {value.casefold() for value in excluded}:
                continue
            target = destination / item.name
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                RetroArchDownloadService._merge(item, target, set())
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
