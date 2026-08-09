"""
Widget para ajuste de valores com slider e exibição do valor.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSlider, QLineEdit
from PyQt6.QtCore import pyqtSignal, Qt

class SliderWithValue(QWidget):
    valueChanged = pyqtSignal(int)

    def __init__(self, label: str, min_val: int = 0, max_val: int = 100, default: int = 50,
                 step: int = 1, description: str = "", parent=None):
        super().__init__(parent)
        self.label = label
        self.min_val = min_val
        self.max_val = max_val
        self.default = default
        self.step = step
        self.description = description
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        # Rótulo
        label_widget = QLabel(self.label)
        label_widget.setStyleSheet("font-weight: bold;")
        layout.addWidget(label_widget)

        # Slider + valor
        slider_layout = QHBoxLayout()

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(self.min_val)
        self.slider.setMaximum(self.max_val)
        self.slider.setSingleStep(self.step)
        self.slider.setValue(self.default)
        self.slider.valueChanged.connect(self._on_slider_changed)
        slider_layout.addWidget(self.slider, 1)

        self.value_display = QLineEdit()
        self.value_display.setFixedWidth(60)
        self.value_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_display.setText(str(self.default))
        self.value_display.setReadOnly(True)
        slider_layout.addWidget(self.value_display)

        layout.addLayout(slider_layout)

        if self.description:
            desc_label = QLabel(self.description)
            desc_label.setStyleSheet("color: #666; font-size: 10px;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

    def _on_slider_changed(self, value: int):
        self.value_display.setText(str(value))
        self.valueChanged.emit(value)

    def get_value(self) -> int:
        return self.slider.value()

    def set_value(self, value: int):
        if self.min_val <= value <= self.max_val:
            self.slider.setValue(value)
            self.value_display.setText(str(value))