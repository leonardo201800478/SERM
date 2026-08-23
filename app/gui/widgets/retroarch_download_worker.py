"""Worker Qt para download do RetroArch e dos cores libretro."""
from __future__ import annotations

import traceback
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.config.app_config import AppConfig
from app.core.services.retroarch_download_service import (
    RetroArchDownloadService,
    RetroArchCoreInfo,
)


class RetroArchDownloadWorker(QObject):
    """Executa downloads do Buildbot fora da thread da GUI."""

    progress = Signal(int, int)
    status = Signal(str)
    log_message = Signal(str)
    finished = Signal(str, str, str)
    failed = Signal(str)

    def __init__(
        self,
        operation: str,
        destination: Path,
        mode: str = "nightly",
        stable_version: str | None = None,
        core_filename: str | None = None,
    ) -> None:
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
                archive = service.download_retroarch(
                    channel,
                    self.destination,
                    progress=lambda received, total: self.progress.emit(received, total),
                )
                preserve = self.operation == "update"
                self.status.emit("Extraindo RetroArch…")
                executable = service.install_retroarch(archive, self.destination, preserve_config=preserve)
                version = channel.version or "nightly"
                config = AppConfig()
                config.retroarch_path = executable
                config.retroarch_dir = self.destination
                config.retroarch_version = version
                config.set_emulator_path("retroarch", "config", self.destination)
                config.set_emulator_path("retroarch", "cores", self.destination / "cores")
                config.set_emulator_path("retroarch", "system", self.destination / "system")
                config.set_emulator_path("retroarch", "assets", self.destination / "assets")
                config.set_emulator_path("retroarch", "shaders", self.destination / "shaders")
                config.set_emulator_path("retroarch", "saves", self.destination / "saves")
                config.set_emulator_path("retroarch", "states", self.destination / "states")
                config.set_emulator_path("retroarch", "downloads", self.destination / "downloads")
                config.save()
                self.finished.emit("retroarch", version, str(executable))
                return

            if self.operation == "core":
                self.status.emit("Consultando lista de cores…")
                cores = service.list_cores(channel)
                selected = next((item for item in cores if item.filename == self.core_filename), None)
                if selected is None:
                    raise ValueError(f"Core não encontrado no índice: {self.core_filename}")
                self.status.emit(f"Baixando core {selected.core_name}…")
                cores_dir = self.destination / "cores"
                dll = service.download_core(
                    channel,
                    selected,
                    cores_dir,
                    progress=lambda received, total: self.progress.emit(received, total),
                )
                self.finished.emit("core", selected.core_name, str(dll))
                return

            raise ValueError(f"Operação RetroArch desconhecida: {self.operation}")
        except Exception as exc:
            self._log(f"ERRO | {type(exc).__name__}: {exc}")
            self.failed.emit("\n".join((f"{type(exc).__name__}: {exc}", traceback.format_exc())))
