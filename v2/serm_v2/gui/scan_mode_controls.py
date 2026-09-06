from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class ScanModeControls(QWidget):
    """Controls explícitos para escolher retomada ou novo scan."""

    mode_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.resume_requested = True
        self.resume_button = QPushButton("RETOMAR ÚLTIMO SCAN")
        self.new_button = QPushButton("INICIAR NOVO SCAN")
        self.status = QLabel("Modo: RETOMAR ÚLTIMO SCAN")
        row = QHBoxLayout(self)
        row.addWidget(self.resume_button)
        row.addWidget(self.new_button)
        row.addWidget(self.status)
        row.addStretch()
        self.resume_button.clicked.connect(lambda: self._set(True))
        self.new_button.clicked.connect(lambda: self._set(False))
        self._set(True)

    def _set(self, resume):
        self.resume_requested = resume
        self.status.setText("Modo: RETOMAR ÚLTIMO SCAN" if resume else "Modo: INICIAR NOVO SCAN")
        self.resume_button.setEnabled(not resume)
        self.new_button.setEnabled(resume)
        self.mode_changed.emit(resume)
