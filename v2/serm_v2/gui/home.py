"""Original SERM V2 home dashboard."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..integrations.launchbox import LaunchBoxIntegration
from .log_handler import LogViewer

logger = logging.getLogger(__name__)


class HomePage(QWidget):
    """Present the application dashboard without owning provider workflows."""

    def __init__(self, log_viewer: LogViewer, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log_viewer = log_viewer
        self.launchbox = LaunchBoxIntegration()
        self._build_ui()
        self.refresh_status()
        self.log_viewer.handler.record_emitted.connect(self._append_log)
        for message in self.log_viewer.handler.records:
            self._append_log("INFO", message)

    def _build_ui(self) -> None:
        """Build the dashboard cards and application log panel."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("SERM")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:30px;font-weight:700;")
        layout.addWidget(title)
        subtitle = QLabel("Strife Emulator and Roms Manager")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setSpacing(12)
        grid.addWidget(self._status_card(), 0, 0)
        grid.addWidget(self._source_card(), 0, 1)
        layout.addLayout(grid)

        log_frame = QFrame()
        log_frame.setObjectName("logFrame")
        log_frame.setStyleSheet(
            "QFrame#logFrame{border:1px solid #3d3d3d;border-radius:8px;}"
            "QLabel#sectionTitle{font-size:15px;font-weight:700;}"
            "QLabel#log{font-family:Consolas,monospace;font-size:11px;}"
        )
        log_layout = QVBoxLayout(log_frame)
        header = QHBoxLayout()
        header.addWidget(QLabel("Logs da aplicação", objectName="sectionTitle"))
        clear = QPushButton("Limpar")
        clear.clicked.connect(self._clear_logs)
        header.addStretch(1)
        header.addWidget(clear)
        log_layout.addLayout(header)
        self.log_label = QLabel()
        self.log_label.setObjectName("log")
        self.log_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.log_label.setWordWrap(False)
        self.log_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        log_layout.addWidget(self.log_label, 1)
        layout.addWidget(log_frame, 1)

    def _status_card(self) -> QFrame:
        """Create the LaunchBox status card."""
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("QFrame#card{border:1px solid #414141;border-radius:8px;padding:8px;}")
        layout = QVBoxLayout(card)
        layout.addWidget(QLabel("Ambiente", objectName="sectionTitle"))
        self.launchbox_status = QLabel("Verificando…")
        self.launchbox_path = QLabel("LaunchBox: —")
        self.launchbox_metadata = QLabel("Metadata DB: —")
        for label in (self.launchbox_status, self.launchbox_path, self.launchbox_metadata):
            label.setWordWrap(True)
            layout.addWidget(label)
        refresh = QPushButton("Atualizar status")
        refresh.clicked.connect(self.refresh_status)
        layout.addWidget(refresh)
        return card

    def _source_card(self) -> QFrame:
        """Create the provider summary card."""
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("QFrame#card{border:1px solid #414141;border-radius:8px;padding:8px;}")
        layout = QVBoxLayout(card)
        layout.addWidget(QLabel("Fontes", objectName="sectionTitle"))
        layout.addWidget(QLabel("No-Intro — Bulk Archive"))
        layout.addWidget(QLabel("Redump — Direct DAT endpoints"))
        layout.addWidget(QLabel("LaunchBox — integração local"))
        detail = QLabel("Os fluxos de aquisição ficam nas suas respectivas abas; a Home permanece apenas como dashboard.")
        detail.setWordWrap(True)
        detail.setStyleSheet("color:#aaa;")
        layout.addWidget(detail)
        return card

    def refresh_status(self) -> None:
        """Refresh local LaunchBox discovery and report it through the application logger."""
        try:
            executable = self.launchbox.discover()
            metadata = self.launchbox.metadata_database()
            if executable:
                self.launchbox_status.setText("● LaunchBox disponível")
                self.launchbox_path.setText(f"Executável: {executable}")
                self.launchbox_metadata.setText(f"Metadata DB: {metadata or 'não localizado'}")
                logger.info("[LAUNCHBOX] disponível: %s", executable)
            else:
                self.launchbox_status.setText("● LaunchBox não configurado")
                self.launchbox_path.setText("LaunchBox: não localizado")
                self.launchbox_metadata.setText("Metadata DB: —")
                logger.warning("[LAUNCHBOX] executável não localizado")
        except Exception as exc:
            logger.exception("[LAUNCHBOX] falha ao atualizar status")
            self.launchbox_status.setText(f"● Erro: {exc}")

    def _append_log(self, _level: str, message: str) -> None:
        """Append a log message to the dashboard without replacing existing entries."""
        current = self.log_label.text()
        lines = current.splitlines() if current else []
        lines.append(message)
        self.log_label.setText("\n".join(lines[-80:]))

    def _clear_logs(self) -> None:
        """Clear only the visible dashboard log history."""
        self.log_label.clear()
