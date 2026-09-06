"""Janela principal do SERM V2."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings, QSize, Qt
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow, QStackedWidget, QStyle, QVBoxLayout, QWidget

from ..config.settings import Settings
from ..database.bootstrap import apply_migrations
from ..database.engine import create_sqlite_engine
from .dat_scraper import DatScraperPage
from .emulator_directories_page import DirectoriesPage
from .emulator_settings_page import EmulatorSettingsPage
from .emulator_shaders_bezels_page import EmulatorShadersBezelsPage
from .filter_profiles_layout import FilterProfilesPage
from .home import HomePage
from .log_handler import LogViewer
from .reconstruction_page import ReconstructionPage


class MainWindow(QMainWindow):
    NAV_ITEMS = (
        ("Home", "Página inicial e estado dos emuladores", "SP_DirHomeIcon"),
        ("Diretórios", "Gerenciar diretórios dos emuladores", "SP_DirIcon"),
        ("Configurações", "Configurações dos emuladores", "SP_FileDialogDetailedView"),
        ("Shaders / Bezels", "Aparência, shaders e bezels", "SP_ComputerIcon"),
        ("Filtros e Scan", "Definir o set, salvar o perfil e executar o scan", "SP_DriveHDIcon"),
        ("Reconstrução", "Planejar e executar a reconstrução das ROMs", "SP_FileDialogInfoView"),
        ("Scraper de DATs", "Importação e processamento de DATs", "SP_FileIcon"),
    )
    _GEOMETRY_KEY = "main_window/geometry"
    _STATE_KEY = "main_window/state"
    _SCREEN_KEY = "main_window/screen_key"
    _SCREEN_GEOMETRY_KEY = "main_window/screen_geometry"
    _DEFAULT_SIZE = QSize(1280, 720)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SERM V2")
        self.resize(self._DEFAULT_SIZE)
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
        self._restore_window_layout()

    @staticmethod
    def _qt_settings() -> QSettings:
        return QSettings("SERM", "SERM V2")

    @staticmethod
    def _screen_key(screen) -> str:
        geometry = screen.geometry()
        return f"{screen.name().strip()}|{geometry.x()},{geometry.y()},{geometry.width()},{geometry.height()}"

    @staticmethod
    def _intersection_area(first, second) -> int:
        intersection = first.intersected(second)
        return max(0, intersection.width()) * max(0, intersection.height())

    def _restore_window_layout(self) -> None:
        settings = self._qt_settings()
        geometry = settings.value(self._GEOMETRY_KEY, QByteArray())
        state = settings.value(self._STATE_KEY, QByteArray())
        saved_screen = str(settings.value(self._SCREEN_KEY, ""))
        if isinstance(geometry, QByteArray) and not geometry.isEmpty():
            self.restoreGeometry(geometry)
        if isinstance(state, QByteArray) and not state.isEmpty():
            self.restoreState(state)
        screens = QApplication.screens()
        if not screens:
            return
        target = None
        if saved_screen:
            target = next((screen for screen in screens if self._screen_key(screen) == saved_screen), None)
            if target is None:
                saved_name = saved_screen.split("|", 1)[0]
                target = next((screen for screen in screens if screen.name().strip() == saved_name), None)
        if target is None:
            target = max(screens, key=lambda screen: self._intersection_area(self.frameGeometry(), screen.availableGeometry()))
        if target is None:
            target = QApplication.primaryScreen()
        if target is None:
            return
        available = target.availableGeometry()
        frame = self.frameGeometry()
        if frame.width() > available.width():
            frame.setWidth(available.width())
        if frame.height() > available.height():
            frame.setHeight(available.height())
        frame.moveLeft(max(available.left(), min(frame.left(), available.right() - frame.width() + 1)))
        frame.moveTop(max(available.top(), min(frame.top(), available.bottom() - frame.height() + 1)))
        self.setGeometry(frame)

    def _save_window_layout(self) -> None:
        settings = self._qt_settings()
        settings.setValue(self._GEOMETRY_KEY, self.saveGeometry())
        settings.setValue(self._STATE_KEY, self.saveState())
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            settings.setValue(self._SCREEN_KEY, self._screen_key(screen))
            settings.setValue(self._SCREEN_GEOMETRY_KEY, screen.geometry())
        settings.sync()

    def closeEvent(self, event) -> None:
        self._save_window_layout()
        if hasattr(self, "log_viewer"):
            self.log_viewer.close()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)
        sidebar = self._build_sidebar()
        root_layout.addWidget(sidebar)
        self.page_stack = QStackedWidget()
        root_layout.addWidget(self.page_stack, 1)
        self.setCentralWidget(root)
        self.home_tab = HomePage(self)
        self.directories_tab = DirectoriesPage(self)
        self.settings_tab = EmulatorSettingsPage(self)
        self.visuals_tab = EmulatorShadersBezelsPage(self)
        self.filters_tab = FilterProfilesPage(self)
        self.reconstruction_tab = ReconstructionPage(self)
        self.dat_scraper_tab = DatScraperPage(self)
        self.pages = [self.home_tab, self.directories_tab, self.settings_tab, self.visuals_tab, self.filters_tab, self.reconstruction_tab, self.dat_scraper_tab]
        for page in self.pages:
            self.page_stack.addWidget(page)
        self.filters_tab.scan_requested.connect(self._on_scan_requested)
        self.filters_tab.reconstruction_requested.connect(self._on_reconstruction_requested)
        self._connect_page_refreshes()
        self.navigation.setCurrentRow(0)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("navigationSidebar")
        sidebar.setMinimumWidth(200)
        sidebar.setMaximumWidth(260)
        layout = QVBoxLayout(sidebar)
        title = QLabel("SERM")
        title.setProperty("role", "sidebarTitle")
        subtitle = QLabel("V2 · EMULATION MANAGER")
        subtitle.setProperty("role", "sidebarSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        self.navigation = QListWidget()
        for label, _, icon_name in self.NAV_ITEMS:
            item = QListWidgetItem(label)
            icon = getattr(QStyle, icon_name, None)
            if icon is not None:
                item.setIcon(self.style().standardIcon(icon))
            self.navigation.addItem(item)
        self.navigation.currentRowChanged.connect(self._navigate)
        layout.addWidget(self.navigation, 1)
        footer = QLabel("SERM V2\nGerenciamento de Emulação e ROM Management")
        footer.setProperty("role", "sidebarFooter")
        layout.addWidget(footer)
        return sidebar

    def _navigate(self, index: int) -> None:
        if 0 <= index < self.page_stack.count():
            self.page_stack.setCurrentIndex(index)

    def _connect_page_refreshes(self) -> None:
        if hasattr(self.home_tab, "refresh"):
            self.home_tab.refresh()
        if hasattr(self.directories_tab, "refresh"):
            self.directories_tab.refresh()
        if hasattr(self.settings_tab, "refresh"):
            self.settings_tab.refresh()
        if hasattr(self.visuals_tab, "refresh"):
            self.visuals_tab.refresh()
        if hasattr(self.filters_tab, "refresh"):
            self.filters_tab.refresh()
        if hasattr(self.reconstruction_tab, "refresh"):
            self.reconstruction_tab.refresh()
        if hasattr(self.dat_scraper_tab, "refresh"):
            self.dat_scraper_tab.refresh()

    def _on_scan_requested(self, profile) -> None:
        self.status_bar.showMessage(f"Scan preparado: {profile.name} | ID={profile.profile_id}")

    def _on_reconstruction_requested(self, context) -> None:
        self.reconstruction_tab.set_scan_context(context)
        self.navigation.setCurrentRow(5)
