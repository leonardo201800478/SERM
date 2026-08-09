"""
Widget para editar uma lista de caminhos (ex.: múltiplas pastas de ROMs).
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox
)
from PyQt6.QtCore import pyqtSignal

class PathListEditor(QWidget):
    """Lista editável de caminhos."""
    pathsChanged = pyqtSignal(list)

    def __init__(self, max_items: int = 5, placeholder: str = "Adicionar caminho", parent=None):
        super().__init__(parent)
        self.max_items = max_items
        self._setup_ui(placeholder)

    def _setup_ui(self, placeholder: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Lista
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.list_widget)

        # Botões
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Adicionar Pasta")
        self.add_btn.clicked.connect(self._add_path)
        self.remove_btn = QPushButton("Remover Selecionado")
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn = QPushButton("Limpar Todos")
        self.clear_btn.clicked.connect(self.clear)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.clear_btn)
        layout.addLayout(btn_layout)

        self.setPlaceholderText(placeholder)

    def _add_path(self):
        if self.list_widget.count() >= self.max_items:
            QMessageBox.warning(self, "Limite", f"Máximo de {self.max_items} pastas permitidas.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Selecionar pasta")
        if folder:
            self.addPath(folder)

    def _remove_selected(self):
        current = self.list_widget.currentRow()
        if current >= 0:
            self.list_widget.takeItem(current)
            self.pathsChanged.emit(self.getPaths())

    def addPath(self, path: str):
        if self.list_widget.count() >= self.max_items:
            return
        self.list_widget.addItem(path)
        self.pathsChanged.emit(self.getPaths())

    def setPaths(self, paths: list):
        self.clear()
        for p in paths:
            if p.strip():
                self.list_widget.addItem(p.strip())
        self.pathsChanged.emit(self.getPaths())

    def getPaths(self) -> list:
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]

    def clear(self):
        self.list_widget.clear()
        self.pathsChanged.emit([])

    def setPlaceholderText(self, text: str):
        # Não há placeholder direto para QListWidget, mas podemos definir um item fantasma
        # Simplesmente ignoramos.
        pass