"""Fluxo operacional unificado do MAME na V2."""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .arcade_studio_page import ArcadeStudioPage
from .mame_filter_page import MameFilterPage
from .mame_scan_page import MameScanPage
from .reconstruction_phase_page import ReconstructionPhasePage


class MameStudioPage(QWidget):
    """Organiza o pipeline MAME em uma única superfície operacional.

    A ordem visual acompanha o contrato técnico: catálogo → scan → filtros →
    reconstrução. Cada etapa continua delegando regras de negócio aos serviços.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.catalog_page = ArcadeStudioPage(self)
        self.scan_page = MameScanPage(self)
        self.filter_page = MameFilterPage(self)
        self.reconstruction_page = ReconstructionPhasePage(self)
        self.tabs.addTab(self.catalog_page, "1 — Catálogo")
        self.tabs.addTab(self.scan_page, "2 — Scan")
        self.tabs.addTab(self.filter_page, "3 — Filtros")
        self.tabs.addTab(self.reconstruction_page, "4 — Reconstrução")
        layout.addWidget(self.tabs)

    def refresh(self) -> None:
        current = self.tabs.currentWidget()
        refresh = getattr(current, "refresh", None)
        if callable(refresh):
            refresh()


__all__ = ["MameStudioPage"]
