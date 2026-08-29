"""SERM V2 Home page."""
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
from ..sources.acquisition.dat_catalog import (
    DatCatalogEntry,
    DatCatalogError,
    PublicDatCatalogProvider,
)

logger = logging.getLogger(__name__)


class HomePage(QWidget):
    """Present LaunchBox status and Public DAT Catalog acquisition."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.launchbox = LaunchBoxIntegration()
        self.launchbox_provider = LaunchBoxProvider(self.launchbox)
        self.dat_catalog = PublicDatCatalogProvider()
        self.no_intro_entries: tuple[DatCatalogEntry, ...] = ()
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
        grid.addWidget(self._create_launchbox_card(), 0, 0)
        grid.addWidget(self._create_no_intro_card(), 0, 1)
        grid.addWidget(self._create_placeholder_card("Emuladores", "Runtime V2 será conectado nesta camada."), 1, 0)
        grid.addWidget(self._create_placeholder_card("Biblioteca", "Scan e matching serão conectados nesta camada."), 1, 1)
        layout.addWidget(status_frame)
        footer = QLabel("V2 usa fontes de DAT desacopladas de páginas web interativas.")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color:#888;font-size:10px;")
        layout.addWidget(footer)
        layout.addStretch(1)

    def _create_launchbox_card(self) -> QFrame:
        """Create the LaunchBox integration card."""
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

    def _create_no_intro_card(self) -> QFrame:
        """Create No-Intro catalog discovery and update actions."""
        card = QFrame()
        card.setObjectName("integrationCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        name = QLabel("No-Intro / Public DAT Catalog")
        name.setObjectName("integrationName")
        layout.addWidget(name)
        self.no_intro_status = QLabel("Aguardando teste…")
        self.no_intro_status.setObjectName("detail")
        layout.addWidget(self.no_intro_status)
        self.no_intro_systems = QComboBox()
        self.no_intro_systems.setPlaceholderText("Sistemas do LaunchBox encontrados no catálogo")
        self.no_intro_systems.setEnabled(False)
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
        download_all = QPushButton("⬇ Baixar todos listados")
        download_all.clicked.connect(self.download_all_no_intro)
        row.addWidget(download_all)
        self.no_intro_download_all_button = download_all
        update = QPushButton("🔄 Atualizar desatualizados")
        update.clicked.connect(self.update_outdated_no_intro)
        row.addWidget(update)
        self.no_intro_update_button = update
        layout.addLayout(row)
        return card

    @staticmethod
    def _create_placeholder_card(title: str, detail: str) -> QFrame:
        """Create a non-operational V2 domain card."""
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
        """Refresh LaunchBox discovery."""
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
            else:
                self.launchbox_status.setText("● Não configurado")
                self.launchbox_status.setStyleSheet("color:#e5c454;font-weight:bold;")
                self.launchbox_path.setText("Executável: —")
                self.launchbox_metadata.setText("Metadata DB: —")
                self.launchbox_launch_button.setEnabled(False)
                self.launchbox_metadata_button.setEnabled(False)
                self.no_intro_test_button.setEnabled(False)
                self._set_no_intro_download_enabled(False)
        except Exception as exc:
            logger.exception("[LAUNCHBOX] Falha ao descobrir LaunchBox")
            self.launchbox_status.setText(f"● Erro: {type(exc).__name__}")
            self.launchbox_launch_button.setEnabled(False)
            self.launchbox_metadata_button.setEnabled(False)
            self.no_intro_test_button.setEnabled(False)
            self._set_no_intro_download_enabled(False)

    def test_no_intro_catalog(self) -> None:
        """Fetch the public DAT index and match its No-Intro systems to LaunchBox."""
        try:
            logger.info("[NO-INTRO][MATCH] Iniciando cruzamento LaunchBox x Public DAT Catalog")
            entries = self.dat_catalog.fetch_catalog()
            platforms = tuple(self.launchbox_provider.iter_platforms())
            names = tuple(platform.name for platform in platforms)
            matches = self.dat_catalog.match(names, entries)
            self.no_intro_entries = matches
            self.no_intro_systems.clear()
            for entry in matches:
                self.no_intro_systems.addItem(Path(entry.name).stem, entry)
            self.no_intro_systems.setEnabled(bool(matches))
            self._set_no_intro_download_enabled(bool(matches))
            self._refresh_freshness()
        except Exception as exc:
            logger.exception("[NO-INTRO][MATCH] Falha no catálogo")
            self.no_intro_status.setText(f"● Erro: {exc}")
            self.no_intro_status.setStyleSheet("color:#e05b5b;font-weight:bold;")
            self.no_intro_entries = ()
            self._set_no_intro_download_enabled(False)

    def download_selected_no_intro(self) -> None:
        """Download and validate the selected DAT."""
        if not self.no_intro_entries:
            return
        entry = self.no_intro_entries[self.no_intro_systems.currentIndex()]
        try:
            status = self.dat_catalog.download(entry)
            self._refresh_freshness()
            QMessageBox.information(self, "No-Intro", f"DAT baixado e validado.\n\n{status.path}")
        except DatCatalogError as exc:
            logger.exception("[NO-INTRO][DAT] Falha no sistema=%s", entry.name)
            QMessageBox.warning(self, "No-Intro", str(exc))

    def download_all_no_intro(self) -> None:
        """Download every matched DAT, validating each file before accepting it."""
        self._batch_download(outdated_only=False)

    def update_outdated_no_intro(self) -> None:
        """Download only DATs that are missing or differ from the current catalog revision."""
        self._batch_download(outdated_only=True)

    def _batch_download(self, *, outdated_only: bool) -> None:
        """Run the selected batch operation while keeping the GUI responsive."""
        entries = self.no_intro_entries
        if not entries:
            return
        candidates = [entry for entry in entries if not outdated_only or self.dat_catalog.status(entry).state != "current"]
        if not candidates:
            self.no_intro_status.setText("● Todos os DATs estão atuais")
            self.no_intro_status.setStyleSheet("color:#55d66b;font-weight:bold;")
            QMessageBox.information(self, "No-Intro", "Nenhum DAT precisa de atualização.")
            return
        succeeded = 0
        failed: list[str] = []
        total = len(candidates)
        self.no_intro_test_button.setEnabled(False)
        self._set_no_intro_download_enabled(False)
        try:
            for index, entry in enumerate(candidates, start=1):
                self.no_intro_status.setText(f"● {'Atualizando' if outdated_only else 'Baixando'} {index}/{total} — {entry.name}")
                QApplication.processEvents()
                try:
                    self.dat_catalog.download(entry)
                    succeeded += 1
                except Exception as exc:
                    failed.append(f"{entry.name}: {exc}")
                    logger.exception("[NO-INTRO][BATCH] FALHA sistema=%s", entry.name)
            self._refresh_freshness()
            detail = f"Concluídos: {succeeded}/{total}"
            if failed:
                detail += "\n\nFalhas:\n" + "\n".join(failed[:10])
            QMessageBox.information(self, "No-Intro", detail)
        finally:
            self.no_intro_test_button.setEnabled(True)
            self._set_no_intro_download_enabled(bool(self.no_intro_entries))
            self._refresh_freshness()

    def _refresh_freshness(self) -> None:
        """Refresh current/outdated/missing counters from local CRC validation."""
        if not self.no_intro_entries:
            self.no_intro_update_button.setEnabled(False)
            return
        statuses = tuple(self.dat_catalog.status(entry) for entry in self.no_intro_entries)
        current = sum(item.state == "current" for item in statuses)
        outdated = sum(item.state == "outdated" for item in statuses)
        missing = sum(item.state == "missing" for item in statuses)
        self.no_intro_update_button.setEnabled(bool(outdated or missing))
        self.no_intro_status.setText(
            f"● {len(statuses)} sistemas — atuais: {current} | desatualizados: {outdated} | ausentes: {missing}"
        )
        self.no_intro_status.setStyleSheet(
            "color:#e5c454;font-weight:bold;" if (outdated or missing) else "color:#55d66b;font-weight:bold;"
        )
        logger.info("[NO-INTRO][FRESHNESS] atuais=%d desatualizados=%d ausentes=%d", current, outdated, missing)

    def _set_no_intro_download_enabled(self, enabled: bool) -> None:
        """Enable or disable No-Intro acquisition actions."""
        self.no_intro_systems.setEnabled(enabled)
        self.no_intro_download_button.setEnabled(enabled)
        self.no_intro_download_all_button.setEnabled(enabled)
        self.no_intro_update_button.setEnabled(enabled)

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
