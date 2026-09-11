"""Hub de configuração da V2.

Agrupa configurações de ambiente que não executam o pipeline de catálogo/ROM.
"""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .emulator_directories_page import DirectoriesPage
from .emulator_settings_page import EmulatorSettingsPage
from .emulator_shaders_bezels_page import EmulatorShadersBezelsPage
from .tools_directories import ToolsDirectoriesPage


class ConfigurationPage(QWidget):
    """Centraliza diretórios, ferramentas, emuladores e aparência."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(DirectoriesPage(self), "Diretórios")
        self.tabs.addTab(ToolsDirectoriesPage(self), "Ferramentas")
        self.tabs.addTab(EmulatorSettingsPage(self), "Emuladores")
        self.tabs.addTab(EmulatorShadersBezelsPage(self), "Vídeo")
        layout.addWidget(self.tabs)

    def refresh(self) -> None:
        for index in range(self.tabs.count()):
            page = self.tabs.widget(index)
            refresh = getattr(page, "refresh", None)
            if callable(refresh):
                refresh()


__all__ = ["ConfigurationPage"]
