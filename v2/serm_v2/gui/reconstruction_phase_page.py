"""Container da fase 3, organizada por família de catálogo."""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .reconstruction_page import ReconstructionPage


class ReconstructionPhasePage(QWidget):
    SYSTEMS = ("MAME", "No-Intro", "Redump", "WHLoader", "C64")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("reconstructionSystemTabs")
        self.pages: list[ReconstructionPage] = []
        for system in self.SYSTEMS:
            page = ReconstructionPage(system, self)
            self.pages.append(page)
            self.tabs.addTab(page, system)
        layout.addWidget(self.tabs, 1)

    def refresh(self) -> None:
        for page in self.pages:
            page.refresh()


__all__ = ["ReconstructionPhasePage"]
