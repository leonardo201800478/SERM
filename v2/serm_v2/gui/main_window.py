"""Main window for SERM V2."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from .home import HomePage
from .redump_home import RedumpPage


class MainWindow(QMainWindow):
    """Top-level V2 window containing the application source pages."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SERM")
        self.resize(1280, 800)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the V2 navigation and acquisition pages."""
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(QLabel("SERM V2", alignment=Qt.AlignmentFlag.AlignLeft))
        tabs = QTabWidget()
        tabs.addTab(HomePage(self), "Home / No-Intro")
        tabs.addTab(RedumpPage(self), "Redump")
        layout.addWidget(tabs, 1)
        self.setCentralWidget(root)
