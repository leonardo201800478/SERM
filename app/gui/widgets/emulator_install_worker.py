"""Worker Qt para downloads/instalações de emuladores sem bloquear a GUI."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.core.services.emulator_install_service import EmulatorInstallService


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
        """Baixa e instala o pacote, emitindo progresso e resultado."""
        try:
            self.status.emit("Consultando release oficial…")
            service = EmulatorInstallService()
            release, asset, executable = service.download_and_install(
                self.emulator,
                self.destination,
                nightly=self.nightly,
                progress=lambda received, total: self.progress.emit(received, total),
            )
            self.finished.emit(self.emulator, release.tag, str(executable))
        except Exception as exc:
            self.failed.emit(str(exc))
