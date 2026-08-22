"""Worker Qt para downloads/instalações de emuladores sem bloquear a GUI."""
from __future__ import annotations

import logging
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.core.services.emulator_install_service import EmulatorInstallService

logger = logging.getLogger(__name__)


class EmulatorInstallWorker(QObject):
    """Executa uma instalação de emulador fora da thread da interface."""

    progress = Signal(int, int)
    status = Signal(str)
    finished = Signal(str, str, str)
    failed = Signal(str)

    def __init__(self, emulator: str, destination: Path, nightly: bool = False) -> None:
        super().__init__()
        self.emulator = emulator
        self.destination = destination
        self.nightly = nightly

    @Slot()
    def run(self) -> None:
        """Executa a operação e converte qualquer exceção em sinal seguro."""
        logger.info("Emulator worker: iniciado | emulator=%s | destination=%s | nightly=%s", self.emulator, self.destination, self.nightly)
        try:
            self.status.emit("Consultando release oficial…")
            service = EmulatorInstallService()
            release, asset, executable = service.download_and_install(
                self.emulator,
                self.destination,
                nightly=self.nightly,
                progress=lambda received, total: self.progress.emit(received, total),
            )
            logger.info("Emulator worker: concluído | emulator=%s | release=%s | asset=%s | executable=%s", self.emulator, release.tag, asset.name, executable)
            self.finished.emit(self.emulator, release.tag, str(executable))
        except Exception as exc:
            logger.exception("Emulator worker: falha | emulator=%s | destination=%s", self.emulator, self.destination)
            diagnostic = "\n".join((f"{type(exc).__name__}: {exc}", traceback.format_exc()))
            self.failed.emit(diagnostic)
