"""Main window for SERM V2, com a Home funcional baseada no núcleo testado."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from app.config.app_config import AppConfig
from app.database.database import Database
from app.gui.tabs.directories_tab import DirectoriesTab
from app.gui.tabs.retroarch_directories_tab import RetroArchDirectoriesTab

from .home import HomePage
from .log_handler import LogViewer
from .no_intro_home import NoIntroPage
from .redump_home import RedumpPage


class MainWindow(QMainWindow):
    """Janela V2 que preserva os contratos de configuração do SERM original."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SERM")
        self.resize(1280, 820)
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Pronto")
        self.config = AppConfig()
        self.db = Database(self.config.db_path)
        self.db.connect()
        self.log_viewer = LogViewer()
        self._build_ui()

    def _build_ui(self) -> None:
        """Monta a navegação V2 mantendo Home e Diretórios funcionais."""
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(QLabel("SERM V2", alignment=Qt.AlignmentFlag.AlignLeft))

        self.tab_widget = QTabWidget()
        self.home_section = HomePage(self)
        self.directories_tab = DirectoriesTab(self)
        self.retroarch_directories_tab = RetroArchDirectoriesTab(self)

        self.tab_widget.addTab(self.home_section, "Home")
        self.tab_widget.addTab(self.directories_tab, "Diretórios")
        self.tab_widget.addTab(NoIntroPage(self), "No-Intro")
        self.tab_widget.addTab(RedumpPage(self), "Redump")
        self.tab_widget.addTab(self.retroarch_directories_tab, "RetroArch Diretórios")
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tab_widget, 1)
        self.setCentralWidget(root)

    def _on_tab_changed(self, index: int) -> None:
        """Atualiza somente a tela selecionada, sem consultar rede desnecessariamente."""
        widget = self.tab_widget.widget(index)
        if widget is self.home_section:
            self.home_section.refresh()
        elif widget is self.directories_tab:
            self.directories_tab._refresh_ui_state()
        elif widget is self.retroarch_directories_tab:
            self.retroarch_directories_tab.refresh()

    def closeEvent(self, event) -> None:  # noqa: N802
        """Fecha recursos locais sem interromper workers ativos."""
        self.log_viewer.close()
        self.db.close()
        super().closeEvent(event)
