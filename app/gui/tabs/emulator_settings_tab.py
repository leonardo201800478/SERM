"""Aba central de configurações dos emuladores do ARCADE MANAGER.

Agrupa MAME, Flycast, Supermodel, FBNeo e RetroArch em subabas independentes.
A implementação específica de cada emulador permanece isolada em seu widget
/adaptador nativo.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from app.gui.tabs.mame_settings_tab import MameSettingsTab
from app.gui.tabs.flycast_settings_tab import FlycastSettingsTab


class EmulatorSettingsTab(QWidget):
    """Container das configurações específicas dos cinco emuladores."""

    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.mame_tab: MameSettingsTab | None = None
        self.flycast_tab: FlycastSettingsTab | None = None
        self.supermodel_tab: QWidget | None = None
        self.fbneo_tab: QWidget | None = None
        self.retroarch_tab: QWidget | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        """Cria as cinco subabas de configuração dos emuladores."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.tab_widget = QTabWidget()
        root.addWidget(self.tab_widget)

        self.mame_tab = MameSettingsTab(self)
        self.tab_widget.addTab(self.mame_tab, "MAME")

        self.flycast_tab = FlycastSettingsTab(self)
        self.tab_widget.addTab(self.flycast_tab, "Flycast")

        self.supermodel_tab = self._create_pending_tab(
            "Supermodel", "Configurações do Supermodel serão implementadas nesta subaba."
        )
        self.tab_widget.addTab(self.supermodel_tab, "Supermodel")

        self.fbneo_tab = self._create_pending_tab(
            "FBNeo", "Configurações do FBNeo serão implementadas nesta subaba."
        )
        self.tab_widget.addTab(self.fbneo_tab, "FBNeo")

        self.retroarch_tab = self._create_pending_tab(
            "RetroArch", "Configurações do RetroArch serão implementadas nesta subaba."
        )
        self.tab_widget.addTab(self.retroarch_tab, "RetroArch")

        self.tab_widget.currentChanged.connect(self._on_subtab_changed)

    @staticmethod
    def _create_pending_tab(emulator: str, message: str) -> QWidget:
        """Cria a página provisória de um emulador ainda não implementado."""
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel(f"Configurações do {emulator}")
        title.setStyleSheet("font-size:20px;font-weight:bold")
        description = QLabel(message)
        description.setWordWrap(True)
        description.setStyleSheet("padding:8px")
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addStretch()
        return page

    def _on_subtab_changed(self, index: int) -> None:
        """Atualiza a subaba selecionada quando ela possui configuração nativa."""
        widget = self.tab_widget.widget(index)
        if widget is self.mame_tab:
            self.mame_tab._load_ini()
        elif widget is self.flycast_tab:
            self.flycast_tab.refresh()

    def refresh(self) -> None:
        """Recarrega a configuração da subaba atualmente selecionada."""
        current = self.tab_widget.currentWidget()
        if current is self.mame_tab:
            self.mame_tab._load_ini()
        elif current is self.flycast_tab:
            self.flycast_tab.refresh()

    @property
    def shader_test_target(self) -> MameSettingsTab:
        """Retorna o widget MAME usado pelo teste de shaders existente."""
        if self.mame_tab is None:
            raise RuntimeError("A subaba MAME ainda não foi inicializada.")
        return self.mame_tab
