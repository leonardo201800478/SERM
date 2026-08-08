"""
Janela principal da aplicação MAME Set Builder.
"""

import sys
import sqlite3
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QFileDialog, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt

from .filters_panel import FiltersPanel
from .machines_table import MachinesTable
from ..filtering.engine import FilterEngine
from ..filtering.profiles import arcade_only, all_systems, consoles_only, computers_only, mechanical_only
from ..domain.set_profile import SetProfile

class MainWindow(QMainWindow):
    def __init__(self, db_path: str):
        super().__init__()
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.filter_engine = FilterEngine(self.conn)
        
        self.setWindowTitle("MAME Set Builder")
        self.setMinimumSize(900, 600)
        
        self._setup_ui()
        self._connect_signals()
        self._load_initial_profile()
    
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.filters_panel = FiltersPanel(self)
        splitter.addWidget(self.filters_panel)
        self.machines_table = MachinesTable()
        splitter.addWidget(self.machines_table)
        splitter.setSizes([300, 600])
        layout.addWidget(splitter)
    
    def _connect_signals(self):
        self.filters_panel.profile_changed.connect(self.apply_profile)
    
    def _load_initial_profile(self):
        profile = arcade_only()
        self.apply_profile(profile)
    
    def apply_profile(self, profile: SetProfile):
        try:
            count = self.filter_engine.count(profile)
            self.filters_panel.update_count(count)
            machines = self.filter_engine.apply(profile)
            self.machines_table.set_machines(machines)
            self.statusBar().showMessage(f"{len(machines)} máquinas exibidas")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao aplicar filtros:\n{str(e)}")
    
    def closeEvent(self, event):
        self.conn.close()
        event.accept()