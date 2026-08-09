"""
Janela principal com abas do MAME Set Builder.
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
from .video_tab import VideoTab
from .shader_tab import ShaderTab
from .build_tab import BuildTab


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

        # Aba Home – versão do MAME e informações
        self.home_tab = HomeTab(self)
        self.tab_widget.addTab(self.home_tab, "Home")

        # Aba Configuração – executável, diretórios, mame.ini
        self.config_tab = ConfigTab(self)
        self.tab_widget.addTab(self.config_tab, "Configuração")

        # Aba Filtros – seleção de categorias, emulação, etc.
        self.filters_tab = FiltersTab(self)
        self.tab_widget.addTab(self.filters_tab, "Filtros")

        # Aba Máquinas – tabela com os resultados dos filtros
        self.machines_table = MachinesTable()
        self.tab_widget.addTab(self.machines_table, "Máquinas")

        # Aba Config MAME – edição avançada do mame.ini (vídeo, áudio, etc.)
        self.mame_config_tab = MameConfigTab(self)
        self.tab_widget.addTab(self.mame_config_tab, "Config MAME")

        # Aba Vídeo – driver, chains BGFX, effects, prescale, filtros
        self.video_tab = VideoTab(self)
        self.tab_widget.addTab(self.video_tab, "Vídeo")

        # Aba Efeitos – parâmetros HLSL/GLSL (scanlines, bloom, shadow mask)
        self.shader_tab = ShaderTab(self)
        self.tab_widget.addTab(self.shader_tab, "Efeitos")

        # Aba Construção – construção do Meu Set a partir do FULLSET
        self.build_tab = BuildTab(self)
        self.tab_widget.addTab(self.build_tab, "Construção")

        layout.addWidget(self.tab_widget)

    def _load_config(self):
        """Carrega configurações salvas e atualiza a aba Home."""
        config = Settings.load()
        version = config.get("mame_version", "")
        if version:
            self.home_tab.set_version(version)

    def _load_initial_profile(self):
        """Carrega o perfil inicial (Arcade Only) e aplica os filtros."""
        profile = arcade_only()
        self.apply_profile(profile)

    def apply_profile(self, profile):
        """Aplica um perfil de filtros e atualiza a tabela de máquinas."""
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