"""Main window for SERM V2."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from .emulator_home import EmulatorHomePage
from .log_handler import LogViewer
from .no_intro_home import NoIntroPage
from .redump_home import RedumpPage


class MainWindow(QMainWindow):
    """Top-level V2 window with the complete tested Home workflow."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SERM")
        self.resize(1280, 800)
        self.log_viewer = LogViewer()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the main navigation and provider pages."""
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(QLabel("SERM V2", alignment=Qt.AlignmentFlag.AlignLeft))
        tabs = QTabWidget()
        tabs.addTab(EmulatorHomePage(self), "Home")
        tabs.addTab(NoIntroPage(self), "No-Intro")
        tabs.addTab(RedumpPage(self), "Redump")
        layout.addWidget(tabs, 1)
        self.setCentralWidget(root)

    def closeEvent(self, event) -> None:  # noqa: N802
        """Detach the GUI logging handler before closing the application."""
        self.log_viewer.close()
        super().closeEvent(event)
