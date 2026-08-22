"""Download e instalação segura de emuladores oficiais."""
from __future__ import annotations

import logging
import shutil
import socket
import ssl
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.services.emulator_download_service import (
    ReleaseAsset,
    ReleaseInfo,
    choose_windows_x64_asset,
    latest_nightly_release,
    latest_release,
)

logger = logging.getLogger(__name__)


class EmulatorInstallError(RuntimeError):
    """Erro controlado durante download ou instalação."""


class EmulatorInstallService:
    """Instala pacotes Windows x64 diretamente no diretório escolhido."""

    DOWNLOAD_CHUNK_SIZE = 1024 * 1024
    DOWNLOAD_TIMEOUT = 60
    MAX_DOWNLOAD_RETRIES = 3

    def release(self, emulator: str, *, nightly: bool = False) -> ReleaseInfo:
        """Obtém metadados do release oficial solicitado e registra diagnóstico."""
        logger.info("Emulator install: consultando release | emulator=%s | nightly=%s", emulator, nightly)
        try:
            release = latest_nightly_release(emulator) if nightly else latest_release(emulator)
        except Exception:
            logger.exception("Emulator install: falha ao consultar GitHub | emulator=%s", emulator)
            raise
        logger.info("Emulator install: release encontrado | emulator=%s | tag=%s | assets=%d", emulator, release.tag, len(release.assets))
        return release

    def select_asset(self, release: ReleaseInfo) -> ReleaseAsset:
        """Seleciona o pacote Windows x64 oficial disponível no release."""
        logger.info("Emulator install: avaliando assets | emulator=%s | release=%s", release.emulator, release.tag)
        for asset in release.assets:
            logger.debug("Emulator install: asset=%s | size=%d | url=%s", asset.name, asset.size, asset.url)
        asset = choose_windows_x64_asset(release)
        if asset is None:
            logger.error("Emulator install: nenhum asset Windows x64 selecionado | emulator=%s | release=%s", release.emulator, release.tag)
            raise EmulatorInstallError(f"Nenhum pacote Windows x64 foi encontrado no release {release.tag!r}.")
        logger.info("Emulator install: asset selecionado | emulator=%s | asset=%s | size=%d", release.emulator, asset.name, asset.size)
        return asset

    def download_and_install(self, emulator: str, destination: Path, *, nightly: bool = False, progress=None) -> tuple[ReleaseInfo, ReleaseAsset, Path]:
        """Baixa, valida e instala sem destruir a instalação existente."""
        destination = Path(destination).expanduser().resolve()
        logger.info("Emulator install: início | emulator=%s | destination=%s", emulator, destination)
        try:
            destination.mkdir(parents=True, exist_ok=True)
            release = self.release(emulator, nightly=nightly)
            asset = self.select_asset(release)

            with tempfile.TemporaryDirectory(prefix="mame-set-builder-emu-") as temp_name:
                temp_dir = Path(temp_name)
                archive = temp_dir / asset.name
                self._download(asset, archive, progress)
                size = archive.stat().st_size
                logger.info("Emulator install: download concluído | emulator=%s | file=%s | bytes=%d", emulator, archive, size)
                if asset.size and size != asset.size:
                    raise EmulatorInstallError(f"Download incompleto: recebido {size} bytes, esperado {asset.size}.")

                if archive.suffix.lower() == ".exe":
                    self._install_executable(archive, destination, emulator)
                else:
                    extract_dir = temp_dir / "extracted"
                    extract_dir.mkdir()
                    self._extract_archive(archive, extract_dir)
                    source_root = self._package_root(extract_dir)
                    self._validate_root_install(source_root, emulator)
                    self._merge_into_destination(source_root, destination)

            executable = self._find_executable(destination, emulator)
            if executable is None:
                raise EmulatorInstallError(f"O pacote de {emulator} foi processado, mas nenhum executável foi encontrado diretamente no diretório selecionado.")
            logger.info("Emulator install: instalação validada | emulator=%s | executable=%s | release=%s", emulator, executable, release.tag)
            return release, asset, executable
        except EmulatorInstallError:
            logger.exception("Emulator install: operação rejeitada | emulator=%s", emulator)
            raise
        except Exception as exc:
            logger.exception("Emulator install: falha inesperada | emulator=%s | destination=%s", emulator, destination)
            raise EmulatorInstallError(f"Falha inesperada na instalação de {emulator}: {type(exc).__name__}: {exc}") from exc

    @classmethod
    def _download(cls, asset: ReleaseAsset, target: Path, progress=None) -> None:
        """Baixa o asset em blocos, com retry e diagnóstico por bloco, sem carregar o arquivo na memória."""
        logger.info("Emulator install: download iniciado | url=%s | target=%s", asset.url, target)
        last_error: Exception | None = None

        for attempt in range(1, cls.MAX_DOWNLOAD_RETRIES + 1):
            received = 0
            started = time.monotonic()
            try:
                request = Request(
                    asset.url,
                    headers={
                        "User-Agent": "mame-set-builder/1.0",
                        "Accept": "application/octet-stream,*/*",
                        "Accept-Encoding": "identity",
                    },
                )
                logger.info("Emulator install: conexão | attempt=%d/%d | url=%s", attempt, cls.MAX_DOWNLOAD_RETRIES, asset.url)
                with urlopen(request, timeout=cls.DOWNLOAD_TIMEOUT, context=ssl.create_default_context()) as response:
                    total_header = response.headers.get("Content-Length")
                    total = int(total_header) if total_header and total_header.isdigit() else int(asset.size or 0)
                    status = getattr(response, "status", None)
                    logger.info("Emulator install: conexão estabelecida | status=%s | total=%d | content-type=%s", status, total, response.headers.get("Content-Type"))
                    if status is not None and status >= 400:
                        raise EmulatorInstallError(f"Servidor retornou HTTP {status}.")

                    with target.open("wb") as output:
                        chunk_number = 0
                        while True:
                            try:
                                chunk = response.read(cls.DOWNLOAD_CHUNK_SIZE)
                            except socket.timeout as exc:
                                raise EmulatorInstallError(f"Timeout durante leitura após {received} bytes.") from exc
                            if not chunk:
                                break
                            output.write(chunk)
                            output.flush()
                            received += len(chunk)
                            chunk_number += 1
                            elapsed = max(time.monotonic() - started, 0.001)
                            speed = received / elapsed / (1024 * 1024)
                            logger.info("Emulator install: chunk=%d | received=%d | total=%d | progress=%.2f%% | speed=%.2f MiB/s", chunk_number, received, total, (received / total * 100.0) if total else 0.0, speed)
                            if progress:
                                progress(received, total)

                logger.info("Emulator install: stream encerrado | received=%d | expected=%d", received, total)
                if total and received != total:
                    raise EmulatorInstallError(f"Download incompleto: recebido {received} bytes, esperado {total}.")
                if received <= 0:
                    raise EmulatorInstallError("Download retornou zero bytes.")
                return
            except (HTTPError, URLError, TimeoutError, socket.timeout, OSError, EmulatorInstallError) as exc:
                last_error = exc
                logger.exception("Emulator install: falha no download | attempt=%d/%d | received=%d", attempt, cls.MAX_DOWNLOAD_RETRIES, received)
                try:
                    if target.exists():
                        target.unlink()
                except OSError:
                    logger.warning("Emulator install: não foi possível remover download parcial | target=%s", target)
                if attempt < cls.MAX_DOWNLOAD_RETRIES:
                    delay = attempt * 2
                    logger.info("Emulator install: retry em %ds | attempt=%d/%d", delay, attempt + 1, cls.MAX_DOWNLOAD_RETRIES)
                    time.sleep(delay)
            except Exception as exc:
                logger.exception("Emulator install: falha não prevista no stream | attempt=%d/%d | received=%d", attempt, cls.MAX_DOWNLOAD_RETRIES, received)
                last_error = exc
                break

        raise EmulatorInstallError(f"Falha no download de {asset.name} após {cls.MAX_DOWNLOAD_RETRIES} tentativa(s): {type(last_error).__name__}: {last_error}") from last_error

    @staticmethod
    def _install_executable(source: Path, destination: Path, emulator: str) -> None:
        """Instala um executável oficial, como o pacote do MAME."""
        preferred = {"mame": "mame.exe"}.get(emulator.lower())
        target = destination / (preferred or source.name)
        logger.info("Emulator install: copiando executável | source=%s | target=%s", source, target)
        try:
            shutil.copy2(source, target)
        except OSError as exc:
            logger.exception("Emulator install: falha ao copiar executável | target=%s", target)
            raise EmulatorInstallError(f"Não foi possível instalar {source.name}: {exc}") from exc

    @staticmethod
    def _extract_archive(archive: Path, destination: Path) -> None:
        """Extrai um ZIP sem permitir escrita fora da área temporária."""
        logger.info("Emulator install: extraindo ZIP | archive=%s", archive)
        if not zipfile.is_zipfile(archive):
            raise EmulatorInstallError(f"O pacote {archive.name} não é um ZIP compatível com a instalação automática.")
        try:
            with zipfile.ZipFile(archive) as zf:
                base = destination.resolve()
                for member in zf.infolist():
                    target = (destination / member.filename).resolve()
                    if target != base and base not in target.parents:
                        raise EmulatorInstallError("O pacote contém um caminho de extração inseguro.")
                zf.extractall(destination)
        except zipfile.BadZipFile as exc:
            raise EmulatorInstallError(f"Arquivo ZIP inválido: {archive.name}") from exc

    @staticmethod
    def _package_root(extracted: Path) -> Path:
        """Retorna a raiz real do pacote, removendo uma única pasta empacotadora."""
        entries = list(extracted.iterdir())
        if len(entries) == 1 and entries[0].is_dir():
            return entries[0]
        return extracted

    @staticmethod
    def _validate_root_install(root: Path, emulator: str) -> None:
        """Garante que o pacote possui executável diretamente em sua raiz."""
        executables = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".exe"]
        if not executables:
            raise EmulatorInstallError(f"O pacote de {emulator} não possui executável diretamente na raiz do pacote.")

    @staticmethod
    def _merge_into_destination(source: Path, destination: Path) -> None:
        """Mescla o conteúdo da raiz do pacote no diretório configurado."""
        logger.info("Emulator install: mesclando pacote | source=%s | destination=%s", source, destination)
        for item in source.iterdir():
            target = destination / item.name
            if item.is_dir():
                if target.exists() and target.is_dir():
                    for child in item.iterdir():
                        EmulatorInstallService._copy_tree_item(child, target / child.name)
                else:
                    shutil.copytree(item, target)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)

    @staticmethod
    def _copy_tree_item(source: Path, target: Path) -> None:
        """Mescla um item preservando a estrutura interna."""
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            for child in source.iterdir():
                EmulatorInstallService._copy_tree_item(child, target / child.name)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    @staticmethod
    def _find_executable(destination: Path, emulator: str) -> Path | None:
        """Localiza o executável somente na raiz da instalação."""
        preferred = {"mame": ("mame.exe",), "flycast": ("flycast.exe",), "supermodel": ("supermodel.exe", "Supermodel.exe", "supermodel3.exe"), "fbneo": ("fbneo.exe", "fba.exe", "fba64.exe")}.get(emulator.strip().lower(), ())
        for name in preferred:
            candidate = destination / name
            if candidate.is_file():
                return candidate
        executables = sorted(p for p in destination.iterdir() if p.is_file() and p.suffix.lower() == ".exe")
        return executables[0] if len(executables) == 1 else None
