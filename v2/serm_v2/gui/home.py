"""SERM V2 Home page.

The visual organization follows the proven legacy Home concept, but all
runtime state in V2 is independent. LaunchBox is the first external
integration exposed from the new Home.
"""
from __future__ import annotations

import logging
import re
import unicodedata
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
from ..integrations.launchbox_provider import LaunchBoxPlatform, LaunchBoxProvider
from ..sources.no_intro.catalog import NoIntroCatalog, NoIntroSystem
from ..sources.no_intro.downloader import NoIntroDownloader

logger = logging.getLogger(__name__)


class HomePage(QWidget):
    """Present the V2 Home and the first external integration status."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.launchbox = LaunchBoxIntegration()
        self.launchbox_provider = LaunchBoxProvider(self.launchbox)
        self.no_intro_catalog = NoIntroCatalog()
        self.no_intro_downloader = NoIntroDownloader()
        self.no_intro_matches: tuple[NoIntroSystem, ...] = ()
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
        grid.addWidget(self._create_no_intro_card(), 0, 1)
        grid.addWidget(self._create_placeholder_card("Emuladores", "Runtime V2 será conectado nesta camada."), 1, 0)
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

    def _create_no_intro_card(self) -> QFrame:
        """Create No-Intro discovery and download actions."""
        card = QFrame()
        card.setObjectName("integrationCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        name = QLabel("No-Intro / DAT-o-MATIC")
        name.setObjectName("integrationName")
        layout.addWidget(name)
        self.no_intro_status = QLabel("Aguardando teste…")
        self.no_intro_status.setObjectName("detail")
        layout.addWidget(self.no_intro_status)
        self.no_intro_systems = QComboBox()
        self.no_intro_systems.setPlaceholderText("Sistemas do LaunchBox encontrados no No-Intro")
        self.no_intro_systems.setEnabled(False)
        layout.addWidget(self.no_intro_systems)
        row = QHBoxLayout()
        test = QPushButton("🌐 Testar catálogo")
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
        """Fetch DAT-o-MATIC and show only systems also present in LaunchBox."""
        try:
            logger.info("[NO-INTRO][MATCH] Iniciando cruzamento LaunchBox x DAT-o-MATIC")
            catalog_html = self.no_intro_catalog.fetch_catalog()
            systems = self.no_intro_catalog.systems(catalog_html)
            platforms = tuple(self.launchbox_provider.iter_platforms())
            logger.info("[LAUNCHBOX][PLATFORMS] plataformas carregadas=%d", len(platforms))
            matches = self._match_platforms(platforms, systems)
            self.no_intro_matches = matches
            logger.info("[NO-INTRO][MATCH] resultado=%d correspondência(s)", len(matches))
            self.no_intro_systems.clear()
            for system in matches:
                self.no_intro_systems.addItem(system.name, system)
            self.no_intro_systems.setEnabled(bool(matches))
            self._set_no_intro_download_enabled(bool(matches))
            self.no_intro_status.setText(f"● Catálogo OK — {len(matches)} sistema(s) compatível(is)")
            self.no_intro_status.setStyleSheet("color:#55d66b;font-weight:bold;")
        except Exception as exc:
            logger.exception("[NO-INTRO][MATCH] Falha no teste do catálogo")
            self.no_intro_status.setText(f"● Erro: {exc}")
            self.no_intro_status.setStyleSheet("color:#e05b5b;font-weight:bold;")
            self.no_intro_matches = ()
            self._set_no_intro_download_enabled(False)

    def download_selected_no_intro(self) -> None:
        """Generate and download the currently selected No-Intro DAT."""
        if not self.no_intro_matches:
            return
        system = self.no_intro_matches[self.no_intro_systems.currentIndex()]
        try:
            destination = self._no_intro_destination(system)
            result = self.no_intro_downloader.download_system(system.name, destination)
            self.no_intro_status.setText(f"● DAT OK — {system.name}")
            self.no_intro_status.setStyleSheet("color:#55d66b;font-weight:bold;")
            QMessageBox.information(self, "No-Intro", f"DAT baixado com sucesso.\n\n{result.path}")
        except Exception as exc:
            logger.exception("[NO-INTRO][DAT] Falha no sistema=%s", system.name)
            self.no_intro_status.setText(f"● Falha — {system.name}")
            self.no_intro_status.setStyleSheet("color:#e05b5b;font-weight:bold;")
            QMessageBox.warning(self, "No-Intro", str(exc))

    def download_all_no_intro(self) -> None:
        """Generate and download every No-Intro system currently listed in the GUI."""
        if not self.no_intro_matches:
            return
        total = len(self.no_intro_matches)
        destination_root = self._no_intro_data_root()
        succeeded = 0
        failed: list[str] = []
        self.no_intro_test_button.setEnabled(False)
        self._set_no_intro_download_enabled(False)
        try:
            for index, system in enumerate(self.no_intro_matches, start=1):
                self.no_intro_status.setText(f"● Baixando {index}/{total} — {system.name}")
                QApplication.processEvents()
                logger.info("[NO-INTRO][DAT][BATCH] %d/%d início sistema=%s", index, total, system.name)
                try:
                    result = self.no_intro_downloader.download_system(
                        system.name,
                        self._no_intro_destination(system, destination_root),
                    )
                    succeeded += 1
                    logger.info("[NO-INTRO][DAT][BATCH] %d/%d OK arquivo=%s", index, total, result.path)
                except Exception as exc:
                    failed.append(f"{system.name}: {exc}")
                    logger.exception("[NO-INTRO][DAT][BATCH] %d/%d FALHA sistema=%s", index, total, system.name)
            self.no_intro_status.setText(f"● Download concluído — {succeeded}/{total} OK")
            self.no_intro_status.setStyleSheet("color:#55d66b;font-weight:bold;" if not failed else "color:#e5c454;font-weight:bold;")
            detail = f"Concluídos: {succeeded}/{total}\nPasta: {destination_root}"
            if failed:
                detail += "\n\nFalhas:\n" + "\n".join(failed[:10])
                if len(failed) > 10:
                    detail += f"\n… e mais {len(failed) - 10} falha(s)."
            QMessageBox.information(self, "No-Intro — download em lote", detail)
        finally:
            self.no_intro_test_button.setEnabled(True)
            self._set_no_intro_download_enabled(bool(self.no_intro_matches))

    def _set_no_intro_download_enabled(self, enabled: bool) -> None:
        """Enable or disable both No-Intro download actions."""
        self.no_intro_download_button.setEnabled(enabled)
        self.no_intro_download_all_button.setEnabled(enabled)

    def _no_intro_data_root(self) -> Path:
        """Return the V2 data directory used for downloaded No-Intro DATs."""
        root = Path(__file__).resolve().parents[2] / "data" / "sources" / "no_intro" / "dats"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _no_intro_destination(self, system: NoIntroSystem, root: Path | None = None) -> Path:
        """Build a stable filesystem-safe destination for one source DAT."""
        root = root or self._no_intro_data_root()
        filename = unicodedata.normalize("NFKD", system.name).encode("ascii", "ignore").decode("ascii")
        filename = re.sub(r"[^A-Za-z0-9._ -]+", "", filename).strip().replace(" ", "_")
        return root / f"{filename}.zip"

    @staticmethod
    def _match_platforms(platforms: tuple[LaunchBoxPlatform, ...], systems: tuple[NoIntroSystem, ...]) -> tuple[NoIntroSystem, ...]:
        """Match using exact, normalized and common LaunchBox/No-Intro naming forms."""
        def normalize(value: str) -> str:
            value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
            value = value.casefold().replace("&", "and")
            return re.sub(r"[^a-z0-9]+", " ", value).strip()

        aliases = {
            "nes": "nintendo entertainment system",
            "famicom": "nintendo entertainment system",
            "snes": "super nintendo entertainment system",
            "super nes": "super nintendo entertainment system",
            "genesis": "mega drive genesis",
            "sega genesis": "mega drive genesis",
            "sms": "master system mark iii",
            "master system": "master system mark iii",
            "game boy": "game boy",
            "game boy color": "game boy color",
            "game boy advance": "game boy advance",
        }
        launchbox_names = {normalize(platform.name): platform.name for platform in platforms}
        matches: list[NoIntroSystem] = []
        matched_launchbox: set[str] = set()
        for system in systems:
            normalized_source = normalize(system.name)
            variants = {normalized_source}
            if " - " in system.name:
                variants.add(normalize(system.name.rsplit(" - ", 1)[-1]))
            for variant in tuple(variants):
                if variant in aliases:
                    variants.add(aliases[variant])
            hit = next((variant for variant in variants if variant in launchbox_names), None)
            if hit:
                matches.append(system)
                matched_launchbox.add(hit)
                logger.debug("[MATCH][OK] LaunchBox='%s' <-> No-Intro='%s'", launchbox_names[hit], system.name)
        for normalized, original in launchbox_names.items():
            if normalized not in matched_launchbox:
                logger.debug("[MATCH][MISS] LaunchBox='%s' sem correspondente", original)
        logger.info("[MATCH] LaunchBox=%d | No-Intro=%d | matches=%d", len(platforms), len(systems), len(matches))
        return tuple(matches)

    def test_no_intro_download(self) -> None:
        """Save a DAT-o-MATIC catalog snapshot to V2 data as a legacy connectivity test."""
        try:
            catalog_html = self.no_intro_catalog.fetch_catalog()
            destination = Path(__file__).resolve().parents[2] / "data" / "sources" / "no_intro" / "catalog.html"
            self.no_intro_catalog.save_catalog(catalog_html, destination)
            system = self.no_intro_systems.currentText() or "nenhum sistema selecionado"
            logger.info("[NO-INTRO][DOWNLOAD] snapshot=%s sistema=%s", destination, system)
            self.no_intro_status.setText(f"● Catálogo baixado — {system}")
            self.no_intro_status.setStyleSheet("color:#55d66b;font-weight:bold;")
        except Exception as exc:
            logger.exception("[NO-INTRO][DOWNLOAD] Falha no download de teste")
            self.no_intro_status.setText(f"● Falha no download: {exc}")
            self.no_intro_status.setStyleSheet("color:#e05b5b;font-weight:bold;")
            QMessageBox.warning(self, "No-Intro", str(exc))

    def select_launchbox(self) -> None:
        """Select and persist a LaunchBox.exe outside the SERM repository."""
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
