"""Janela principal do SERM V2."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from ..config.settings import Settings
from ..database.bootstrap import apply_migrations
from ..database.engine import create_sqlite_engine
from .dat_scraper import DatScraperPage
from .emulator_directories_page import DirectoriesPage
from .emulator_settings_page import EmulatorSettingsPage
from .emulator_shaders_bezels_page import EmulatorShadersBezelsPage
from .home import HomePage
from .log_handler import LogViewer
from .mame_guides_page import MameGuidesPage


class MainWindow(QMainWindow):
    """Janela principal otimizada para telas 16:9."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SERM V2")
        self.resize(1280, 720)
        self.setMinimumSize(1152, 648)
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Pronto")

        settings = Settings()
        database_path = Path(settings.database)
        applied = apply_migrations(database_path)
        if applied:
            logging.getLogger(__name__).info("[SERM][DB] migrations aplicadas=%s", ", ".join(applied))
        self.database = create_sqlite_engine(database_path)
        self.log_viewer = LogViewer()
        self._build_ui()

    def _build_ui(self) -> None:
        """Monta a navegação principal sem duplicar funcionalidades."""
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(QLabel("SERM V2"))
        self.tab_widget = QTabWidget()
        self.home_section = HomePage(self)
        self.directories_tab = DirectoriesPage(self)
        self.settings_tab = EmulatorSettingsPage(self)
        self.visuals_tab = EmulatorShadersBezelsPage(self)
        self.mame_guides_tab = MameGuidesPage(self)
        self.dat_scraper_tab = DatScraperPage(self)
        self.tab_widget.addTab(self.home_section, "Home")
        self.tab_widget.addTab(self.directories_tab, "Diretórios")
        self.tab_widget.addTab(self.settings_tab, "Configurações")
        self.tab_widget.addTab(self.visuals_tab, "Shaders / Bezels")
        self.tab_widget.addTab(self.mame_guides_tab, "MAME")
        self.tab_widget.addTab(self.dat_scraper_tab, "Scraper de DATs")
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tab_widget, 1)
        self.setCentralWidget(root)

    def _on_tab_changed(self, index: int) -> None:
        """Atualiza somente o componente selecionado."""
        widget = self.tab_widget.widget(index)
        if widget is self.home_section:
            self.home_section.refresh()
        elif widget is self.directories_tab:
            self.directories_tab.refresh()
        elif widget is self.settings_tab:
            self.settings_tab.refresh()
        elif widget is self.visuals_tab:
            self.visuals_tab.refresh()
        elif widget is self.mame_guides_tab:
            self.mame_guides_tab.refresh()
        elif widget is self.dat_scraper_tab:
            self.dat_scraper_tab.setFocus()

    def closeEvent(self, event) -> None:  # noqa: N802
        """Fecha os recursos locais da aplicação."""
        self.log_viewer.close()
        self.database.dispose()
        super().closeEvent(event)
