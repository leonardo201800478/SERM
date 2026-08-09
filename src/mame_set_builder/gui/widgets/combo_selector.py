"""
Widget para seleção de opções com rótulo e descrição.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QVBoxLayout
from PyQt6.QtCore import pyqtSignal

class ComboSelector(QWidget):
    valueChanged = pyqtSignal(str)

    def __init__(self, label: str, options: list, default: str = "", description: str = "", parent=None):
        super().__init__(parent)
        self.label = label
        self.options = options
        self.default = default
        self.description = description
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        # Rótulo
        label_widget = QLabel(self.label)
        label_widget.setStyleSheet("font-weight: bold;")
        layout.addWidget(label_widget)

        # Combo + descrição
        combo_layout = QHBoxLayout()
        self.combo = QComboBox()
        self.combo.addItems(self.options)

        if self.default and self.default in self.options:
            self.combo.setCurrentText(self.default)

        self.combo.currentTextChanged.connect(self.valueChanged.emit)

        combo_layout.addWidget(self.combo, 1)

        # Descrição (opcional)
        if self.description:
            desc_label = QLabel(self.description)
            desc_label.setStyleSheet("color: #666; font-size: 10px;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        layout.addLayout(combo_layout)

    def get_value(self) -> str:
        return self.combo.currentText()

    def set_value(self, value: str):
        if value in self.options:
            self.combo.setCurrentText(value)