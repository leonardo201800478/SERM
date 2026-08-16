from PySide6.QtWidgets import QMainWindow, QTabWidget, QStatusBar
from PySide6.QtCore import Qt

from app.gui.tabs.home_tab import HomeTab
from app.gui.tabs.directories_tab import DirectoriesTab
from app.gui.tabs.filters_tab import FiltersTab
from app.gui.tabs.scan_roms_tab import ScanRomsTab
from app.database.database import Database
from app.config.app_config import AppConfig


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MAME Set Builder")
        self.resize(1024, 768)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Pronto")

        # Banco de dados
        self.config = AppConfig()
        self.db = Database(self.config.db_path)
        self.db.connect()

        # Abas
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        self.home_tab = HomeTab(self)
        self.directories_tab = DirectoriesTab(self)
        self.filters_tab = FiltersTab(self, db=self.db)
        self.scan_tab = ScanRomsTab(self)

        self.tab_widget.addTab(self.home_tab, "Home")
        self.tab_widget.addTab(self.directories_tab, "Diretórios")
        self.tab_widget.addTab(self.filters_tab, "Filtragem")
        self.tab_widget.addTab(self.scan_tab, "Scan Roms")

        # --------------------------------------------------------------
        # CONEXÃO DE SINAIS (movido para __init__)
        # --------------------------------------------------------------

        # Recarregar perfis ao mudar para a aba Scan Roms
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # Diretórios → Home / Filters
        if hasattr(self.directories_tab, 'settings_changed'):
            self.directories_tab.settings_changed.connect(self.home_tab.refresh_status)
            self.directories_tab.settings_changed.connect(self.filters_tab._update_database_info)

        # Banco atualizado → atualiza Home e recarrega perfis no Scan Roms
        if hasattr(self.filters_tab, 'database_updated'):
            self.filters_tab.database_updated.connect(self._on_database_updated)
            # Recarrega a lista de perfis na ScanRomsTab quando o banco muda
            self.filters_tab.database_updated.connect(self.scan_tab.refresh_profiles)

        # Filtros alterados (mudança de perfil na aba Filters) → atualiza label da ScanRomsTab
        if hasattr(self.filters_tab, 'filters_changed'):
            self.filters_tab.filters_changed.connect(self._on_filters_changed)

        # NOTA: Se a FiltersTab emitir um sinal específico para quando um perfil for salvo,
        # ele pode ser conectado aqui. Por exemplo:
        # if hasattr(self.filters_tab, 'profile_saved'):
        #     self.filters_tab.profile_saved.connect(self.scan_tab.refresh_profiles)

    # ========================================================================
    # CALLBACKS PARA SINAIS
    # ========================================================================

    def _on_tab_changed(self, index):
        """Recarrega perfis quando a aba Scan Roms for selecionada."""
        if self.tab_widget.widget(index) is self.scan_tab:
            self.scan_tab.refresh_profiles()

    def _on_database_updated(self):
        """Callback quando o banco é atualizado (ex: importação de dados, categorias, etc.)"""
        self.home_tab.refresh_status()
        if hasattr(self.scan_tab, '_update_ui_state'):
            self.scan_tab._update_ui_state()

    def _on_filters_changed(self):
        """Quando o perfil na aba Filters muda, atualiza o label informativo na ScanRomsTab."""
        if hasattr(self.scan_tab, 'set_active_profile_name'):
            profile_name = self.filters_tab.profile_combo.currentText()
            self.scan_tab.set_active_profile_name(profile_name)

    # ========================================================================
    # API PARA A SCANROMSTAB (fallback de critérios)
    # ========================================================================

    def get_current_filter_criteria(self):
        """Retorna os critérios de filtro atuais da guia FiltersTab.
        Este método é chamado pela ScanRomsTab quando o usuário escolhe
        '(usar perfil da aba Filters)' no seletor de perfis."""
        if hasattr(self.filters_tab, 'current_criteria'):
            return self.filters_tab.current_criteria
        from app.core.models.filter_profile import FilterCriteria
        return FilterCriteria()

    # ========================================================================
    # FECHAMENTO
    # ========================================================================

    def closeEvent(self, event):
        if self.db:
            self.db.close()
        event.accept()