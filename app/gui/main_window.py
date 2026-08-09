from PySide6.QtWidgets import QMainWindow, QTabWidget, QStatusBar
from PySide6.QtCore import Signal
from app.gui.tabs.home_tab import HomeTab
from app.gui.tabs.directories_tab import DirectoriesTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MAME Set Builder")
        self.resize(1024, 768)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Pronto")

        # Tab widget
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # Tabs
        self.home_tab = HomeTab(self)
        self.directories_tab = DirectoriesTab(self)

        self.tab_widget.addTab(self.home_tab, "Home")
        self.tab_widget.addTab(self.directories_tab, "Diretórios")

        # Conectar sinal de mudança de configuração
        self.directories_tab.settings_changed.connect(self.home_tab.refresh_status)

        # Atualizar status inicial
        self.home_tab.refresh_status()