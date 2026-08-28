"""Janela principal e orquestradora das abas do ARCADE MANAGER."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QMainWindow, QTabWidget, QStatusBar, QWidget

from app.mame import physical_rom_scanner_guard  # noqa: F401
from app.gui.tabs.home_tab import HomeTab
from app.gui.tabs.directories_tab import DirectoriesTab
from app.gui.tabs.filters_tab_realtime import FiltersTab
from app.gui.tabs.scan_roms_tab import ScanRomsTab
from app.gui.tabs.emulator_catalogs_tab import EmulatorCatalogsTab
from app.gui.scan_thread_guard import install as install_scan_thread_guard
from app.gui.tabs.reconstruction_tab import ReconstructionTab
from app.gui.tabs.emulator_settings_tab import EmulatorSettingsTab
from app.gui.tabs.retroarch_home_tab_v2 import RetroArchHomeTab
from app.gui.tabs.retroarch_catalog_tab import RetroArchCatalogTab
from app.gui.tabs.retroarch_directories_tab import RetroArchDirectoriesTab
from app.gui.tabs.launchbox_integration_tab import LaunchBoxIntegrationTab
from app.gui.mame_shader_test_widget import install_shader_test
from app.database.database import Database
from app.config.app_config import AppConfig

install_scan_thread_guard()


class _LazyTabPlaceholder(QWidget):
    """Placeholder leve para uma aba que será materializada somente ao acesso."""

    def __init__(self, key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key = key
        self.setObjectName(f"lazy_tab_{key}")


class MainWindow(QMainWindow):
    """Janela principal; abas pesadas são inicializadas sob demanda."""

    _LAZY_TABS = (
        ("catalogs_tab", "Catálogos", EmulatorCatalogsTab),
        ("emulator_settings_tab", "Configurações dos Emuladores", EmulatorSettingsTab),
        ("scan_tab", "Scan Roms", ScanRomsTab),
        ("reconstruction_tab", "Reconstrução", ReconstructionTab),
        ("retroarch_catalog_tab", "RetroArch Catálogo", RetroArchCatalogTab),
        ("retroarch_directories_tab", "RetroArch Diretórios", RetroArchDirectoriesTab),
        ("launchbox_integration_tab", "LaunchBox", LaunchBoxIntegrationTab),
    )

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MAME Set Builder")
        self.resize(1200, 820)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Pronto")
        self.config = AppConfig()
        self.db = Database(self.config.db_path)
        self.db.connect()
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # Estas telas são leves e participam do estado/configuração inicial.
        self.home_tab = HomeTab(self)
        self.retroarch_home_tab = RetroArchHomeTab(self)
        self.home_section = QTabWidget()
        self.home_section.setDocumentMode(True)
        self.home_section.setTabPosition(QTabWidget.TabPosition.North)
        self.home_section.addTab(self.home_tab, "Arcade / MAME")
        self.home_section.addTab(self.retroarch_home_tab, "RetroArch")
        self.home_section.currentChanged.connect(self._on_home_section_changed)

        self.directories_tab = DirectoriesTab(self)
        self.filters_tab = FiltersTab(self, db=self.db)

        self._lazy_factories: dict[str, Callable[[], QWidget]] = {}
        self._lazy_placeholders: dict[str, _LazyTabPlaceholder] = {}
        self._register_lazy_tabs()

        self.shader_test_controller = None

        self.tab_widget.addTab(self.home_section, "Home")
        self.tab_widget.addTab(self.directories_tab, "Diretórios")
        self._add_lazy_tab("catalogs_tab", "Catálogos")
        self._add_lazy_tab("emulator_settings_tab", "Configurações dos Emuladores")
        self.tab_widget.addTab(self.filters_tab, "Filtragem")
        self._add_lazy_tab("scan_tab", "Scan Roms")
        self._add_lazy_tab("reconstruction_tab", "Reconstrução")
        self._add_lazy_tab("retroarch_catalog_tab", "RetroArch Catálogo")
        self._add_lazy_tab("retroarch_directories_tab", "RetroArch Diretórios")
        self._add_lazy_tab("launchbox_integration_tab", "LaunchBox")

        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self._connect_directory_signals()
        self._connect_filter_signals()

        # Compatibilidade: o teste de shaders exige a subaba MAME, mas não
        # deve materializar Flycast/Supermodel/FBNeo/RetroArch.
        settings = self._ensure_lazy_tab("emulator_settings_tab", select=False)
        self.shader_test_controller = install_shader_test(settings.shader_test_target)
        self.tab_widget.setCurrentIndex(0)
        self.home_tab.refresh_status()

    def _register_lazy_tabs(self) -> None:
        """Registra fábricas sem construir os widgets associados."""
        for attr, _label, widget_type in self._LAZY_TABS:
            self._lazy_factories[attr] = lambda cls=widget_type: cls(self)
            setattr(self, attr, None)

    def _add_lazy_tab(self, attr: str, label: str) -> None:
        """Adiciona um placeholder visual para uma aba lazy."""
        placeholder = _LazyTabPlaceholder(attr, self.tab_widget)
        self._lazy_placeholders[attr] = placeholder
        self.tab_widget.addTab(placeholder, label)

    def _ensure_lazy_tab(self, attr: str, *, select: bool = True) -> QWidget:
        """Materializa uma aba lazy e substitui seu placeholder no mesmo índice."""
        current = getattr(self, attr, None)
        if current is not None:
            if select:
                self.tab_widget.setCurrentWidget(current)
            return current
        factory = self._lazy_factories.get(attr)
        placeholder = self._lazy_placeholders.get(attr)
        if factory is None or placeholder is None:
            raise KeyError(f"Aba lazy desconhecida: {attr}")

        index = self.tab_widget.indexOf(placeholder)
        if index < 0:
            raise RuntimeError(f"Placeholder da aba {attr} não está registrado.")

        widget = factory()
        setattr(self, attr, widget)
        self._lazy_placeholders.pop(attr, None)

        self.tab_widget.blockSignals(True)
        try:
            self.tab_widget.removeTab(index)
            self.tab_widget.insertTab(index, widget, self._label_for_lazy_tab(attr))
            if select:
                self.tab_widget.setCurrentIndex(index)
        finally:
            self.tab_widget.blockSignals(False)
        return widget

    def _label_for_lazy_tab(self, attr: str) -> str:
        """Retorna o rótulo persistente de uma aba lazy."""
        for candidate, label, _widget_type in self._LAZY_TABS:
            if candidate == attr:
                return label
        raise KeyError(attr)

    def _connect_directory_signals(self) -> None:
        """Conecta sinais que não exigem materializar abas pesadas."""
        if hasattr(self.directories_tab, "settings_changed"):
            self.directories_tab.settings_changed.connect(self.home_tab.refresh_status)
            self.directories_tab.settings_changed.connect(self.filters_tab._update_database_info)
            self.directories_tab.settings_changed.connect(self._refresh_loaded_catalogs)

    def _connect_filter_signals(self) -> None:
        """Conecta alterações de filtros sem forçar o carregamento do scanner."""
        if hasattr(self.filters_tab, "database_updated"):
            self.filters_tab.database_updated.connect(self._on_database_updated)
        if hasattr(self.filters_tab, "filters_changed"):
            self.filters_tab.filters_changed.connect(self._on_filters_changed)

    def _refresh_loaded_catalogs(self) -> None:
        """Atualiza Catálogos somente se a aba já tiver sido aberta."""
        if self.catalogs_tab is not None:
            self.catalogs_tab.refresh()

    def _on_home_section_changed(self, index: int) -> None:
        """Atualiza a sessão selecionada dentro da Home."""
        widget = self.home_section.widget(index)
        if widget is self.home_tab:
            self.home_tab.refresh_status()
        elif widget is self.retroarch_home_tab:
            self.retroarch_home_tab.refresh()

    def _on_tab_changed(self, index: int) -> None:
        """Materializa a aba selecionada e atualiza somente seu estado."""
        widget = self.tab_widget.widget(index)
        for attr, _label, _widget_type in self._LAZY_TABS:
            if widget is self._lazy_placeholders.get(attr):
                widget = self._ensure_lazy_tab(attr, select=False)
                break

        if widget is self.home_section:
            self._on_home_section_changed(self.home_section.currentIndex())
        elif widget is self.directories_tab:
            self.directories_tab._refresh_ui_state()
        elif widget is self.filters_tab:
            self.filters_tab._update_database_info()
        elif widget is self.catalogs_tab:
            self.catalogs_tab.refresh()
        elif widget is self.emulator_settings_tab:
            self.emulator_settings_tab.refresh()
        elif widget is self.scan_tab:
            self.scan_tab.refresh_profiles()
        elif widget is self.reconstruction_tab:
            self.reconstruction_tab.refresh()
        elif widget is self.retroarch_catalog_tab:
            self.retroarch_catalog_tab.refresh()
        elif widget is self.retroarch_directories_tab:
            self.retroarch_directories_tab.refresh()
        elif widget is self.launchbox_integration_tab:
            self.launchbox_integration_tab.refresh()

    def _on_database_updated(self) -> None:
        """Atualiza somente componentes já materializados."""
        self.home_tab.refresh_status()
        self._refresh_loaded_catalogs()
        if self.scan_tab is not None and hasattr(self.scan_tab, "_update_ui_state"):
            self.scan_tab._update_ui_state()

    def _on_filters_changed(self) -> None:
        """Propaga o perfil ativo somente para o scanner já materializado."""
        if self.scan_tab is not None and hasattr(self.scan_tab, "set_active_profile_name"):
            self.scan_tab.set_active_profile_name(self.filters_tab.profile_combo.currentText())

    def get_current_filter_criteria(self):
        """Retorna os critérios ativos da aba Filtragem."""
        if hasattr(self.filters_tab, "current_criteria"):
            return self.filters_tab.current_criteria
        from app.core.models.filter_profile import FilterCriteria
        return FilterCriteria()

    def closeEvent(self, event):
        """Cancela workers e fecha apenas recursos efetivamente materializados."""
        if getattr(self, "shader_test_controller", None) is not None:
            self.shader_test_controller.stop()
        for attr, _label, _widget_type in self._LAZY_TABS:
            widget = getattr(self, attr, None)
            if widget is not None and widget is not self.emulator_settings_tab and hasattr(widget, "closeEvent"):
                widget.close()
        if self.emulator_settings_tab is not None:
            self.emulator_settings_tab.close()
        self.db.close()
        event.accept()


__all__ = ["MainWindow"]
