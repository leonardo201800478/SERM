"""Downloader oficial do RetroArch e dos cores libretro para Windows.

A arquitetura segue o modelo usado pelo Stellar: o Buildbot é a fonte de
verdade, o ``.index-extended`` é usado para descobrir versões/data/CRC dos
cores e os arquivos são baixados para TEMP antes da instalação.

Não usamos GitHub Releases para RetroArch. O projeto oficial distribui os
pacotes Windows pelo Libretro Buildbot, inclusive Stable e Nightly.
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
from datetime import datetime, timezone
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
        """Retorna o nome lógico do core sem sufixos de plataforma e compactação."""
        name = self.filename
        if name.endswith(".zip"):
            name = name[:-4]
        return re.sub(r"_libretro(?:_[^.]+)?$", "", name)


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
        versions = set(re.findall(r'href=[\"\']([0-9]+\.[0-9]+(?:\.[0-9]+)*)/[\"\']', html))
        return sorted(versions, key=lambda value: tuple(int(x) for x in value.split(".")), reverse=True)

    @classmethod
    def discover_nightly_archive(cls) -> tuple[str, int, str]:
        """Localiza o ``RetroArch.7z`` mais recente no diretório Nightly Windows x64."""
        base = f"{cls.BUILD_ROOT}/nightly/windows/{cls.WINDOWS_ARCH}/"
        html = cls._download_text(base)
        matches = re.findall(
            r'href=[\"\'](\d{4}-\d{2}-\d{2}_RetroArch\.7z)[\"\'][^>]*>.*?</a>\s*([^<]*)',
            html,
            re.IGNORECASE | re.DOTALL,
        )
        if not matches:
            raise RetroArchDownloadError("Não foi possível localizar o RetroArch.7z Nightly no Buildbot.")
        filename = sorted(item[0] for item in matches)[-1]
        url = base + filename
        return filename, 0, url

    def list_cores(self, channel: RetroArchChannel) -> list[RetroArchCoreInfo]:
        """Lê ``.index-extended`` e retorna todos os cores Windows x64 publicados."""
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
            result.append(RetroArchCoreInfo(filename=filename, date=date, crc32=crc.lower()))
        result.sort(key=lambda item: item.core_name.casefold())
        if not result:
            raise RetroArchDownloadError(f"O índice de cores não contém DLLs válidas: {index_url}")
        self._log(f"ÍNDICE DE CORES CARREGADO | cores={len(result)}")
        return result

    def core_url(self, channel: RetroArchChannel, core: RetroArchCoreInfo) -> str:
        """Monta a URL oficial do ZIP de um core."""
        return channel.base_url + core.filename

    def download_retroarch(self, channel: RetroArchChannel, destination: Path, progress=None) -> Path:
        """Baixa o pacote RetroArch.7z para TEMP e retorna o arquivo temporário."""
        filename = "RetroArch.7z"
        if channel.name.casefold() == "nightly":
            filename, _, url = self.discover_nightly_archive()
        else:
            url = channel.base_url + filename
        temp = Path(tempfile.mkdtemp(prefix="mame-set-builder-retroarch-"))
        archive = temp / filename
        self._log(f"DOWNLOAD RETROARCH | canal={channel.name} | url={url}")
        self._download(url, archive, progress)
        return archive

    def install_retroarch(self, archive: Path, destination: Path, preserve_config: bool = True) -> Path:
        """Extrai RetroArch no destino e preserva configuração/dados existentes."""
        destination = Path(destination).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)
        temp_extract = archive.parent / "extracted"
        temp_extract.mkdir(parents=True, exist_ok=True)
        self._extract_7z(archive, temp_extract)

        excluded = {
            "config", "saves", "states", "retroarch.cfg", "retroarch.default.cfg",
        } if preserve_config else set()
        self._merge(temp_extract, destination, excluded)
        executable = destination / "retroarch.exe"
        if not executable.is_file():
            raise RetroArchDownloadError(f"retroarch.exe não encontrado após instalação: {destination}")
        return executable

    def download_core(self, channel: RetroArchChannel, core: RetroArchCoreInfo, cores_dir: Path, progress=None) -> Path:
        """Baixa e instala um único core libretro no diretório ``cores``."""
        cores_dir = Path(cores_dir).expanduser().resolve()
        cores_dir.mkdir(parents=True, exist_ok=True)
        temp = Path(tempfile.mkdtemp(prefix="mame-set-builder-core-"))
        archive = temp / core.filename
        url = self.core_url(channel, core)
        self._log(f"DOWNLOAD CORE | {core.core_name} | url={url}")
        try:
            self._download(url, archive, progress)
            expected = core.crc32
            actual = f"{self._crc32(archive):08x}"
            if expected and expected != actual:
                raise RetroArchDownloadError(
                    f"CRC32 inválido para {core.filename}: recebido={actual}, índice={expected}"
                )
            self._extract_7z(archive, cores_dir)
            dll = cores_dir / core.filename[:-4]
            if not dll.is_file():
                candidates = list(cores_dir.glob(f"{core.core_name}*_libretro.dll"))
                if not candidates:
                    raise RetroArchDownloadError(f"Core instalado sem DLL esperada: {core.filename}")
                dll = candidates[0]
            return dll
        finally:
            shutil.rmtree(temp, ignore_errors=True)

    @classmethod
    def _download(cls, url: str, target: Path, progress=None) -> None:
        """Baixa em blocos com retry e valida tamanho quando o servidor informa Content-Length."""
        last: Exception | None = None
        for attempt in range(1, cls.RETRIES + 1):
            received = 0
            try:
                request = Request(
                    url,
                    headers={
                        "User-Agent": "mame-set-builder RetroArch downloader",
                        "Accept": "application/octet-stream,*/*",
                        "Accept-Encoding": "identity",
                    },
                )
                with urlopen(request, timeout=cls.TIMEOUT, context=ssl.create_default_context()) as response:
                    total_header = response.headers.get("Content-Length")
                    total = int(total_header) if total_header and total_header.isdigit() else 0
                    with target.open("wb") as output:
                        while True:
                            chunk = response.read(cls.CHUNK_SIZE)
                            if not chunk:
                                break
                            output.write(chunk)
                            received += len(chunk)
                            if progress:
                                progress(received, total)
                if received <= 0:
                    raise RetroArchDownloadError(f"Download vazio: {url}")
                if total and received != total:
                    raise RetroArchDownloadError(
                        f"Download incompleto: recebido={received}, esperado={total}"
                    )
                return
            except (HTTPError, URLError, TimeoutError, OSError, RetroArchDownloadError) as exc:
                last = exc
                target.unlink(missing_ok=True)
                if attempt < cls.RETRIES:
                    time.sleep(attempt * 2)
        raise RetroArchDownloadError(
            f"Falha no download após {cls.RETRIES} tentativa(s): {type(last).__name__}: {last}"
        ) from last

    @staticmethod
    def _download_text(url: str) -> str:
        """Obtém texto UTF-8 do Buildbot usando HTTPS."""
        request = Request(url, headers={"User-Agent": "mame-set-builder RetroArch downloader"})
        with urlopen(request, timeout=60, context=ssl.create_default_context()) as response:
            return response.read().decode("utf-8", errors="replace")

    @staticmethod
    def _crc32(path: Path) -> int:
        """Calcula CRC32 do arquivo baixado sem carregá-lo inteiro na memória."""
        value = 0
        with Path(path).open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                value = binascii.crc32(chunk, value)
        return value & 0xFFFFFFFF

    @staticmethod
    def _find_7zip() -> str:
        """Localiza 7z.exe/7zz.exe no PATH ou nas instalações padrão do Windows."""
        for name in ("7z.exe", "7zz.exe", "7za.exe"):
            found = shutil.which(name)
            if found:
                return found
        for path in (
            Path(r"C:\Program Files\7-Zip\7z.exe"),
            Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
        ):
            if path.is_file():
                return str(path)
        raise RetroArchDownloadError("7-Zip não encontrado. Instale 7-Zip para extrair RetroArch e cores.")

    @classmethod
    def _extract_7z(cls, archive: Path, destination: Path) -> None:
        """Extrai um pacote 7z silenciosamente, sem executar seu conteúdo."""
        seven_zip = cls._find_7zip()
        command = [seven_zip, "x", "-y", f"-o{destination}", str(archive)]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            creationflags=creationflags,
            timeout=600,
            check=False,
        )
        if result.returncode != 0:
            raise RetroArchDownloadError(
                f"7-Zip falhou ao extrair {archive.name}: {(result.stderr or result.stdout).strip()}"
            )

    @staticmethod
    def _merge(source: Path, destination: Path, excluded: set[str]) -> None:
        """Mescla uma árvore extraída sem substituir dados protegidos."""
        source = Path(source).resolve()
        destination = Path(destination).resolve()
        for item in source.rglob("*"):
            relative = item.relative_to(source)
            if relative.parts and relative.parts[0].casefold() in {x.casefold() for x in excluded}:
                continue
            if relative.name.casefold() in {x.casefold() for x in excluded}:
                continue
            target = destination / relative
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
