from PySide6.QtWidgets import QMainWindow, QTabWidget
from app.gui.tabs.home_tab import HomeTab
from app.gui.tabs.directories_tab import DirectoriesTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MAME Set Builder")
        self.resize(1024, 768)

        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        self.home_tab = HomeTab(self)
        self.directories_tab = DirectoriesTab(self)

        self.tab_widget.addTab(self.home_tab, "Home")
        self.tab_widget.addTab(self.directories_tab, "Diretórios")
        # Outras abas serão adicionadas nas fases seguintes