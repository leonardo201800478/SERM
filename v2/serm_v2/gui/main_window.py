"""Janela principal do SERM V2."""
from __future__ import annotations

from app.config.app_config import AppConfig
from app.database.database import Database
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from .dat_scraper import DatScraperPage
from .directories_page import DirectoriesPage
from .home import HomePage
from .log_handler import LogViewer


class MainWindow(QMainWindow):
    """Janela principal com Home, Diretórios unificados e Scraper de DATs."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SERM")
        self.resize(1280, 820)
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Pronto")
        self.config = AppConfig()
        self.db = Database(self.config.db_path)
        self.db.connect()
        self.log_viewer = LogViewer()
        self._build_ui()

    def _build_ui(self) -> None:
        """Monta a navegação sem duplicar Diretórios, No-Intro ou Redump."""
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(QLabel("SERM V2"))
        self.tab_widget = QTabWidget()
        self.home_section = HomePage(self)
        self.directories_tab = DirectoriesPage(self)
        self.dat_scraper_tab = DatScraperPage(self)
        self.tab_widget.addTab(self.home_section, "Home")
        self.tab_widget.addTab(self.directories_tab, "Diretórios")
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

    def closeEvent(self, event) -> None:  # noqa: N802
        """Fecha os recursos locais da aplicação."""
        self.log_viewer.close()
        self.db.close()
        super().closeEvent(event)
