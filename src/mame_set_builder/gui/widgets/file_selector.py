"""
Widget reutilizável: campo de texto + botão "Procurar" para arquivo ou pasta.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QFileDialog
from PyQt6.QtCore import pyqtSignal

class FileSelector(QWidget):
    """Seletor de arquivo ou pasta com campo de texto e botão."""
    textChanged = pyqtSignal(str)

    def __init__(self, placeholder: str = "", file_mode: bool = True, parent=None):
        """
        :param placeholder: texto de placeholder
        :param file_mode: True para arquivo, False para pasta
        """
        super().__init__(parent)
        self.file_mode = file_mode
        self._setup_ui(placeholder)

    def _setup_ui(self, placeholder: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self.line = QLineEdit()
        self.line.setPlaceholderText(placeholder)
        self.line.textChanged.connect(self.textChanged.emit)

        self.btn = QPushButton("...")
        self.btn.setFixedWidth(30)
        self.btn.clicked.connect(self._browse)

        layout.addWidget(self.line, 1)
        layout.addWidget(self.btn)

    def _browse(self):
        if self.file_mode:
            path, _ = QFileDialog.getOpenFileName(
                self, "Selecionar arquivo", "", "Todos os arquivos (*.*)"
            )
        else:
            path = QFileDialog.getExistingDirectory(self, "Selecionar pasta")
        if path:
            self.line.setText(path)

    def text(self) -> str:
        return self.line.text()

    def setText(self, text: str):
        self.line.setText(text)

    def setPlaceholderText(self, text: str):
        self.line.setPlaceholderText(text)

    def setEnabled(self, enabled: bool):
        self.line.setEnabled(enabled)
        self.btn.setEnabled(enabled)