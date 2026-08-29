"""Worker Qt para downloads/instalações de emuladores sem bloquear a GUI."""
from __future__ import annotations

import logging
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.config.app_config import AppConfig
from app.core.services.emulator_install_service import EmulatorInstallService

logger = logging.getLogger(__name__)


class EmulatorInstallWorker(QObject):
    """Executa uma instalação de emulador fora da thread da interface."""

    progress = Signal(int, int)
    status = Signal(str)
    log_message = Signal(str)
    finished = Signal(str, str, str)
    failed = Signal(str)

    def __init__(self, emulator: str, destination: Path, nightly: bool = False) -> None:
        super().__init__()
        self.emulator = emulator
        self.destination = destination
        self.nightly = nightly

    def _log(self, message: str) -> None:
        """Envia uma mensagem operacional para a GUI e para o log normal."""
        logger.info("Emulator worker: %s", message)
        self.log_message.emit(message)

    @Slot()
    def run(self) -> None:
        """Executa a instalação e publica cada etapa operacional."""
        self._log(
            f"INÍCIO | emulador={self.emulator} | destino={self.destination} | nightly={self.nightly}"
        )
        try:
            service = EmulatorInstallService(log_callback=self._log)
            self.status.emit("Consultando release oficial…")
            self._log("1/8 Consultando o release oficial e procurando o link do pacote…")
            release = service.release(self.emulator, nightly=self.nightly)
            self._log(
                f"2/8 Release encontrado | tag={release.tag} | assets={len(release.assets)}"
            )

            asset = service.select_asset(release)
            self._log(
                f"3/8 Pacote selecionado | nome={asset.name} | tamanho={asset.size:,} bytes | url={asset.url}"
            )

            self.status.emit("Baixando pacote…")
            self._log("4/8 Iniciando download do arquivo…")
            release, asset, executable = service.download_and_install(
                self.emulator,
                self.destination,
                nightly=self.nightly,
                release=release,
                progress=lambda received, total: self.progress.emit(received, total),
            )

            try:
                config = AppConfig()
                setattr(config, f"{self.emulator}_version", release.tag)
                setattr(config, f"{self.emulator}_path", Path(executable))
                setattr(config, f"{self.emulator}_dir", Path(executable).parent)
                config.save()
                self._log(
                    f"VERSÃO PERSISTIDA | emulator={self.emulator} | versão={release.tag} | origem=GitHub release confirmado"
                )
            except Exception:
                logger.exception(
                    "Emulator worker: falha ao persistir versão | emulator=%s | version=%s",
                    self.emulator,
                    release.tag,
                )
                self._log("AVISO | instalação concluída, mas a versão não pôde ser persistida")

            self._log(
                f"8/8 INSTALAÇÃO CONCLUÍDA | executável={executable} | release={release.tag} | asset={asset.name}"
            )
            logger.info(
                "Emulator worker: concluído | emulator=%s | release=%s | asset=%s | executable=%s",
                self.emulator,
                release.tag,
                asset.name,
                executable,
            )
            self.finished.emit(self.emulator, release.tag, str(executable))
        except Exception as exc:
            self._log(f"ERRO FATAL | {type(exc).__name__}: {exc}")
            logger.exception(
                "Emulator worker: falha | emulator=%s | destination=%s",
                self.emulator,
                self.destination,
            )
            diagnostic = "\n".join((f"{type(exc).__name__}: {exc}", traceback.format_exc()))
            self.failed.emit(diagnostic)
