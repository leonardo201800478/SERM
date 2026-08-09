"""
Diálogo com barra de progresso para operações longas.
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal

class ProgressDialog(QDialog):
    """Diálogo modal com barra de progresso."""
    canceled = pyqtSignal()

    def __init__(self, title: str = "Processando...", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.label = QLabel("Aguarde...")
        layout.addWidget(self.label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)

        # Botão Cancelar
        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def _on_cancel(self):
        self.canceled.emit()
        self.reject()

    def setLabel(self, text: str):
        self.label.setText(text)

    def setProgress(self, value: int):
        self.progress.setValue(value)

    def setRange(self, min_val: int, max_val: int):
        self.progress.setRange(min_val, max_val)

    def setCancelEnabled(self, enabled: bool):
        self.cancel_btn.setEnabled(enabled)