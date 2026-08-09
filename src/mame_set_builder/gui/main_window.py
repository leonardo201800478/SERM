"""
Janela principal com abas.
"""

import sys
import sqlite3
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QMessageBox, QApplication
)
from .home_tab import HomeTab
from .config_tab import ConfigTab
from .filters_tab import FiltersTab
from .machines_table import MachinesTable
from .settings import Settings
from ..filtering.engine import FilterEngine
from ..filtering.profiles import arcade_only
from .mame_config_tab import MameConfigTab
class MainWindow(QMainWindow):
    def __init__(self, db_path: str):
        super().__init__()
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.filter_engine = FilterEngine(self.conn)

        self.setWindowTitle("MAME Set Builder")
        self.setMinimumSize(1000, 700)

        self._setup_ui()
        self._load_initial_profile()
        self._load_config()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.tab_widget = QTabWidget()

        # Aba Home
        self.home_tab = HomeTab(self)
        self.tab_widget.addTab(self.home_tab, "Home")

        # Aba Configuração
        self.config_tab = ConfigTab(self)
        self.tab_widget.addTab(self.config_tab, "Configuração")

        # Aba Filtros
        self.filters_tab = FiltersTab(self)
        self.tab_widget.addTab(self.filters_tab, "Filtros")

        # Aba Máquinas (tabela)
        self.machines_table = MachinesTable()
        self.tab_widget.addTab(self.machines_table, "Máquinas")

        self.mame_config_tab = MameConfigTab(self)
        self.tab_widget.addTab(self.mame_config_tab, "Config MAME")

        # Futuras abas: Manifesto, Construção, etc.

        layout.addWidget(self.tab_widget)

    def _load_config(self):
        """Carrega configurações e atualiza a Home."""
        config = Settings.load()
        version = config.get("mame_version", "")
        if version:
            self.home_tab.set_version(version)

    def _load_initial_profile(self):
        """Carrega perfil inicial (Arcade Only) e aplica."""
        profile = arcade_only()
        self.apply_profile(profile)

    def apply_profile(self, profile):
        try:
            count = self.filter_engine.count(profile)
            self.filters_tab.update_count(count)
            machines = self.filter_engine.apply(profile)
            self.machines_table.set_machines(machines)
            self.statusBar().showMessage(f"{len(machines)} máquinas exibidas")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao aplicar filtros:\n{str(e)}")

    def get_config(self) -> dict:
        """Retorna a configuração atual (da aba Configuração)."""
        return self.config_tab.get_config()

    def closeEvent(self, event):
        self.conn.close()
        event.accept()