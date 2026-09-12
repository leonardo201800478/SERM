"""Configuração inicial de áudio do SERM V2."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QLabel, QSlider, QVBoxLayout, QWidget
from PySide6.QtCore import Qt


class SoundSettingsPage(QWidget):
    """Placeholder funcional para a futura central de áudio do SERM."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        title = QLabel("Som")
        title.setProperty("role", "title")
        root.addWidget(title)

        general = QGroupBox("Áudio da interface")
        form = QFormLayout(general)
        form.setContentsMargins(10, 8, 10, 9)
        form.setVerticalSpacing(6)
        self.enabled = QComboBox()
        self.enabled.addItem("Ativado", True)
        self.enabled.addItem("Desativado", False)
        form.addRow("Interface:", self.enabled)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(80)
        form.addRow("Volume:", self.volume)
        root.addWidget(general)

        note = QLabel(
            "Seção inicial. Nas próximas etapas definiremos mixer, sons de interface, "
            "dispositivos, latência e comportamento por emulador."
        )
        note.setWordWrap(True)
        root.addWidget(note)
        root.addStretch(1)


__all__ = ["SoundSettingsPage"]
