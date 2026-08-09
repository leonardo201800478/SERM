"""
Tabela de máquinas selecionadas.
"""

from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt
from typing import List, Dict, Any

class MachinesTable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([
            "Nome", "Descrição", "Ano", "Fabricante", "Clone de", "Categoria", "Emulação"
        ])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setSortingEnabled(True)

    def set_machines(self, machines: List[Dict[str, Any]]):
        self.setRowCount(len(machines))
        for row, mach in enumerate(machines):
            self.setItem(row, 0, QTableWidgetItem(mach.get("name", "")))
            self.setItem(row, 1, QTableWidgetItem(mach.get("description", "")))
            self.setItem(row, 2, QTableWidgetItem(mach.get("year", "")))
            self.setItem(row, 3, QTableWidgetItem(mach.get("manufacturer", "")))
            self.setItem(row, 4, QTableWidgetItem(mach.get("cloneof") or ""))
            self.setItem(row, 5, QTableWidgetItem(mach.get("category", "")))
            self.setItem(row, 6, QTableWidgetItem(mach.get("emulation", "")))