"""Hub de aquisição e atualização das fontes externas da V2."""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .dat_scraper import DatScraperPage
from .progetto_snaps_page import ProgettoSnapsPage


class DataSourcesPage(QWidget):
    """Agrupa aquisição de DATs e recursos auxiliares sem misturar execução de scans."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(DatScraperPage(self), "DATs e catálogos")
        self.tabs.addTab(ProgettoSnapsPage(self), "Progetto-SNAPS")
        layout.addWidget(self.tabs)

    def refresh(self) -> None:
        for index in range(self.tabs.count()):
            page = self.tabs.widget(index)
            refresh = getattr(page, "refresh", None)
            if callable(refresh):
                refresh()


__all__ = ["DataSourcesPage"]
