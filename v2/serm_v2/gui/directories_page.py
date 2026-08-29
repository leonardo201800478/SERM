"""Página unificada de diretórios do SERM V2."""
from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from app.gui.tabs.directories_tab import DirectoriesTab
from app.gui.tabs.retroarch_directories_tab import RetroArchDirectoriesTab

from .tools_directories import ToolsDirectoriesPage


class DirectoriesPage(QWidget):
    """Agrupa os diretórios tradicionais, RetroArch e ferramentas auxiliares."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.parent_window = parent
        self._build_ui()

    def _build_ui(self) -> None:
        """Monta as três sessões sem duplicar as implementações originais."""
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.emulators_tab = DirectoriesTab(self.parent_window)
        self.retroarch_tab = RetroArchDirectoriesTab(self.parent_window)
        self.tools_tab = ToolsDirectoriesPage(self.parent_window)
        self.tabs.addTab(self.emulators_tab, "Emuladores")
        self.tabs.addTab(self.retroarch_tab, "RetroArch")
        self.tabs.addTab(self.tools_tab, "LaunchBox / 7-Zip")
        layout.addWidget(self.tabs)
        self.emulators_tab.settings_changed.connect(self._refresh_related)

    def _refresh_related(self) -> None:
        """Atualiza as subguias que dependem da configuração central."""
        self.retroarch_tab.refresh()
        self.tools_tab.refresh()

    def refresh(self) -> None:
        """Atualiza todas as subguias da página unificada."""
        self.emulators_tab._refresh_ui_state()
        self.retroarch_tab.refresh()
        self.tools_tab.refresh()


__all__ = ["DirectoriesPage"]
