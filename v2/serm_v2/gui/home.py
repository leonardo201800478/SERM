"""SERM V2 Home page.

The visual organization follows the proven legacy Home concept, but all
runtime state in V2 is independent. LaunchBox is the first external
integration exposed from the new Home.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QUrl

from ..integrations.launchbox import LaunchBoxIntegration

logger = logging.getLogger(__name__)


class HomePage(QWidget):
    """Present the V2 Home and the first external integration status."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.launchbox = LaunchBoxIntegration()
        self._build_ui()
        self.refresh_status()

    def _build_ui(self) -> None:
        """Build the Home surface without importing any V1 service."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("SERM")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: 700;")
        layout.addWidget(title)

        subtitle = QLabel("Strife Emulator and Roms Manager")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        status_frame = QFrame()
        status_frame.setObjectName("statusFrame")
        status_frame.setStyleSheet(
            "QFrame#statusFrame{background:#151515;border:1px solid #3d3d3d;"
            "border-radius:8px;padding:10px;}"
            "QFrame#integrationCard{background:#202020;border:1px solid #414141;"
            "border-radius:7px;}"
            "QLabel#integrationName{font-size:15px;font-weight:bold;}"
            "QLabel#detail{color:#b8b8b8;}"
        )
        grid = QGridLayout(status_frame)
        self.launchbox_card = self._create_launchbox_card()
        grid.addWidget(self.launchbox_card, 0, 0)
        grid.addWidget(self._create_placeholder_card("Emuladores", "Runtime V2 será conectado nesta camada."), 0, 1)
        grid.addWidget(self._create_placeholder_card("Catálogo", "Data Foundation V2 será conectada nesta camada."), 1, 0)
        grid.addWidget(self._create_placeholder_card("Biblioteca", "Scan e matching serão conectados nesta camada."), 1, 1)
        layout.addWidget(status_frame)

        footer = QLabel("V2 não importa banco, configuração ou serviços da arquitetura legada.")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color:#888;font-size:10px;")
        layout.addWidget(footer)
        layout.addStretch(1)

    def _create_launchbox_card(self) -> QFrame:
        """Create the LaunchBox integration card and its actions."""
        card = QFrame()
        card.setObjectName("integrationCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)

        name = QLabel("LaunchBox")
        name.setObjectName("integrationName")
        layout.addWidget(name)

        self.launchbox_status = QLabel("Verificando…")
        self.launchbox_status.setObjectName("detail")
        layout.addWidget(self.launchbox_status)

        self.launchbox_path = QLabel("Executável: —")
        self.launchbox_path.setObjectName("detail")
        self.launchbox_path.setWordWrap(True)
        layout.addWidget(self.launchbox_path)

        self.launchbox_metadata = QLabel("Metadata DB: —")
        self.launchbox_metadata.setObjectName("detail")
        self.launchbox_metadata.setWordWrap(True)
        layout.addWidget(self.launchbox_metadata)

        row = QHBoxLayout()
        select = QPushButton("📁 Selecionar LaunchBox.exe")
        select.clicked.connect(self.select_launchbox)
        row.addWidget(select)

        launch = QPushButton("▶ Abrir LaunchBox")
        launch.clicked.connect(self.open_launchbox)
        row.addWidget(launch)
        self.launchbox_launch_button = launch

        metadata = QPushButton("📂 Abrir Metadata")
        metadata.clicked.connect(self.open_metadata_folder)
        row.addWidget(metadata)
        self.launchbox_metadata_button = metadata
        layout.addLayout(row)
        return card

    @staticmethod
    def _create_placeholder_card(title: str, detail: str) -> QFrame:
        """Create a non-operational V2 domain card without legacy dependencies."""
        card = QFrame()
        card.setObjectName("integrationCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        name = QLabel(title)
        name.setObjectName("integrationName")
        layout.addWidget(name)
        label = QLabel(f"● Em preparação\n{detail}")
        label.setObjectName("detail")
        label.setWordWrap(True)
        layout.addWidget(label)
        return card

    def refresh_status(self) -> None:
        """Refresh LaunchBox discovery without network access or V1 state."""
        try:
            executable = self.launchbox.discover()
            if executable:
                self.launchbox_status.setText("● Disponível")
                self.launchbox_status.setStyleSheet("color:#55d66b;font-weight:bold;")
                self.launchbox_path.setText(f"Executável: {executable}")
                metadata = self.launchbox.metadata_database()
                self.launchbox_metadata.setText(f"Metadata DB: {metadata or 'não localizado'}")
                self.launchbox_launch_button.setEnabled(True)
                self.launchbox_metadata_button.setEnabled(metadata is not None)
            else:
                self.launchbox_status.setText("● Não configurado")
                self.launchbox_status.setStyleSheet("color:#e5c454;font-weight:bold;")
                self.launchbox_path.setText("Executável: —")
                self.launchbox_metadata.setText("Metadata DB: —")
                self.launchbox_launch_button.setEnabled(False)
                self.launchbox_metadata_button.setEnabled(False)
        except Exception as exc:
            logger.exception("Falha ao descobrir LaunchBox")
            self.launchbox_status.setText(f"● Erro: {type(exc).__name__}")
            self.launchbox_launch_button.setEnabled(False)
            self.launchbox_metadata_button.setEnabled(False)

    def select_launchbox(self) -> None:
        """Select and persist a LaunchBox.exe outside the SERM repository."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar LaunchBox.exe",
            str(Path.home()),
            "LaunchBox (LaunchBox.exe)",
        )
        if not path:
            return
        try:
            self.launchbox.set_executable(Path(path))
            self.refresh_status()
        except (ValueError, FileNotFoundError, OSError) as exc:
            QMessageBox.warning(self, "LaunchBox", str(exc))

    def open_launchbox(self) -> None:
        """Start the configured LaunchBox installation."""
        try:
            self.launchbox.launch()
        except (FileNotFoundError, OSError) as exc:
            QMessageBox.warning(self, "LaunchBox", str(exc))

    def open_metadata_folder(self) -> None:
        """Open LaunchBox's Metadata directory in Windows Explorer."""
        database = self.launchbox.metadata_database()
        if database is None:
            QMessageBox.information(self, "LaunchBox", "LaunchBox.Metadata.db não foi localizado.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(database.parent)))
