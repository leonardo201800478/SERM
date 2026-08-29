"""SERM V2 Home page with LaunchBox, No-Intro and Redump acquisition."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
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
from ..sources.acquisition.dat_catalog import DatCatalogError, PublicDatCatalogProvider
from ..sources.acquisition.redump import RedumpError, RedumpProvider

logger = logging.getLogger(__name__)


class HomePage(QWidget):
    """Present LaunchBox status and independent public DAT catalogs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.launchbox = LaunchBoxIntegration()
        self.launchbox_provider = LaunchBoxProvider(self.launchbox)
        self.no_intro = PublicDatCatalogProvider()
        self.redump = RedumpProvider()
        self.no_intro_entries = ()
        self.redump_entries = ()
        self._build_ui()
        self.refresh_status()

    def _build_ui(self) -> None:
        """Build the V2 home surface."""
        layout = QVBoxLayout(self)
        title = QLabel("SERM")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:28px;font-weight:700;")
        layout.addWidget(title)
        subtitle = QLabel("Strife Emulator and Roms Manager")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        frame = QFrame()
        frame.setObjectName("statusFrame")
        frame.setStyleSheet(
            "QFrame#statusFrame{background:#151515;border:1px solid #3d3d3d;border-radius:8px;padding:10px;}"
            "QFrame#integrationCard{background:#202020;border:1px solid #414141;border-radius:7px;}"
            "QLabel#integrationName{font-size:15px;font-weight:bold;}"
            "QLabel#detail{color:#b8b8b8;}"
        )
        grid = QGridLayout(frame)
        grid.addWidget(self._launchbox_card(), 0, 0, 1, 2)
        grid.addWidget(self._source_card("No-Intro / Public DAT Catalog", "no_intro"), 1, 0)
        grid.addWidget(self._source_card("Redump / Public DAT Catalog", "redump"), 1, 1)
        layout.addWidget(frame)
        footer = QLabel("DAT-o-MATIC não é usado. As fontes são catálogos públicos com links diretos.")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color:#888;font-size:10px;")
        layout.addWidget(footer)
        layout.addStretch(1)

    def _launchbox_card(self) -> QFrame:
        """Create the LaunchBox status card."""
        card = QFrame()
        card.setObjectName("integrationCard")
        layout = QVBoxLayout(card)
        name = QLabel("LaunchBox")
        name.setObjectName("integrationName")
        layout.addWidget(name)
        self.launchbox_status = self._detail("Verificando…")
        self.launchbox_path = self._detail("Executável: —")
        self.launchbox_metadata = self._detail("Metadata DB: —")
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

    @staticmethod
    def _detail(text: str) -> QLabel:
        """Create a detail label using the shared object name."""
        label = QLabel(text)
        label.setObjectName("detail")
        label.setWordWrap(True)
        return label

    def _source_card(self, title: str, source: str) -> QFrame:
        """Create a DAT acquisition card for No-Intro or Redump."""
        card = QFrame()
        card.setObjectName("integrationCard")
        layout = QVBoxLayout(card)
        name = QLabel(title)
        name.setObjectName("integrationName")
        layout.addWidget(name)
        status = self._detail("Aguardando catálogo…")
        combo = QComboBox()
        combo.setPlaceholderText("Sistemas do LaunchBox encontrados")
        row = QHBoxLayout()
        refresh = QPushButton("🌐 Atualizar catálogo")
        refresh.clicked.connect(lambda: self._refresh_source(source))
        row.addWidget(refresh)
        download = QPushButton("⬇ Baixar")
        download.clicked.connect(lambda: self._download_selected(source))
        row.addWidget(download)
        download_all = QPushButton("⬇ Todos")
        download_all.clicked.connect(lambda: self._download_all(source))
        row.addWidget(download_all)
        update = QPushButton("🔄 Atualizar")
        update.clicked.connect(lambda: self._download_all(source, outdated_only=True))
        row.addWidget(update)
        layout.addWidget(status)
        layout.addWidget(combo)
        layout.addLayout(row)
        setattr(self, f"{source}_status", status)
        setattr(self, f"{source}_combo", combo)
        setattr(self, f"{source}_refresh", refresh)
        setattr(self, f"{source}_download", download)
        setattr(self, f"{source}_all", download_all)
        setattr(self, f"{source}_update", update)
        self._set_source_enabled(source, False)
        return card

    def refresh_status(self) -> None:
        """Refresh LaunchBox discovery and enable catalog actions when available."""
        try:
            executable = self.launchbox.discover()
            available = executable is not None and self.launchbox.metadata_database() is not None
            self.launchbox_launch_button.setEnabled(executable is not None)
            self.launchbox_metadata_button.setEnabled(available)
            if executable:
                self.launchbox_status.setText("● Disponível")
                self.launchbox_path.setText(f"Executável: {executable}")
                self.launchbox_metadata.setText(f"Metadata DB: {self.launchbox.metadata_database() or 'não localizado'}")
            else:
                self.launchbox_status.setText("● Não configurado")
        except Exception as exc:
            logger.exception("[LAUNCHBOX] Falha ao descobrir LaunchBox")
            self.launchbox_status.setText(f"● Erro: {exc}")

    def _launchbox_names(self) -> tuple[str, ...]:
        """Return every platform from LaunchBox Platforms.xml, with no source filtering."""
        return tuple(platform.name for platform in self.launchbox_provider.iter_platforms())

    def _refresh_source(self, source: str) -> None:
        """Fetch a complete source catalog and match it against every LaunchBox platform."""
        try:
            names = self._launchbox_names()
            if source == "no_intro":
                entries = self.no_intro.fetch_catalog()
                matches = self.no_intro.match(names, entries)
            else:
                entries = self.redump.fetch_catalog()
                matches = self.redump.match(names, entries)
            setattr(self, f"{source}_entries", matches)
            combo: QComboBox = getattr(self, f"{source}_combo")
            combo.clear()
            for entry in matches:
                combo.addItem(Path(entry.name).stem, entry)
            self._set_source_enabled(source, bool(matches))
            self._refresh_source_status(source)
            logger.info("[%s][MATCH] LaunchBox=%d catalog=%d matches=%d", source.upper(), len(names), len(entries), len(matches))
        except Exception as exc:
            logger.exception("[%s][MATCH] Falha", source.upper())
            getattr(self, f"{source}_status").setText(f"● Erro: {exc}")
            self._set_source_enabled(source, False)

    def _refresh_source_status(self, source: str) -> None:
        """Update current/outdated/missing counters for one source."""
        entries = getattr(self, f"{source}_entries")
        if not entries:
            getattr(self, f"{source}_status").setText("● Nenhum sistema compatível encontrado")
            return
        provider = self.no_intro if source == "no_intro" else self.redump
        statuses = tuple(provider.status(entry) for entry in entries)
        current = sum(item.state == "current" for item in statuses)
        outdated = sum(item.state == "outdated" for item in statuses)
        missing = sum(item.state == "missing" for item in statuses)
        getattr(self, f"{source}_status").setText(
            f"● {len(statuses)} sistemas — atuais: {current} | desatualizados: {outdated} | ausentes: {missing}"
        )
        getattr(self, f"{source}_update").setEnabled(bool(outdated or missing))

    def _set_source_enabled(self, source: str, enabled: bool) -> None:
        """Enable or disable acquisition controls for one source."""
        for suffix in ("combo", "download", "all", "update"):
            getattr(self, f"{source}_{suffix}").setEnabled(enabled)

    def _download_selected(self, source: str) -> None:
        """Download the selected DAT and validate it."""
        entries = getattr(self, f"{source}_entries")
        combo: QComboBox = getattr(self, f"{source}_combo")
        if not entries:
            return
        entry = entries[combo.currentIndex()]
        try:
            provider = self.no_intro if source == "no_intro" else self.redump
            status = provider.download(entry)
            self._refresh_source_status(source)
            QMessageBox.information(self, source.title(), f"DAT validado.\n\n{status.path}")
        except (DatCatalogError, RedumpError) as exc:
            QMessageBox.warning(self, source.title(), str(exc))

    def _download_all(self, source: str, outdated_only: bool = False) -> None:
        """Download all matched DATs or only missing/outdated entries."""
        entries = getattr(self, f"{source}_entries")
        if not entries:
            return
        provider = self.no_intro if source == "no_intro" else self.redump
        candidates = [entry for entry in entries if not outdated_only or provider.status(entry).state != "current"]
        if not candidates:
            self._refresh_source_status(source)
            return
        failed = []
        for entry in candidates:
            try:
                provider.download(entry)
            except Exception as exc:
                failed.append(f"{entry.name}: {exc}")
        self._refresh_source_status(source)
        message = f"Concluídos: {len(candidates) - len(failed)}/{len(candidates)}"
        if failed:
            message += "\n\nFalhas:\n" + "\n".join(failed[:10])
        QMessageBox.information(self, source.title(), message)

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
        """Start LaunchBox."""
        try:
            self.launchbox.launch()
        except (FileNotFoundError, OSError) as exc:
            QMessageBox.warning(self, "LaunchBox", str(exc))

    def open_metadata_folder(self) -> None:
        """Open LaunchBox's Metadata directory."""
        database = self.launchbox.metadata_database()
        if database is None:
            QMessageBox.information(self, "LaunchBox", "LaunchBox.Metadata.db não foi localizado.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(database.parent)))
