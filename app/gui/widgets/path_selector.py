"""Seletor reutilizável de arquivo ou diretório para a GUI."""
from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QFileDialog, QWidget


class PathSelector(QWidget):
    """Campo de caminho com botão compacto e seleção gráfica."""

    def __init__(self, mode: str = "directory", placeholder: str = "", parent=None) -> None:
        super().__init__(parent)
        self.mode = mode
        self.edit = QLineEdit(self)
        self.edit.setPlaceholderText(placeholder)
        self.button = QPushButton("...")
        self.button.setFixedWidth(36)
        self.button.clicked.connect(self._browse)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.button)

    def _browse(self) -> None:
        """Abre o seletor correspondente ao tipo configurado."""
        current = self.edit.text().strip()
        if self.mode == "file":
            value, _ = QFileDialog.getOpenFileName(self, "Selecionar arquivo", current)
        else:
            value = QFileDialog.getExistingDirectory(self, "Selecionar diretório", current)
        if value:
            self.edit.setText(value)
            self.edit.editingFinished.emit()

    def set_path(self, path: str | Path | None) -> None:
        """Define o caminho exibido."""
        self.edit.setText(str(path) if path else "")

    def path(self) -> Path | None:
        """Retorna o caminho atual ou None quando vazio."""
        value = self.edit.text().strip()
        return Path(value) if value else None
