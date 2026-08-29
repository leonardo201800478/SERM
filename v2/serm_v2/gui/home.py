"""SERM V2 Home page with LaunchBox and DAT source acquisition."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
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

from ..integrations.launchbox import LaunchBoxIntegration
from ..integrations.launchbox_provider import LaunchBoxProvider
from ..sources.acquisition.dat_catalog import DatCatalogEntry, DatCatalogError, PublicDatCatalogProvider
from ..sources.acquisition.redump import RedumpEntry, RedumpError, RedumpProvider

logger = logging.getLogger(__name__)


class HomePage(QWidget):
    """Present LaunchBox discovery and independent No-Intro/Redump catalogs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.launchbox = LaunchBoxIntegration()
        self.launchbox_provider = LaunchBoxProvider(self.launchbox)
        self.dat_catalog = PublicDatCatalogProvider()
        self.redump = RedumpProvider()
        self.no_intro_entries: tuple[DatCatalogEntry, ...] = ()
        self.redump_entries: tuple[RedumpEntry, ...] = ()
        self._build_ui()
        self.refresh_status()

    def _build_ui(self) -> None:
        """Build the V2 Home surface."""
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
            "QFrame#statusFrame{background:#151515;border:1px solid #3d3d3d;border-radius:8px;padding:10px;}"
            "QFrame#integrationCard{background:#202020;border:1px solid #414141;border-radius:7px;}"
            "QLabel#integrationName{font-size:15px;font-weight:bold;}"
            "QLabel#detail{color:#b8b8b8;}"
        )
        grid = QGridLayout(status_frame)
        grid.addWidget(self._create_launchbox_card(), 0, 0, 1, 2)
        grid.addWidget(self._create_no_intro_card(), 1, 0)
        grid.addWidget(self._create_redump_card(), 1, 1)
        layout.addWidget(status_frame)
        footer = QLabel("DATs são obtidos de catálogos públicos com links diretos; DAT-o-MATIC não é usado.")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color:#888;font-size:10px;")
        layout.addWidget(footer)
        layout.addStretch(1)

    @staticmethod
    def _card(title: str) -> tuple[QFrame, QVBoxLayout]:
        """Create a standard integration card and its layout."""
        card = QFrame()
        card.setObjectName("integrationCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        name = QLabel(title)
        name.setObjectName("integrationName")
        layout.addWidget(name)
        return card, layout

    def _create_launchbox_card(self) -> QFrame:
        """Create the LaunchBox integration card."""
        card, layout = self._card("LaunchBox")
        self.launchbox_status = QLabel("Verificando…", objectName="detail")
        self.launchbox_path = QLabel("Executável: —", objectName="detail")
        self.launchbox_path.setWordWrap(True)
        self.launchbox_metadata = QLabel("Metadata DB: —", objectName="detail")
        self.launchbox_metadata.setWordWrap(True)
        layout.addWidget(self.launchbox_status)
        layout.addWidget(self.launchbox_path)
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

    def _create_no_intro_card(self) -> QFrame:
        """Create No-Intro catalog actions."""
        card, layout = self._card("No-Intro / Public DAT Catalog")
        self.no_intro_status = QLabel("Aguardando teste…", objectName="detail")
        layout.addWidget(self.no_intro_status)
        self.no_intro_systems = QComboBox()
        self.no_intro_systems.setPlaceholderText("Sistemas do LaunchBox encontrados")
        layout.addWidget(self.no_intro_systems)
        row = QHBoxLayout()
        test = QPushButton("🌐 Atualizar catálogo")
        test.clicked.connect(self.test_no_intro_catalog)
        row.addWidget(test)
        self.no_intro_test_button = test
        download = QPushButton("⬇ Baixar selecionado")
        download.clicked.connect(self.download_selected_no_intro)
        row.addWidget(download)
        self.no_intro_download_button = download
        all_button = QPushButton("⬇ Baixar todos")
        all_button.clicked.connect(lambda: self._batch_download("no_intro", False))
        row.addWidget(all_button)
        self.no_intro_download_all_button = all_button
        update = QPushButton("🔄 Atualizar")
        update.clicked.connect(lambda: self._batch_download("no_intro", True))
        row.addWidget(update)
        self.no_intro_update_button = update
        layout.addLayout(row)
        self._set_no_intro_download_enabled(False)
        return card

    def _create_redump_card(self) -> QFrame:
        """Create Redump catalog actions using the public direct-file mirror."""
        card, layout = self._card("Redump / Public DAT Catalog")
        self.redump_status = QLabel("Aguardando teste…", objectName="detail")
        layout.addWidget(self.redump_status)
        self.redump_systems = QComboBox()
        self.redump_systems.setPlaceholderText("Sistemas de mídia de disco do LaunchBox")
        layout.addWidget(self.redump_systems)
        row = QHBoxLayout()
        test = QPushButton("🌐 Atualizar catálogo")
        test.clicked.connect(self.test_redump_catalog)
        row.addWidget(test)
        self.redump_test_button = test
        download = QPushButton("⬇ Baixar selecionado")
        download.clicked.connect(self.download_selected_redump)
        row.addWidget(download)
        self.redump_download_button = download
        all_button = QPushButton("⬇ Baixar todos")
        all_button.clicked.connect(lambda: self._batch_download("redump", False))
        row.addWidget(all_button)
        self.redump_download_all_button = all_button
        update = QPushButton("🔄 Atualizar")
        update.clicked.connect(lambda: self._batch_download("redump", True))
        row.addWidget(update)
        self.redump_update_button = update
        layout.addLayout(row)
        self._set_redump_download_enabled(False)
        return card

    def refresh_status(self) -> None:
        """Refresh LaunchBox discovery and availability of catalog actions."""
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
                self.no_intro_test_button.setEnabled(metadata is not None)
                self.redump_test_button.setEnabled(metadata is not None)
            else:
                self.launchbox_status.setText("● Não configurado")
                self.launchbox_status.setStyleSheet("color:#e5c454;font-weight:bold;")
                self.launchbox_path.setText("Executável: —")
                self.launchbox_metadata.setText("Metadata DB: —")
                self.launchbox_launch_button.setEnabled(False)
                self.launchbox_metadata_button.setEnabled(False)
                self.no_intro_test_button.setEnabled(False)
                self.redump_test_button.setEnabled(False)
        except Exception as exc:
            logger.exception("[LAUNCHBOX] Falha ao descobrir LaunchBox")

    def _launchbox_names(self) -> tuple[str, ...]:
        """Return every platform from LaunchBox Platforms.xml, without source filtering."""
        return tuple(platform.name for platform in self.launchbox_provider.iter_platforms())

    def test_no_intro_catalog(self) -> None:
        """Match all LaunchBox platforms against the No-Intro catalog."""
        try:
            entries = self.dat_catalog.fetch_catalog()
            matches = self.dat_catalog.match(self._launchbox_names(), entries)
            self.no_intro_entries = matches
            self.no_intro_systems.clear()
            for entry in matches:
                self.no_intro_systems.addItem(Path(entry.name).stem, entry)
            self._set_no_intro_download_enabled(bool(matches))
            self._refresh_freshness("no_intro")
            logger.info("[NO-INTRO][MATCH] LaunchBox=%d matches=%d", len(self._launchbox_names()), len(matches))
        except Exception as exc:
            logger.exception("[NO-INTRO][MATCH] Falha no catálogo")
            self.no_intro_status.setText(f"● Erro: {exc}")
            self._set_no_intro_download_enabled(False)

    def test_redump_catalog(self) -> None:
        """Match every LaunchBox platform against the complete Redump catalog."""
        try:
            platforms = self._launchbox_names()
            entries = self.redump.fetch_catalog()
            matches = self.redump.match(platforms, entries)
            self.redump_entries = matches
            self.redump_systems.clear()
            for entry in matches:
                self.redump_systems.addItem(Path(entry.name).stem, entry)
            self._set_redump_download_enabled(bool(matches))
            self._refresh_freshness("redump")
            logger.info("[REDUMP][MATCH] LaunchBox=%d RedumpDATs=%d matches=%d", len(platforms), len(entries), len(matches))
        except Exception as exc:
            logger.exception("[REDUMP][MATCH] Falha no catálogo")
            self.redump_status.setText(f"● Erro: {exc}")
            self._set_redump_download_enabled(False)

    def download_selected_no_intro(self) -> None:
        """Download the selected No-Intro DAT."""
        if not self.no_intro_entries:
            return
        try:
            entry = self.no_intro_entries[self.no_intro_systems.currentIndex()]
            status = self.dat_catalog.download(entry)
            self._refresh_freshness("no_intro")
            QMessageBox.information(self, "No-Intro", f"DAT validado.\n\n{status.path}")
        except DatCatalogError as exc:
            QMessageBox.warning(self, "No-Intro", str(exc))

    def download_selected_redump(self) -> None:
        """Download the selected Redump DAT."""
        if not self.redump_entries:
            return
        try:
            entry = self.redump_entries[self.redump_systems.currentIndex()]
            status = self.redump.download(entry)
            self._refresh_freshness("redump")
            QMessageBox.information(self, "Redump", f"DAT validado.\n\n{status.path}")
        except RedumpError as exc:
            QMessageBox.warning(self, "Redump", str(exc))

    def _batch_download(self, source: str, outdated_only: bool) -> None:
        """Download all missing/outdated entries from one source."""
        entries = self.no_intro_entries if source == "no_intro" else self.redump_entries
        if not entries:
            return
        provider = self.dat_catalog if source == "no_intro" else self.redump
        candidates = [entry for entry in entries if not outdated_only or provider.status(entry).state != "current"]
        if not candidates:
            self._refresh_freshness(source)
            return
        succeeded = 0
        failed: list[str] = []
        for index, entry in enumerate(candidates, 1):
            self._set_source_status(source, f"● Baixando {index}/{len(candidates)} — {entry.name}")
            QApplication.processEvents()
            try:
                provider.download(entry)
                succeeded += 1
            except Exception as exc:
                failed.append(f"{entry.name}: {exc}")
                logger.exception("[%s][BATCH] FALHA sistema=%s", source.upper(), entry.name)
        self._refresh_freshness(source)
        detail = f"Concluídos: {succeeded}/{len(candidates)}"
        if failed:
            detail += "\n\nFalhas:\n" + "\n".join(failed[:10])
        QMessageBox.information(self, source.title(), detail)

    def _refresh_freshness(self, source: str) -> None:
        """Refresh current/outdated/missing counters for a source."""
        entries = self.no_intro_entries if source == "no_intro" else self.redump_entries
        provider = self.dat_catalog if source == "no_intro" else self.redump
        if not entries:
            return
        statuses = tuple(provider.status(entry) for entry in entries)
        current = sum(item.state == "current" for item in statuses)
        outdated = sum(item.state == "outdated" for item in statuses)
        missing = sum(item.state == "missing" for item in statuses)
        self._set_source_status(source, f"● {len(statuses)} sistemas — atuais: {current} | desatualizados: {outdated} | ausentes: {missing}")
        button = self.no_intro_update_button if source == "no_intro" else self.redump_update_button
        button.setEnabled(bool(outdated or missing))

    def _set_source_status(self, source: str, text: str) -> None:
        """Set the status label for one catalog source."""
        label = self.no_intro_status if source == "no_intro" else self.redump_status
        label.setText(text)
        label.setStyleSheet("color:#e5c454;font-weight:bold;")

    def _set_no_intro_download_enabled(self, enabled: bool) -> None:
        """Enable or disable No-Intro acquisition controls."""
        for widget in (self.no_intro_systems, self.no_intro_download_button, self.no_intro_download_all_button, self.no_intro_update_button):
            widget.setEnabled(enabled)

    def _set_redump_download_enabled(self, enabled: bool) -> None:
        """Enable or disable Redump acquisition controls."""
        for widget in (self.redump_systems, self.redump_download_button, self.redump_download_all_button, self.redump_update_button):
            widget.setEnabled(enabled)

    def select_launchbox(self) -> None:
        """Select and persist a LaunchBox executable."""
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar LaunchBox.exe", str(Path.home()), "LaunchBox (LaunchBox.exe)")
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
