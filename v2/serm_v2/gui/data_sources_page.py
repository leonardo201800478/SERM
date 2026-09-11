"""Hub visual compacto de aquisição e atualização das fontes do SERM V2."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget, QVBoxLayout, QWidget

from .dat_scraper import DatScraperPage
from .progetto_snaps_page import ProgettoSnapsPage


class _SourceCard(QFrame):
    """Entrada compacta para uma família de fontes."""

    def __init__(self, number: str, title: str, description: str, action, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sourceCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(4)
        badge = QLabel(number)
        badge.setObjectName("sourceCardNumber")
        title_label = QLabel(title)
        title_label.setObjectName("sourceCardTitle")
        title_label.setWordWrap(True)
        description_label = QLabel(description)
        description_label.setObjectName("sourceCardDescription")
        description_label.setWordWrap(True)
        button = QPushButton("ABRIR")
        button.clicked.connect(action)
        layout.addWidget(badge)
        layout.addWidget(title_label)
        layout.addWidget(description_label, 1)
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)


class DataSourcesPage(QWidget):
    """Centraliza fontes externas em uma superfície visual compacta."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(7)

        title = QLabel("FONTES E DADOS")
        title.setProperty("role", "title")
        subtitle = QLabel("Aquisição, atualização e validação das fontes que alimentam o catálogo do SERM.")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        banner = QFrame()
        banner.setObjectName("sourceStatusBanner")
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(9, 5, 9, 5)
        banner_layout.setSpacing(8)
        banner_layout.addWidget(QLabel("PIPELINE"))
        status = QLabel("FONTES → INGESTÃO → CATÁLOGO → SCAN")
        status.setObjectName("sourceStatus")
        banner_layout.addWidget(status)
        banner_layout.addStretch(1)
        root.addWidget(banner)

        cards = QGridLayout()
        cards.setContentsMargins(0, 0, 0, 0)
        cards.setHorizontalSpacing(7)
        cards.setVerticalSpacing(7)
        self.tabs = QTabWidget()
        self.dat_page = DatScraperPage(self)
        self.snaps_page = ProgettoSnapsPage(self)
        self.tabs.addTab(self.dat_page, "DATs / Catálogos")
        self.tabs.addTab(self.snaps_page, "MAME / Artwork e SupportFiles")
        self.tabs.hide()

        entries = (
            ("01", "DATs e catálogos", "No-Intro, Redump, WHLoader, C64 e catálogo MAME.", 0),
            ("02", "MAME — projeto-SNAPS", "DATs, INIs, artwork e recursos auxiliares.", 1),
            ("03", "Proveniência e cache", "Origem, versão, hash e estado local das aquisições.", 1),
            ("04", "Preparação do catálogo", "Aquisição concluída antes da operação em MAME Studio.", 1),
        )
        for pos, (number, card_title, description, index) in enumerate(entries):
            cards.addWidget(
                _SourceCard(number, card_title, description, lambda i=index: self._open_source(i), self),
                0, pos,
            )
        root.addLayout(cards)
        root.addWidget(self.tabs, 1)

        self.tabs.currentChanged.connect(self._tab_changed)
        self._open_source(0)

    def _open_source(self, index: int) -> None:
        self.tabs.show()
        self.tabs.setCurrentIndex(index)
        self._refresh_current()

    def _tab_changed(self, _index: int) -> None:
        self._refresh_current()

    def _refresh_current(self) -> None:
        page = self.tabs.currentWidget()
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            refresh()

    def refresh(self) -> None:
        self._refresh_current()


__all__ = ["DataSourcesPage"]
