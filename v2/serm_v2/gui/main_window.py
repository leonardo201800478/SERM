"""Janela principal do SERM V2."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..config.settings import Settings
from ..database.bootstrap import apply_migrations
from ..database.engine import create_sqlite_engine
from .dat_scraper import DatScraperPage
from .emulator_directories_page import DirectoriesPage
from .emulator_settings_page import EmulatorSettingsPage
from .emulator_shaders_bezels_page import EmulatorShadersBezelsPage
from .home import HomePage
from .log_handler import LogViewer
from .mame_guides_page import MameGuidesPage


class MainWindow(QMainWindow):
    """Janela principal com navegação lateral persistente e conteúdo empilhado."""

    NAV_ITEMS = (
        ("Home", "Página inicial e estado dos emuladores", "SP_DirHomeIcon"),
        ("Diretórios", "Gerenciar diretórios dos emuladores", "SP_DirIcon"),
        ("Configurações", "Configurações dos emuladores", "SP_FileDialogDetailedView"),
        ("Shaders / Bezels", "Aparência, shaders e bezels", "SP_ComputerIcon"),
        ("MAME", "Guias e ferramentas do MAME", "SP_DriveHDIcon"),
        ("Scraper de DATs", "Importação e processamento de DATs", "SP_FileIcon"),
    )

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SERM V2")
        self.resize(1280, 720)
        self.setMinimumSize(1152, 648)
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Pronto")

        settings = Settings()
        database_path = Path(settings.database)
        applied = apply_migrations(database_path)
        if applied:
            logging.getLogger(__name__).info("[SERM][DB] migrations aplicadas=%s", ", ".join(applied))
        self.database = create_sqlite_engine(database_path)
        self.log_viewer = LogViewer()
        self._build_ui()

    def _build_ui(self) -> None:
        """Monta a navegação lateral e as páginas sem duplicar funcionalidades."""
        root = QWidget(self)
        root.setObjectName("centralWidget")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        sidebar = QFrame()
        sidebar.setObjectName("navigationSidebar")
        sidebar.setMinimumWidth(205)
        sidebar.setMaximumWidth(235)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 12, 10, 12)
        sidebar_layout.setSpacing(6)

        brand = QLabel("SERM")
        brand.setObjectName("navigationBrand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(brand)

        version = QLabel("V2 • EMULATION MANAGER")
        version.setObjectName("navigationVersion")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(version)
        sidebar_layout.addSpacing(10)

        self.navigation = QListWidget()
        self.navigation.setObjectName("navigationList")
        self.navigation.setIconSize(QSize(20, 20))
        self.navigation.setSpacing(3)
        self.navigation.setFrameShape(QFrame.Shape.NoFrame)
        self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.navigation.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)

        for index, (label, description, style_icon) in enumerate(self.NAV_ITEMS):
            item = QListWidgetItem(self.style().standardIcon(getattr(QStyle, style_icon)), label)
            item.setToolTip(description)
            item.setData(Qt.ItemDataRole.UserRole, description)
            item.setSizeHint(QSize(0, 46))
            self.navigation.addItem(item)

        self.navigation.currentRowChanged.connect(self._on_navigation_changed)
        sidebar_layout.addWidget(self.navigation, 1)

        footer = QLabel("SERM V2\nSistema de Emulação e ROM Management")
        footer.setObjectName("navigationFooter")
        footer.setWordWrap(True)
        sidebar_layout.addWidget(footer)

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("pageStack")

        self.home_section = HomePage(self)
        self.directories_tab = DirectoriesPage(self)
        self.settings_tab = EmulatorSettingsPage(self)
        self.visuals_tab = EmulatorShadersBezelsPage(self)
        self.mame_guides_tab = MameGuidesPage(self)
        self.dat_scraper_tab = DatScraperPage(self)

        self.pages = (
            self.home_section,
            self.directories_tab,
            self.settings_tab,
            self.visuals_tab,
            self.mame_guides_tab,
            self.dat_scraper_tab,
        )
        for page in self.pages:
            self.page_stack.addWidget(page)

        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.page_stack, 1)
        self.setCentralWidget(root)

        self.navigation.setCurrentRow(0)

    def _on_navigation_changed(self, index: int) -> None:
        """Seleciona a página e atualiza somente o componente necessário."""
        if index < 0 or index >= len(self.pages):
            return
        self.page_stack.setCurrentIndex(index)
        self._refresh_page(index)
        item = self.navigation.item(index)
        if item is not None:
            self.status_bar.showMessage(item.data(Qt.ItemDataRole.UserRole) or item.text())

    def _refresh_page(self, index: int) -> None:
        """Atualiza o conteúdo dinâmico da página selecionada."""
        page = self.pages[index]
        if page is self.home_section:
            self.home_section.refresh()
        elif page is self.directories_tab:
            self.directories_tab.refresh()
        elif page is self.settings_tab:
            self.settings_tab.refresh()
        elif page is self.visuals_tab:
            self.visuals_tab.refresh()
        elif page is self.mame_guides_tab:
            self.mame_guides_tab.refresh()
        elif page is self.dat_scraper_tab:
            self.dat_scraper_tab.setFocus()

    def _on_tab_changed(self, index: int) -> None:
        """Mantém compatibilidade com chamadas antigas da navegação por abas."""
        self._on_navigation_changed(index)

    def closeEvent(self, event) -> None:  # noqa: N802
        """Fecha os recursos locais da aplicação."""
        self.log_viewer.close()
        self.database.dispose()
        super().closeEvent(event)


# Importações Qt mantidas no fim para evitar poluir a seção principal de widgets.
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStyle


__all__ = ["MainWindow"]
