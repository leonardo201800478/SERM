"""No-Intro acquisition page for SERM V2."""

from __future__ import annotations

import logging
from pathlib import Path

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
from ..sources.acquisition.no_intro_archive import NoIntroArchiveError, NoIntroArchiveProvider

logger = logging.getLogger(__name__)


class NoIntroPage(QWidget):
    """Discover LaunchBox platforms and manage the No-Intro bulk archive."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.launchbox = LaunchBoxIntegration()
        self.launchbox_provider = LaunchBoxProvider(self.launchbox)
        self.provider = NoIntroArchiveProvider()
        self.entries = ()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the No-Intro acquisition controls."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        title = QLabel("No-Intro — Bulk Archive")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:24px;font-weight:700;")
        layout.addWidget(title)
        detail = QLabel(
            "Usa o ZIP único de release do Internet Archive. Não utiliza DAT-o-MATIC, Selenium ou navegador automatizado."
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
        self.refresh_button = QPushButton("🌐 Carregar catálogo")
        self.refresh_button.clicked.connect(self.load_catalog)
        row.addWidget(self.refresh_button)
        self.download = QPushButton("⬇ Baixar arquivo completo")
        self.download.setEnabled(False)
        self.download.clicked.connect(self.download_archive)
        row.addWidget(self.download)
        layout.addLayout(row)
        layout.addStretch(1)

    def load_catalog(self) -> None:
        """Fetch the bulk archive catalog and match it against LaunchBox."""
        self.refresh_button.setEnabled(False)
        try:
            QApplication.processEvents()
            names = tuple(platform.name for platform in self.launchbox_provider.iter_platforms())
            catalog = self.provider.fetch_catalog()
            self.entries = self.provider.match(names, catalog)
            self.systems.clear()
            for entry in self.entries:
                self.systems.addItem(Path(entry.name).stem, entry)
            self.systems.setEnabled(bool(self.entries))
            self.download.setEnabled(bool(self.entries))
            self.status.setText(
                f"{len(self.entries)} sistemas No-Intro encontrados no LaunchBox. Catálogo: {len(catalog)} entradas."
            )
            logger.info(
                "[NO-INTRO][MATCH] LaunchBox=%d catalog=%d matches=%d",
                len(names),
                len(catalog),
                len(self.entries),
            )
        except NoIntroArchiveError as exc:
            logger.exception("[NO-INTRO][ARCHIVE] Falha ao carregar catálogo")
            self.entries = ()
            self.download.setEnabled(False)
            self.status.setText(f"Erro: {exc}")
            QMessageBox.warning(self, "No-Intro", str(exc))
        except Exception as exc:
            logger.exception("[NO-INTRO][MATCH] Falha inesperada")
            self.entries = ()
            self.download.setEnabled(False)
            self.status.setText(f"Erro: {exc}")
            QMessageBox.warning(self, "No-Intro", str(exc))
        finally:
            self.refresh_button.setEnabled(True)

    def download_archive(self) -> None:
        """Download and extract the complete No-Intro release archive."""
        self.refresh_button.setEnabled(False)
        self.download.setEnabled(False)
        try:
            self.status.setText("Baixando e extraindo arquivo completo…")
            QApplication.processEvents()
            result = self.provider.fetch_catalog()
            self.status.setText("OK: arquivo No-Intro atualizado.")
            logger.info("[NO-INTRO][ARCHIVE] Arquivo atualizado: %s", result)
            QMessageBox.information(self, "No-Intro", "O arquivo completo foi baixado e extraído.")
        except NoIntroArchiveError as exc:
            logger.exception("[NO-INTRO][ARCHIVE] Falha no download")
            self.status.setText(f"Erro: {exc}")
            QMessageBox.warning(self, "No-Intro", str(exc))
        finally:
            self.refresh_button.setEnabled(True)
            self.download.setEnabled(bool(self.entries))
