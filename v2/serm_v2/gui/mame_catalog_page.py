"""Interface para ingerir o DAT/ListXML do MAME configurado."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..services.mame_catalog_service import MameCatalogError, MameCatalogService


class _Worker(QThread):
    """Executa a ingestão sem bloquear a interface Qt."""

    completed = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        """Executa uma ingestão completa do catálogo."""
        try:
            self.completed.emit(MameCatalogService().ingest())
        except MameCatalogError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class MameCatalogPage(QWidget):
    """Permite testar e persistir o catálogo do executável MAME selecionado."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.worker: _Worker | None = None
        self.service = MameCatalogService()
        self._build_ui()

    def _build_ui(self) -> None:
        """Monta status, ação de ingestão, progresso e log."""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("MAME — DAT / ListXML"))
        self.executable = QLabel("Executável configurado: —")
        layout.addWidget(self.executable)
        self.status = QLabel("Nenhuma ingestão executada.")
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.run_button = QPushButton("OBTER DAT DO MAME (-listxml)")
        self.run_button.clicked.connect(self.ingest)
        layout.addWidget(self.run_button)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1000)
        layout.addWidget(self.log, 1)
        self.refresh()

    def refresh(self) -> None:
        """Mostra o executável atualmente configurado em Diretórios."""
        try:
            self.executable.setText(
                f"Executável configurado: {self.service.configured_executable()}"
            )
        except MameCatalogError as exc:
            self.executable.setText(f"Executável configurado: não definido — {exc}")

    def ingest(self) -> None:
        """Inicia a extração do ListXML e sua persistência."""
        if self.worker and self.worker.isRunning():
            return
        self.refresh()
        self.run_button.setEnabled(False)
        self.progress.setVisible(True)
        self.status.setText("Executando MAME -listxml…")
        self.log.appendPlainText("MAME | iniciando ingestão pelo executável configurado")
        self.worker = _Worker(self)
        self.worker.completed.connect(self._completed)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _completed(self, result: object) -> None:
        """Exibe o resultado da ingestão concluída."""
        data = cast(dict[str, object], result)
        self.status.setText(f"Ingestão concluída: {data['machine_count']} máquinas")
        self.log.appendPlainText(f"OK | executável={data['executable']}")
        self.log.appendPlainText(f"OK | máquinas={data['machine_count']}")
        self.log.appendPlainText(f"OK | XML={data['raw_xml']}")
        self.log.appendPlainText(f"OK | banco={data['database']}")

    def _failed(self, message: str) -> None:
        """Exibe a falha sem ocultar a causa original."""
        self.status.setText("Falha na ingestão")
        self.log.appendPlainText(f"ERRO MAME | {message}")

    def _finished(self) -> None:
        """Libera os controles após a thread terminar."""
        self.progress.setVisible(False)
        self.run_button.setEnabled(True)
        self.refresh()


__all__ = ["MameCatalogPage"]
