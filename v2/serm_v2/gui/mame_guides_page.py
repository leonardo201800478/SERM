"""Guias específicas do MAME para configuração, shaders e artworks."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from .emulator_settings_page import EmulatorSettingsPage
from .emulator_shaders_bezels_page import EmulatorShadersBezelsPage
from .mame_shaders_page import MameShadersPage


class MameGuidesPage(QWidget):
    """Agrupa as áreas de configuração e recursos visuais específicos do MAME."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        """Cria as guias de Configurações, Shaders e Artworks do MAME."""
        layout = QVBoxLayout(self)
        title = QLabel("MAME — Configurações, Shaders e Artworks")
        title.setProperty("role", "title")
        layout.addWidget(title)
        info = QLabel(
            "Seletores de BGFX são descobertos diretamente da instalação do MAME. "
            "Arquivos auxiliares como LICENSE, README e desktop.ini não aparecem como shaders."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        self.tabs = QTabWidget()
        self.settings = EmulatorSettingsPage(self)
        self.shaders = MameShadersPage(self)
        self.visuals = EmulatorShadersBezelsPage(self)
        self.tabs.addTab(self.settings, "Configurações MAME")
        self.tabs.addTab(self.shaders, "Shaders BGFX")
        self.tabs.addTab(self.visuals, "Artworks / Bezels")
        layout.addWidget(self.tabs, 1)

    def refresh(self) -> None:
        """Atualiza as páginas sem gravar configurações."""
        self.settings.refresh()
        self.shaders.refresh()
        self.visuals.refresh()
