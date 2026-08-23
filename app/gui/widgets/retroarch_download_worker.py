"""Worker Qt para download do RetroArch e dos cores libretro."""
from __future__ import annotations

import traceback
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.config.app_config import AppConfig
from app.core.services.retroarch_download_service import RetroArchDownloadService


class RetroArchDownloadWorker(QObject):
    """Executa downloads do Buildbot fora da thread da GUI."""

    progress = Signal(int, int)
    status = Signal(str)
    log_message = Signal(str)
    finished = Signal(str, str, str)
    failed = Signal(str)

    def __init__(self, operation: str, destination: Path, mode: str = "nightly", stable_version: str | None = None, core_filename: str | None = None) -> None:
        """Configura uma operação de instalação/atualização."""
        super().__init__()
        self.operation = operation
        self.destination = Path(destination)
        self.mode = mode
        self.stable_version = stable_version
        self.core_filename = core_filename

    def _log(self, message: str) -> None:
        """Publica uma mensagem operacional."""
        self.log_message.emit(str(message))

    @Slot()
    def run(self) -> None:
        """Executa a operação selecionada e atualiza AppConfig."""
        try:
            service = RetroArchDownloadService(log_callback=self._log)
            self.status.emit("Consultando Buildbot oficial…")
            channel = service.channel(self.mode, self.stable_version)
            self._log(f"CANAL | {channel.name} | base={channel.base_url}")

            if self.operation in {"install", "update"}:
                self.status.emit("Baixando RetroArch…")
                archive = service.download_retroarch(channel, self.destination, progress=lambda received, total: self.progress.emit(received, total))
                preserve = self.operation == "update"
                self.status.emit("Extraindo RetroArch…")
                executable = service.install_retroarch(archive, self.destination, preserve_config=preserve)
                config = AppConfig()
                config.retroarch_version = channel.version or "nightly"
                # O retroarch.cfg é a fonte de verdade. Depois de extrair,
                # reimportamos todos os diretórios nativos em vez de inventar
                # uma árvore paralela no AppConfig.
                try:
                    config.set_retroarch_executable(executable)
                except (FileNotFoundError, OSError, ValueError) as exc:
                    config.retroarch_path = executable
                    config.retroarch_dir = self.destination
                    self._log(f"AVISO | retroarch.cfg não pôde ser importado após instalação: {exc}")
                config.retroarch_version = channel.version or "nightly"
                config.save()
                self.finished.emit("retroarch", config.retroarch_version or "nightly", str(executable))
                return

            if self.operation in {"core", "cores_installed"}:
                self.status.emit("Consultando lista de cores…")
                cores = service.list_cores(channel)
                by_name = {item.core_name.casefold(): item for item in cores}
                cores_dir = self.destination / "cores"
                if self.operation == "core":
                    selected = next((item for item in cores if item.filename == self.core_filename), None)
                    if selected is None:
                        raise ValueError(f"Core não encontrado no índice: {self.core_filename}")
                    selected_cores = [selected]
                else:
                    installed = sorted(cores_dir.glob("*_libretro.dll")) if cores_dir.is_dir() else []
                    selected_cores = []
                    for dll in installed:
                        logical = dll.stem.removesuffix("_libretro").casefold()
                        if logical in by_name:
                            selected_cores.append(by_name[logical])
                    if not selected_cores:
                        raise ValueError("Nenhum core instalado corresponde ao índice oficial deste canal. Verifique o diretório Cores importado do retroarch.cfg.")
                    self._log(f"CORES INSTALADOS | candidatos={len(selected_cores)}")

                for index, selected in enumerate(selected_cores, start=1):
                    self.status.emit(f"Baixando core {index}/{len(selected_cores)}: {selected.core_name}…")
                    self._log(f"CORE {index}/{len(selected_cores)} | {selected.core_name} | CRC={selected.crc32}")
                    service.download_core(
                        channel,
                        selected,
                        cores_dir,
                        progress=lambda received, total, offset=index - 1, count=len(selected_cores): self.progress.emit(int(((offset + (received / total if total else 0)) / count) * 100), 100),
                    )
                self.finished.emit("cores", str(len(selected_cores)), str(cores_dir))
                return

            raise ValueError(f"Operação RetroArch desconhecida: {self.operation}")
        except Exception as exc:
            self._log(f"ERRO | {type(exc).__name__}: {exc}")
            self.failed.emit("\n".join((f"{type(exc).__name__}: {exc}", traceback.format_exc())))
