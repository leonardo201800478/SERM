"""Guias específicas do MAME para configuração, shaders e artworks.

As guias reutilizam as implementações existentes do V2, mantendo o catálogo
MAME separado das configurações e recursos visuais do emulador.
"""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from .emulator_settings_page import EmulatorSettingsPage
from .emulator_shaders_bezels_page import EmulatorShadersBezelsPage


class MameGuidesPage(QWidget):
    """Agrupa as três áreas de trabalho específicas do MAME."""

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
            "Estas guias trabalham sobre os arquivos reais configurados para o MAME. "
            "O catálogo relacional permanece somente como fonte de dados do catálogo; "
            "profiles de sets não são criados nesta etapa."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.tabs = QTabWidget()
        self.settings = EmulatorSettingsPage(self)
        self.visuals = EmulatorShadersBezelsPage(self)

        # As páginas existentes possuem a navegação por emulador. O wrapper deixa
        # o foco explícito no MAME sem duplicar os editores e suas regras de backup.
        self.tabs.addTab(self.settings, "Configurações MAME")
        self.tabs.addTab(self.visuals, "Shaders / Artworks MAME")
        layout.addWidget(self.tabs, 1)

    def refresh(self) -> None:
        """Atualiza as duas páginas reutilizadas sem alterar arquivos."""
        self.settings.refresh()
        self.visuals.refresh()
