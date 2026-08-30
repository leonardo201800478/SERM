"""Painel de teste da Etapa 3: ingestão do resolution.ini."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget

from ..services.mame_catalog_service import MameCatalogError, MameCatalogService
from ..services.mame_resolution_service import MameResolutionError, MameResolutionService


class _ResolutionWorker(QThread):
    """Executa a ingestão sem bloquear a interface."""
    message = Signal(str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, database_path, mame_root, parent=None) -> None:
        super().__init__(parent)
        self.database_path = database_path
        self.mame_root = mame_root

    def run(self) -> None:
        """Executa o serviço e encaminha os logs para a GUI."""
        try:
            result = MameResolutionService(self.database_path, self.mame_root).ingest(logger=self.message.emit)
            self.completed.emit(result)
        except (MameResolutionError, MameCatalogError) as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class MameResolutionTab(QWidget):
    """Painel isolado para testar a importação de resolution.ini."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.catalog = MameCatalogService()
        self.worker = None
        self._build_ui()

    def _build_ui(self) -> None:
        """Monta controles, status e log operacional."""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("MAME — Resolution.ini"))
        self.status = QLabel("Aguardando importação.")
        layout.addWidget(self.status)
        self.button = QPushButton("IMPORTAR RESOLUTION.INI")
        self.button.clicked.connect(self.ingest)
        layout.addWidget(self.button)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(3000)
        layout.addWidget(self.log, 1)

    def _log(self, text: str) -> None:
        """Adiciona uma mensagem ao log da GUI."""
        self.log.appendPlainText(text)

    def ingest(self) -> None:
        """Inicia a importação usando o executável configurado em Diretórios."""
        if self.worker and self.worker.isRunning():
            return
        try:
            executable = self.catalog.configured_executable()
        except MameCatalogError as exc:
            self._log(f"ERROR | {exc}")
            return
        self.button.setEnabled(False)
        self.progress.setVisible(True)
        self.status.setText("Importando resolution.ini…")
        self._log(f"START | executável={executable}")
        self._log(f"SOURCE | raiz={executable.parent}")
        self.worker = _ResolutionWorker(self.catalog.DB_FILE, executable.parent, self)
        self.worker.message.connect(lambda message: self._log(message))
        self.worker.completed.connect(self._completed)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _completed(self, result: object) -> None:
        """Exibe o resumo da ingestão."""
        self.status.setText(f"Concluído | entradas={result['entries']:,} | resolvidas={result['resolved']:,} | não resolvidas={result['unresolved']:,}")
        self._log(f"OK | RESOLUTION | entradas={result['entries']:,}")
        self._log(f"OK | RESOLUTION | resolvidas={result['resolved']:,}")
        self._log(f"OK | RESOLUTION | não resolvidas={result['unresolved']:,}")
        self._log(f"DONE | RESOLUTION | source_id={result['source_id']}")

    def _failed(self, message: str) -> None:
        """Exibe a falha sem ocultar sua causa."""
        self.status.setText("Falha na importação.")
        self._log(f"ERROR | RESOLUTION | {message}")

    def _finished(self) -> None:
        """Libera a interface após o worker terminar."""
        self.progress.setVisible(False)
        self.button.setEnabled(True)


__all__ = ["MameResolutionTab"]
