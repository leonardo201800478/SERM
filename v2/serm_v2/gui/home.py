"""Initial clean Home page for SERM V2.

The page deliberately has no dependency on V1 services, database or configuration.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class HomePage(QWidget):
    """Present the V2 application status without performing legacy discovery."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        """Create the clean V2 Home surface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("SERM")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 30px; font-weight: 700;")
        layout.addWidget(title)

        subtitle = QLabel("Strife Emulator and Roms Manager")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        status = QFrame()
        status_layout = QVBoxLayout(status)
        status_layout.addWidget(QLabel("SERM V2"))
        status_layout.addWidget(QLabel("Nova arquitetura inicializada."))
        status_layout.addWidget(QLabel("Banco, catálogo e runtimes serão conectados nas próximas etapas."))
        status_layout.addWidget(QLabel("A versão legada não participa desta execução."))
        layout.addWidget(status)
        layout.addStretch(1)
