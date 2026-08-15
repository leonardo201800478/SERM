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
        self.scan_tab = ScanRomsTab(self)

        self.tab_widget.addTab(self.home_tab, "Home")
        self.tab_widget.addTab(self.directories_tab, "Diretórios")
        self.tab_widget.addTab(self.filters_tab, "Filtragem")
        self.tab_widget.addTab(self.scan_tab, "Scan Roms")

        # Conecta sinais (ajuste conforme existir)
        if hasattr(self.directories_tab, 'settings_changed'):
            self.directories_tab.settings_changed.connect(self.home_tab.refresh_status)
            self.directories_tab.settings_changed.connect(self.filters_tab._update_database_info)
        if hasattr(self.filters_tab, 'database_updated'):
            self.filters_tab.database_updated.connect(self.home_tab.refresh_status)
            self.filters_tab.database_updated.connect(self.scan_tab._load_filter_profiles)

    def closeEvent(self, event):
        if self.db:
            self.db.close()
        event.accept()