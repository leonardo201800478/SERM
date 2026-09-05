"""Interface inicial do WHLoader para aquisição e indexação da base WHDLoad."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget

from ..services.whloader_data_service import WHLoaderDataError, WHLoaderDataService, WHLoaderScanResult

logger = logging.getLogger(__name__)


class _WHLoaderScanWorker(QThread):
    """Executa a atualização da base WHDLoad fora da thread da interface."""

    completed = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        try:
            self.completed.emit(WHLoaderDataService().scan())
        except WHLoaderDataError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class WHLoaderPage(QWidget):
    """Página de dados WHDLoad; a biblioteca de jogos será adicionada depois."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.worker: _WHLoaderScanWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("WHLoader — Base WHDLoad"))
        layout.addWidget(QLabel("Fonte principal: Amiberry Game DB (db.amiberry.com)"))

        actions = QHBoxLayout()
        self.scan_button = QPushButton("ATUALIZAR / SCAN DATA")
        self.scan_button.setToolTip("Baixa a base WHDLoad do Amiberry, valida o JSON e atualiza o índice local do SERM.")
        self.scan_button.clicked.connect(self.scan_data)
        actions.addWidget(self.scan_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.status = QLabel("Base WHDLoad ainda não sincronizada nesta sessão.")
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1000)
        layout.addWidget(self.log, 1)

    def refresh(self) -> None:
        """Mantém a página pronta sem disparar download automático."""
        return

    def _append(self, message: str) -> None:
        self.log.appendPlainText(message)
        logger.info("[WHLoader] %s", message)

    def scan_data(self) -> None:
        """Atualiza a base Amiberry e reconstrói o índice local."""
        if self.worker and self.worker.isRunning():
            return
        self.scan_button.setEnabled(False)
        self.progress.setVisible(True)
        self.status.setText("Baixando e indexando a base WHDLoad…")
        self._append("SCAN | iniciando atualização da base Amiberry")
        self.worker = _WHLoaderScanWorker(self)
        self.worker.completed.connect(self._completed)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _completed(self, result: WHLoaderScanResult) -> None:
        self.status.setText(
            f"{result.games:,} jogos | {result.slaves:,} slaves | schema {result.schema_version or '—'}"
        )
        self._append(f"OK | jogos={result.games} | slaves={result.slaves}")
        self._append(f"SHA256 | {result.source_hash}")
        self._append(f"RAW | {Path(result.raw_path)}")
        self._append(f"TEMPO | {result.elapsed_seconds:.2f}s")

    def _failed(self, message: str) -> None:
        self.status.setText(f"Erro: {message}")
        self._append(f"ERRO | {message}")

    def _finished(self) -> None:
        self.progress.setVisible(False)
        self.scan_button.setEnabled(True)


__all__ = ["WHLoaderPage"]
