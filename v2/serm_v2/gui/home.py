"""Home V2 baseada nos componentes funcionais originais do SERM."""
from __future__ import annotations

from app.gui.tabs.home_tab import HomeTab
from app.gui.tabs.retroarch_home_tab_v2 import RetroArchHomeTab
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget


class HomePage(QWidget):
    """Composição da Home original: Arcade/MAME e RetroArch."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.parent_window = parent
        self._build_ui()

    def _build_ui(self) -> None:
        """Monta as duas subabas funcionais sem duplicar lógica já testada."""
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
        """Atualiza a subaba selecionada usando o mesmo contrato da Home original."""
        widget = self.home_section.widget(index)
        if widget is self.arcade_tab:
            self.arcade_tab.refresh_status()
        elif widget is self.retroarch_tab:
            self.retroarch_tab.refresh()

    def refresh(self) -> None:
        """Atualiza os estados da Home Arcade e RetroArch."""
        self.arcade_tab.refresh_status()
        self.retroarch_tab.refresh()

    @property
    def home_tab(self) -> HomeTab:
        """Retorna a Home Arcade funcional original."""
        return self.arcade_tab

    @property
    def retroarch_home_tab(self) -> RetroArchHomeTab:
        """Retorna a Home RetroArch funcional original."""
        return self.retroarch_tab
