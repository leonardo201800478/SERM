"""Home V2 baseada diretamente nos fluxos funcionais validados do SERM original."""
from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from app.gui.tabs.home_tab import HomeTab
from app.gui.tabs.retroarch_home_tab_v2 import RetroArchHomeTab


class HomePage(QWidget):
    """Replica a Home original sem reimplementar seus fluxos testados."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.parent_window = parent
        self._build_ui()

    def _build_ui(self) -> None:
        """Monta Arcade/MAME e RetroArch usando as implementações originais."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.home_section = QTabWidget()
        self.home_section.setDocumentMode(True)
        self.home_section.setTabPosition(QTabWidget.TabPosition.North)
        self.arcade_tab = HomeTab(self.parent_window)
        self.retroarch_tab = RetroArchHomeTab(self.parent_window)
        self.home_section.addTab(self.arcade_tab, "Arcade / MAME")
        self.home_section.addTab(self.retroarch_tab, "RetroArch")
        self.home_section.currentChanged.connect(self._on_section_changed)
        layout.addWidget(self.home_section)

    def _on_section_changed(self, index: int) -> None:
        """Atualiza a subaba selecionada, preservando o comportamento original."""
        widget = self.home_section.widget(index)
        if widget is self.arcade_tab:
            self.arcade_tab.refresh_status()
        elif widget is self.retroarch_tab:
            self.retroarch_tab.refresh()

    def refresh(self) -> None:
        """Atualiza os componentes funcionais da Home."""
        self.arcade_tab.refresh_status()
        self.retroarch_tab.refresh()

    @property
    def home_tab(self) -> HomeTab:
        """Retorna a implementação original da Home Arcade."""
        return self.arcade_tab

    @property
    def retroarch_home_tab(self) -> RetroArchHomeTab:
        """Retorna a implementação original da Home RetroArch."""
        return self.retroarch_tab
