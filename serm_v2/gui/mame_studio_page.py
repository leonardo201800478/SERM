"""Fluxo operacional unificado do MAME na V2."""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .arcade_studio_page import ArcadeStudioPage
from .mame_filter_page import MameFilterPage
from .mame_scan_page import MameScanPage
from .mame_visual_library_page import MameVisualLibraryPage
from .reconstruction_page import ReconstructionPage


class MameStudioPage(QWidget):
    """Organiza o pipeline MAME em uma única superfície operacional.

    A ordem visual acompanha o contrato técnico: catálogo → scan → filtros →
    reconstrução. A etapa de catálogo agora abre uma biblioteca visual baseada
    no artwork local do MAME, sem alterar a separação das fases do pipeline.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.catalog_page = ArcadeStudioPage(self)
        self.scan_page = MameScanPage(self)
        self.filter_page = MameFilterPage(self)
        self.reconstruction_page = ReconstructionPage("MAME", self)

        # ArcadeStudioPage ainda possui uma implementação histórica de abas
        # internas. Somente Catálogo e Auditoria CHD pertencem à etapa 1;
        # filtros e reconstrução são centralizados nas etapas 3 e 4 abaixo.
        if hasattr(self.catalog_page, "tabs"):
            while self.catalog_page.tabs.count() > 2:
                self.catalog_page.tabs.removeTab(1)

            # A Biblioteca Visual é a entrada principal da etapa de catálogo.
            # O comparador técnico e a auditoria CHD continuam disponíveis nas
            # abas seguintes, preservando o fluxo existente.
            self.visual_library_page = MameVisualLibraryPage(self.catalog_page)
            self.catalog_page.tabs.insertTab(0, self.visual_library_page, "Biblioteca Visual")
            self.catalog_page.tabs.setCurrentIndex(0)
        else:
            self.visual_library_page = None

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
        if self.visual_library_page is not None and current is self.catalog_page:
            self.visual_library_page.refresh()


__all__ = ["MameStudioPage"]
