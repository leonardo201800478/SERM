"""Redump direct acquisition page for SERM V2."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..integrations.launchbox import LaunchBoxIntegration
from ..integrations.launchbox_provider import LaunchBoxProvider
from ..sources.acquisition.redump import RedumpEntry, RedumpError, RedumpProvider

logger = logging.getLogger(__name__)


class RedumpPage(QWidget):
    """Discover LaunchBox platforms and download their Redump DATs directly."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.launchbox = LaunchBoxIntegration()
        self.launchbox_provider = LaunchBoxProvider(self.launchbox)
        self.provider = RedumpProvider()
        self.entries: tuple[RedumpEntry, ...] = ()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the Redump acquisition controls."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        title = QLabel("Redump — DATs diretos")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:24px;font-weight:700;")
        layout.addWidget(title)
        detail = QLabel(
            "Usa /datfile/<sistema>/ diretamente, sem Selenium, CAPTCHA ou página interativa."
        )
        detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail.setWordWrap(True)
        layout.addWidget(detail)
        self.status = QLabel("Aguardando catálogo…")
        layout.addWidget(self.status)
        self.systems = QComboBox()
        self.systems.setEnabled(False)
        layout.addWidget(self.systems)
        row = QHBoxLayout()
        refresh = QPushButton("🌐 Carregar sistemas Redump")
        refresh.clicked.connect(self.load_systems)
        row.addWidget(refresh)
        self.download = QPushButton("⬇ Baixar selecionado")
        self.download.setEnabled(False)
        self.download.clicked.connect(self.download_selected)
        row.addWidget(self.download)
        self.refresh_button = refresh
        layout.addLayout(row)
        layout.addStretch(1)

    def load_systems(self) -> None:
        """Match LaunchBox platforms against all supported Redump endpoints."""
        try:
            platforms = tuple(self.launchbox_provider.iter_platforms())
            names = tuple(platform.name for platform in platforms)
            self.entries = self.provider.match(names)
            self.systems.clear()
            for entry in self.entries:
                self.systems.addItem(entry.name, entry)
            self.systems.setEnabled(bool(self.entries))
            self.download.setEnabled(bool(self.entries))
            self.status.setText(f"{len(self.entries)} sistemas Redump encontrados no LaunchBox.")
        except Exception as exc:
            logger.exception("[REDUMP][MATCH] Falha ao carregar sistemas")
            self.status.setText(f"Erro: {exc}")
            self.entries = ()
            self.download.setEnabled(False)

    def download_selected(self) -> None:
        """Download and validate the selected Redump DAT."""
        if not self.entries:
            return
        entry = self.entries[self.systems.currentIndex()]
        self.refresh_button.setEnabled(False)
        self.download.setEnabled(False)
        try:
            self.status.setText(f"Baixando {entry.name}…")
            QApplication.processEvents()
            result = self.provider.download(entry)
            self.status.setText(f"OK: {result.path}")
            QMessageBox.information(self, "Redump", f"DAT baixado e validado.\n\n{result.path}")
        except RedumpError as exc:
            logger.exception("[REDUMP][DAT] Falha no sistema=%s", entry.name)
            self.status.setText(f"Erro: {exc}")
            QMessageBox.warning(self, "Redump", str(exc))
        finally:
            self.refresh_button.setEnabled(True)
            self.download.setEnabled(bool(self.entries))
