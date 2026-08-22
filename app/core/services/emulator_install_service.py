"""Download e instalação segura de emuladores oficiais."""
from __future__ import annotations

import logging
import shutil
import socket
import ssl
import subprocess
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

    def __init__(self, log_callback=None) -> None:
        """Inicializa o serviço com um callback opcional para diagnóstico visual."""
        self._log_callback = log_callback

    def _log(self, message: str) -> None:
        """Registra uma etapa tanto no logger quanto na interface quando disponível."""
        logger.info("Emulator install: %s", message)
        if self._log_callback is not None:
            try:
                self._log_callback(message)
            except Exception:
                logger.exception("Emulator install: falha ao enviar log para GUI")

    def release(self, emulator: str, *, nightly: bool = False) -> ReleaseInfo:
        """Obtém metadados do release oficial solicitado."""
        self._log(f"PROCURANDO RELEASE | emulator={emulator} | nightly={nightly}")
        try:
            release = latest_nightly_release(emulator) if nightly else latest_release(emulator)
        except Exception:
            logger.exception("Emulator install: falha ao consultar GitHub | emulator=%s", emulator)
            raise
        self._log(f"RELEASE ENCONTRADO | tag={release.tag} | nome={release.name} | assets={len(release.assets)}")
        return release

    def select_asset(self, release: ReleaseInfo) -> ReleaseAsset:
        """Seleciona o pacote Windows x64 oficial disponível no release."""
        self._log(f"PROCURANDO PACOTE | release={release.tag} | assets={len(release.assets)}")
        for asset in release.assets:
            self._log(f"ASSET | {asset.name} | {asset.size:,} bytes | {asset.url}")
        asset = choose_windows_x64_asset(release)
        if asset is None:
            self._log("ERRO | nenhum pacote Windows x64 compatível foi encontrado")
            raise EmulatorInstallError(f"Nenhum pacote Windows x64 foi encontrado no release {release.tag!r}.")
        self._log(f"PACOTE SELECIONADO | {asset.name} | {asset.size:,} bytes | {asset.url}")
        return asset

    def download_and_install(self, emulator: str, destination: Path, *, nightly: bool = False, progress=None) -> tuple[ReleaseInfo, ReleaseAsset, Path]:
        """Baixa, valida, extrai/instala e valida o executável final."""
        destination = Path(destination).expanduser().resolve()
        self._log(f"INÍCIO DA INSTALAÇÃO | emulator={emulator} | destino={destination}")
        try:
            destination.mkdir(parents=True, exist_ok=True)
            self._log(f"PASTA DE DESTINO PRONTA | {destination}")
            release = self.release(emulator, nightly=nightly)
            asset = self.select_asset(release)

            with tempfile.TemporaryDirectory(prefix="mame-set-builder-emu-") as temp_name:
                temp_dir = Path(temp_name)
                archive = temp_dir / asset.name
                self._log(f"ARQUIVO TEMPORÁRIO | {archive}")
                self._download(asset, archive, progress)
                size = archive.stat().st_size
                self._log(f"DOWNLOAD FINALIZADO | arquivo={archive} | recebido={size:,} bytes | esperado={asset.size:,} bytes")
                if asset.size and size != asset.size:
                    raise EmulatorInstallError(f"Download incompleto: recebido {size} bytes, esperado {asset.size}.")

                self._log(f"VALIDANDO ARQUIVO BAIXADO | {archive}")
                suffix = archive.suffix.lower()
                if suffix == ".exe":
                    self._log("PACOTE É EXECUTÁVEL | iniciando cópia para destino")
                    self._install_executable(archive, destination, emulator)
                elif suffix in {".zip", ".7z", ".7zip"}:
                    self._log(f"PACOTE COMPACTADO | extensão={suffix}")
                    extract_dir = temp_dir / "extracted"
                    extract_dir.mkdir()
                    self._log(f"INICIANDO DESCOMPACTAÇÃO SILENCIOSA | origem={archive} | destino={extract_dir}")
                    self._extract_archive(archive, extract_dir)
                    self._log("DESCOMPACTAÇÃO CONCLUÍDA | analisando estrutura do pacote")
                    source_root = self._package_root(extract_dir)
                    self._log(f"RAIZ DO PACOTE | {source_root}")
                    self._validate_root_install(source_root, emulator)
                    self._log("VALIDAÇÃO DO PACOTE CONCLUÍDA | iniciando movimentação/mesclagem")
                    self._merge_into_destination(source_root, destination)
                    self._log("MOVIMENTAÇÃO/MESCLAGEM CONCLUÍDA")
                else:
                    raise EmulatorInstallError(f"Formato de pacote não suportado: {suffix}")

            self._log("PROCURANDO EXECUTÁVEL INSTALADO NO DESTINO")
            executable = self._find_executable(destination, emulator)
            if executable is None:
                raise EmulatorInstallError(f"O pacote de {emulator} foi processado, mas nenhum executável foi encontrado diretamente no diretório selecionado.")
            self._log(f"EXECUTÁVEL ENCONTRADO | {executable}")
            self._log(f"INSTALAÇÃO VALIDADA | emulator={emulator} | release={release.tag}")
            return release, asset, executable
        except EmulatorInstallError:
            logger.exception("Emulator install: operação rejeitada | emulator=%s", emulator)
            raise
        except Exception as exc:
            logger.exception("Emulator install: falha inesperada | emulator=%s | destination=%s", emulator, destination)
            raise EmulatorInstallError(f"Falha inesperada na instalação de {emulator}: {type(exc).__name__}: {exc}") from exc

    @classmethod
    def _download(cls, asset: ReleaseAsset, target: Path, progress=None) -> None:
        """Baixa o asset em blocos com retry e diagnóstico detalhado."""
        logger.info("Emulator install: download iniciado | url=%s | target=%s", asset.url, target)
        last_error: Exception | None = None
        for attempt in range(1, cls.MAX_DOWNLOAD_RETRIES + 1):
            received = 0
            started = time.monotonic()
            try:
                logger.info("Emulator install: tentando download | attempt=%d/%d | url=%s", attempt, cls.MAX_DOWNLOAD_RETRIES, asset.url)
                request = Request(asset.url, headers={"User-Agent": "mame-set-builder/1.0", "Accept": "application/octet-stream,*/*", "Accept-Encoding": "identity"})
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
                            percent = received / total * 100.0 if total else 0.0
                            if progress:
                                progress(received, total)
                            if chunk_number == 1 or chunk_number % 10 == 0 or (total and received >= total):
                                logger.info("Emulator install: recebendo arquivo | chunk=%d | recebido=%s/%s bytes | %.2f%% | %.2f MiB/s", chunk_number, f"{received:,}", f"{total:,}", percent, speed)
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
        """Copia o executável para o destino e informa se haverá sobrescrita."""
        preferred = {"mame": "mame.exe"}.get(emulator.lower())
        target = destination / (preferred or source.name)
        logger.info("Emulator install: tentativa de abertura/cópia | source=%s | target=%s", source, target)
        logger.info("Emulator install: %s arquivo existente | target=%s", "SOBRESCREVENDO" if target.exists() else "criando novo", target)
        try:
            shutil.copy2(source, target)
            logger.info("Emulator install: arquivo copiado com sucesso | target=%s | bytes=%d", target, target.stat().st_size)
        except OSError as exc:
            logger.exception("Emulator install: falha ao copiar executável | target=%s", target)
            raise EmulatorInstallError(f"Não foi possível instalar {source.name}: {exc}") from exc

    @staticmethod
    def _find_7zip() -> str | None:
        """Localiza 7z.exe/7zz.exe sem abrir a interface do programa."""
        for name in ("7z.exe", "7zz.exe", "7za.exe"):
            found = shutil.which(name)
            if found:
                return found
        for candidate in (Path(r"C:\Program Files\7-Zip\7z.exe"), Path(r"C:\Program Files (x86)\7-Zip\7z.exe")):
            if candidate.is_file():
                return str(candidate)
        return None

    @classmethod
    def _extract_archive(cls, archive: Path, destination: Path) -> None:
        """Extrai ZIP internamente e 7z via CLI completamente oculto no Windows."""
        suffix = archive.suffix.lower()
        if suffix == ".zip":
            logger.info("Emulator install: tentando abrir ZIP | archive=%s", archive)
            if not zipfile.is_zipfile(archive):
                raise EmulatorInstallError(f"O pacote {archive.name} não é um ZIP válido.")
            try:
                with zipfile.ZipFile(archive) as zf:
                    members = zf.infolist()
                    logger.info("Emulator install: ZIP aberto | arquivos=%d", len(members))
                    base = destination.resolve()
                    for index, member in enumerate(members, start=1):
                        target = (destination / member.filename).resolve()
                        if target != base and base not in target.parents:
                            raise EmulatorInstallError("O pacote contém um caminho de extração inseguro.")
                        if index <= 20 or index == len(members):
                            logger.info("Emulator install: extraindo [%d/%d] | %s | %d bytes", index, len(members), member.filename, member.file_size)
                    zf.extractall(destination)
                logger.info("Emulator install: extração ZIP concluída | destino=%s", destination)
                return
            except zipfile.BadZipFile as exc:
                logger.exception("Emulator install: ZIP inválido | archive=%s", archive)
                raise EmulatorInstallError(f"Arquivo ZIP inválido: {archive.name}") from exc

        seven_zip = cls._find_7zip()
        if not seven_zip:
            raise EmulatorInstallError("O pacote é 7z, mas 7z.exe/7zz.exe não foi encontrado no sistema.")
        logger.info("Emulator install: 7-Zip encontrado | executable=%s", seven_zip)
        logger.info("Emulator install: abrindo pacote 7z em modo silencioso | archive=%s", archive)
        command = [seven_zip, "x", "-y", f"-o{destination}", str(archive)]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = None
        if hasattr(subprocess, "STARTUPINFO"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", shell=False, creationflags=creationflags, startupinfo=startupinfo, cwd=str(archive.parent), timeout=300, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.exception("Emulator install: falha ao executar 7-Zip silenciosamente")
            raise EmulatorInstallError(f"Não foi possível executar o 7-Zip: {exc}") from exc
        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()
        logger.info("Emulator install: 7-Zip finalizado | returncode=%s | stdout=%s | stderr=%s", result.returncode, output[-2000:], error[-2000:])
        if result.returncode != 0:
            raise EmulatorInstallError(f"7-Zip falhou durante a extração (código {result.returncode})." + (f"\n{error}" if error else f"\n{output}" if output else ""))

    @staticmethod
    def _package_root(extracted: Path) -> Path:
        """Retorna a raiz real do pacote, removendo uma única pasta empacotadora."""
        entries = list(extracted.iterdir())
        logger.info("Emulator install: conteúdo extraído | entries=%d | path=%s", len(entries), extracted)
        if len(entries) == 1 and entries[0].is_dir():
            logger.info("Emulator install: pacote possui diretório raiz | %s", entries[0])
            return entries[0]
        return extracted

    @staticmethod
    def _validate_root_install(root: Path, emulator: str) -> None:
        """Valida a existência de executável na raiz do pacote."""
        executables = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".exe"]
        logger.info("Emulator install: executáveis encontrados na raiz | count=%d | files=%s", len(executables), [p.name for p in executables])
        if not executables:
            raise EmulatorInstallError(f"O pacote de {emulator} não possui executável diretamente na raiz do pacote.")

    @staticmethod
    def _merge_into_destination(source: Path, destination: Path) -> None:
        """Mescla o pacote no destino, registrando criação e sobrescrita."""
        logger.info("Emulator install: INÍCIO DA MOVIMENTAÇÃO | source=%s | destination=%s", source, destination)
        for item in source.iterdir():
            EmulatorInstallService._copy_tree_item(item, destination / item.name)
        logger.info("Emulator install: FIM DA MOVIMENTAÇÃO | destination=%s", destination)

    @staticmethod
    def _copy_tree_item(source: Path, target: Path) -> None:
        """Copia recursivamente e informa cada criação/sobrescrita relevante."""
        if source.is_dir():
            logger.info("Emulator install: diretório | %s -> %s", source, target)
            target.mkdir(parents=True, exist_ok=True)
            for child in source.iterdir():
                EmulatorInstallService._copy_tree_item(child, target / child.name)
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Emulator install: %s | %s | bytes=%d", "SOBRESCREVENDO" if target.exists() else "CRIANDO", target, source.stat().st_size)
        shutil.copy2(source, target)

    @staticmethod
    def _find_executable(destination: Path, emulator: str) -> Path | None:
        """Localiza o executável somente na raiz da instalação."""
        preferred = {"mame": ("mame.exe",), "flycast": ("flycast.exe",), "supermodel": ("supermodel.exe", "Supermodel.exe", "supermodel3.exe"), "fbneo": ("fbneo.exe", "FBNeo.exe", "fba64.exe", "fba.exe")}.get(emulator.strip().lower(), ())
        for name in preferred:
            candidate = destination / name
            if candidate.is_file():
                return candidate
        executables = sorted(p for p in destination.iterdir() if p.is_file() and p.suffix.lower() == ".exe")
        return executables[0] if len(executables) == 1 else None
