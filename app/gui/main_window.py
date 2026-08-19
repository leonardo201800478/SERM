from PySide6.QtWidgets import QMainWindow, QTabWidget, QStatusBar

# Instala a proteção de leitura ZIP antes de carregar a aba de scanner.
from app.mame import physical_rom_scanner_guard  # noqa: F401
from app.gui.tabs.home_tab import HomeTab
from app.gui.tabs.directories_tab import DirectoriesTab
from app.gui.tabs.filters_tab_realtime import FiltersTab
from app.gui.tabs.scan_roms_tab import ScanRomsTab
from app.gui.scan_thread_guard import install as install_scan_thread_guard
from app.gui.tabs.reconstruction_tab import ReconstructionTab
from app.gui.tabs.mame_settings_tab import MameSettingsTab
from app.database.database import Database
from app.config.app_config import AppConfig

install_scan_thread_guard()


class MainWindow(QMainWindow):
    """Janela principal e orquestradora das abas do MAME Set Builder."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MAME Set Builder")
        self.resize(1024, 768)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Pronto")
        self.config = AppConfig()
        self.db = Database(self.config.db_path)
        self.db.connect()
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        self.home_tab = HomeTab(self)
        self.directories_tab = DirectoriesTab(self)
        self.filters_tab = FiltersTab(self, db=self.db)
        self.mame_settings_tab = MameSettingsTab(self)
        self.scan_tab = ScanRomsTab(self)
        self.reconstruction_tab = ReconstructionTab(self)
        self.tab_widget.addTab(self.home_tab, "Home")
        self.tab_widget.addTab(self.directories_tab, "Diretórios")
        self.tab_widget.addTab(self.filters_tab, "Filtragem")
        self.tab_widget.addTab(self.mame_settings_tab, "Configurações MAME")
        self.tab_widget.addTab(self.scan_tab, "Scan Roms")
        self.tab_widget.addTab(self.reconstruction_tab, "Reconstrução")
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        if hasattr(self.directories_tab, "settings_changed"):
            self.directories_tab.settings_changed.connect(self.home_tab.refresh_status)
            self.directories_tab.settings_changed.connect(self.filters_tab._update_database_info)
        if hasattr(self.filters_tab, "database_updated"):
            self.filters_tab.database_updated.connect(self._on_database_updated)
            self.filters_tab.database_updated.connect(self.scan_tab.refresh_profiles)
        if hasattr(self.filters_tab, "filters_changed"):
            self.filters_tab.filters_changed.connect(self._on_filters_changed)

    def _on_tab_changed(self, index):
        """Atualiza dados transitórios quando uma aba é selecionada."""
        widget = self.tab_widget.widget(index)
        if widget is self.scan_tab:
            self.scan_tab.refresh_profiles()
        elif widget is self.reconstruction_tab:
            self.reconstruction_tab.refresh()
        elif widget is self.mame_settings_tab:
            self.mame_settings_tab._load_ini()

    def _on_database_updated(self):
        """Atualiza abas dependentes do dataset."""
        self.home_tab.refresh_status()
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
        """Cancela e aguarda workers antes de fechar o banco SQLite."""
        worker = getattr(self.scan_tab, "worker", None)
        if worker is not None and worker.isRunning():
            worker.cancel()
            worker.wait(10000)
        loader = getattr(self.scan_tab, "loader", None)
        if loader is not None and loader.isRunning():
            loader.wait(5000)
        if self.db:
            self.db.close()
        event.accept()
