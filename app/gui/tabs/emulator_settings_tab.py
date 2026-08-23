"""Aba central de configurações dos emuladores do ARCADE MANAGER."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from app.gui.tabs.mame_settings_tab import MameSettingsTab
from app.gui.tabs.flycast_settings_tab import FlycastSettingsTab
from app.gui.tabs.supermodel_settings_tab import SupermodelSettingsTab
from app.gui.tabs.fbneo_settings_tab import FBNeoSettingsTab
from app.gui.tabs.retroarch_settings_tab import RetroArchSettingsTab


class EmulatorSettingsTab(QWidget):
    """Container das configurações específicas dos cinco emuladores."""

    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.mame_tab: MameSettingsTab | None = None
        self.flycast_tab: FlycastSettingsTab | None = None
        self.supermodel_tab: SupermodelSettingsTab | None = None
        self.fbneo_tab: FBNeoSettingsTab | None = None
        self.retroarch_tab: RetroArchSettingsTab | None = None
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
        self.supermodel_tab = SupermodelSettingsTab(self)
        self.tab_widget.addTab(self.supermodel_tab, "Supermodel")
        self.fbneo_tab = FBNeoSettingsTab(self)
        self.tab_widget.addTab(self.fbneo_tab, "FBNeo")
        self.retroarch_tab = RetroArchSettingsTab(self)
        self.tab_widget.addTab(self.retroarch_tab, "RetroArch")

        self.tab_widget.currentChanged.connect(self._on_subtab_changed)
        for widget in (self.mame_tab, self.flycast_tab, self.supermodel_tab, self.fbneo_tab, self.retroarch_tab):
            widget.settings_changed.connect(self.settings_changed)

    def _on_subtab_changed(self, index: int) -> None:
        """Atualiza a configuração nativa da subaba selecionada."""
        widget = self.tab_widget.widget(index)
        if widget is self.mame_tab:
            self.mame_tab._load_ini()
        elif widget is self.flycast_tab:
            self.flycast_tab.refresh()
        elif widget is self.supermodel_tab:
            self.supermodel_tab._load_installation()
        elif widget is self.fbneo_tab:
            self.fbneo_tab.refresh()
        elif widget is self.retroarch_tab:
            self.retroarch_tab.refresh()

    def refresh(self) -> None:
        """Recarrega a configuração da subaba atualmente selecionada."""
        current = self.tab_widget.currentWidget()
        if current is self.mame_tab:
            self.mame_tab._load_ini()
        elif current is self.flycast_tab:
            self.flycast_tab.refresh()
        elif current is self.supermodel_tab:
            self.supermodel_tab._load_installation()
        elif current is self.fbneo_tab:
            self.fbneo_tab.refresh()
        elif current is self.retroarch_tab:
            self.retroarch_tab.refresh()

    @property
    def shader_test_target(self) -> MameSettingsTab:
        """Retorna o widget MAME usado pelo teste de shaders existente."""
        if self.mame_tab is None:
            raise RuntimeError("A subaba MAME ainda não foi inicializada.")
        return self.mame_tab
