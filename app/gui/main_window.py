from PySide6.QtWidgets import QMainWindow, QTabWidget, QStatusBar

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
from app.gui.mame_shader_test_widget import install_shader_test
from app.database.database import Database
from app.config.app_config import AppConfig

install_scan_thread_guard()


class MainWindow(QMainWindow):
    """Janela principal e orquestradora das abas do ARCADE MANAGER."""

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

        # ------------------------------------------------------------------
        # Home
        # ------------------------------------------------------------------
        # A Home deixa de ser uma aba plana para se tornar uma pequena seção
        # com duas sessões irmãs: a Home tradicional e a Home do RetroArch.
        # As duas recebem a MainWindow como parent para preservar os atalhos
        # e a navegação já implementados nas respectivas sessões.
        self.home_tab = HomeTab(self)
        self.retroarch_home_tab = RetroArchHomeTab(self)
        self.home_section = QTabWidget()
        self.home_section.setDocumentMode(True)
        self.home_section.setTabPosition(QTabWidget.TabPosition.North)
        self.home_section.addTab(self.home_tab, "Arcade / MAME")
        self.home_section.addTab(self.retroarch_home_tab, "RetroArch")
        self.home_section.currentChanged.connect(self._on_home_section_changed)

        # ------------------------------------------------------------------
        # Demais sessões
        # ------------------------------------------------------------------
        self.catalogs_tab = EmulatorCatalogsTab(self)
        self.directories_tab = DirectoriesTab(self)
        self.emulator_settings_tab = EmulatorSettingsTab(self)
        self.filters_tab = FiltersTab(self, db=self.db)
        self.shader_test_controller = install_shader_test(self.emulator_settings_tab.shader_test_target)
        self.scan_tab = ScanRomsTab(self)
        self.reconstruction_tab = ReconstructionTab(self)
        self.retroarch_catalog_tab = RetroArchCatalogTab(self)
        self.retroarch_directories_tab = RetroArchDirectoriesTab(self)

        # A Home continua sendo uma única aba na barra principal. O usuário
        # alterna entre Arcade/MAME e RetroArch dentro dela.
        self.tab_widget.addTab(self.home_section, "Home")
        self.tab_widget.addTab(self.catalogs_tab, "Catálogos")
        self.tab_widget.addTab(self.directories_tab, "Diretórios")
        self.tab_widget.addTab(self.emulator_settings_tab, "Configurações dos Emuladores")
        self.tab_widget.addTab(self.filters_tab, "Filtragem")
        self.tab_widget.addTab(self.scan_tab, "Scan Roms")
        self.tab_widget.addTab(self.reconstruction_tab, "Reconstrução")
        self.tab_widget.addTab(self.retroarch_catalog_tab, "RetroArch Catálogo")
        self.tab_widget.addTab(self.retroarch_directories_tab, "RetroArch Diretórios")

        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        if hasattr(self.directories_tab, "settings_changed"):
            self.directories_tab.settings_changed.connect(self.home_tab.refresh_status)
            self.directories_tab.settings_changed.connect(self.filters_tab._update_database_info)
            self.directories_tab.settings_changed.connect(self.catalogs_tab.refresh)
        if hasattr(self.filters_tab, "database_updated"):
            self.filters_tab.database_updated.connect(self._on_database_updated)
            self.filters_tab.database_updated.connect(self.scan_tab.refresh_profiles)
        if hasattr(self.filters_tab, "filters_changed"):
            self.filters_tab.filters_changed.connect(self._on_filters_changed)

    def _on_home_section_changed(self, index: int) -> None:
        """Atualiza a sessão selecionada dentro da Home sem recriá-la."""
        widget = self.home_section.widget(index)
        if widget is self.home_tab:
            self.home_tab.refresh_status()
        elif widget is self.retroarch_home_tab:
            self.retroarch_home_tab.refresh()

    def _on_tab_changed(self, index):
        """Atualiza dados transitórios quando uma aba principal é selecionada."""
        widget = self.tab_widget.widget(index)
        if widget is self.home_section:
            self._on_home_section_changed(self.home_section.currentIndex())
        elif widget is self.catalogs_tab:
            self.catalogs_tab.refresh()
        elif widget is self.directories_tab:
            self.directories_tab._refresh_ui_state()
        elif widget is self.scan_tab:
            self.scan_tab.refresh_profiles()
        elif widget is self.reconstruction_tab:
            self.reconstruction_tab.refresh()
        elif widget is self.emulator_settings_tab:
            self.emulator_settings_tab.refresh()
        elif widget is self.retroarch_catalog_tab:
            self.retroarch_catalog_tab.refresh()
        elif widget is self.retroarch_directories_tab:
            self.retroarch_directories_tab.refresh()

    def _on_database_updated(self):
        """Atualiza abas dependentes do dataset."""
        self.home_tab.refresh_status()
        self.catalogs_tab.refresh()
        if hasattr(self.scan_tab, "_update_ui_state"):
            self.scan_tab._update_ui_state()

    def _on_filters_changed(self):
        """Propaga o perfil ativo para o scanner."""
        if hasattr(self.scan_tab, "set_active_profile_name"):
            self.scan_tab.set_active_profile_name(self.filters_tab.profile_combo.currentText())

    def get_current_filter_criteria(self):
        """Retorna os critérios ativos da aba Filtragem."""
        if hasattr(self.filters_tab, "current_criteria"):
            return self.filters_tab.current_criteria
        from app.core.models.filter_profile import FilterCriteria
        return FilterCriteria()

    def closeEvent(self, event):
        """Cancela workers, encerra testes e fecha recursos com segurança."""
        if getattr(self, "shader_test_controller", None) is not None:
            self.shader_test_controller.stop()
        self.db.close()
        event.accept()


__all__ = ["MainWindow"]
