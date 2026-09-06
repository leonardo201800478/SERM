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
from .filter_phase_page import FilteringPhasePage
from .home import HomePage
from .log_handler import LogViewer
from .mame_filter_page import MameFilterPage
from .mame_scan_page import MameScanPage
from .reconstruction_phase_page import ReconstructionPhasePage
from .scan_phase_page import ScanPhasePage
from .tools_directories import ToolsDirectoriesPage


class MainWindow(QMainWindow):
    NAV_ITEMS = (
        ("Home", "Página inicial e estado dos emuladores", "SP_DirHomeIcon"),
        ("Diretórios", "Gerenciar diretórios dos emuladores", "SP_DirIcon"),
        ("Ferramentas", "LaunchBox, 7-Zip e outros executáveis auxiliares", "SP_ComputerIcon"),
        ("Configurações", "Configurações dos emuladores", "SP_FileDialogDetailedView"),
        ("Shaders / Bezels", "Aparência, shaders e bezels", "SP_ComputerIcon"),
        ("1 — Scan", "Auditoria completa contra DAT/catalogo", "SP_DriveHDIcon"),
        ("MAME — Scans", "Novo scan, histórico e exclusão de scans MAME", "SP_DriveHDIcon"),
        ("2 — Filtragem", "Aplicar filtros sobre um scan já concluído", "SP_FileDialogDetailedView"),
        ("MAME — Filtros", "Filtros MAME separados por tipo de jogo e tipo de SET", "SP_FileDialogDetailedView"),
        ("3 — Reconstrução", "Montar o set a partir do arquivo filtrado", "SP_FileDialogInfoView"),
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
    def _get_screen_key(screen) -> str:
        geometry = screen.geometry()
        return f"{screen.name().strip()}|{geometry.x()},{geometry.y()},{geometry.width()},{geometry.height()}"

    @staticmethod
    def _intersection_area(first, second) -> int:
        intersection = first.intersected(second)
        return max(0, intersection.width()) * max(0, intersection.height())

    def _find_restore_screen(self, screens, saved_screen, rect):
        target = next((screen for screen in screens if self._get_screen_key(screen) == saved_screen), None)
        if target is None and saved_screen:
            name = saved_screen.split("|", 1)[0]
            target = next((screen for screen in screens if screen.name().strip() == name), None)
        if target is not None:
            return target
        best = max(screens, key=lambda screen: self._intersection_area(rect, screen.availableGeometry()))
        if self._intersection_area(rect, best.availableGeometry()) > 0:
            return best
        return self.screen() or QApplication.primaryScreen() or screens[0]

    def _fit_window_to_screen(self, screen) -> None:
        available = screen.availableGeometry()
        rect = self.frameGeometry()
        width = min(max(rect.width(), self.minimumWidth()), available.width())
        height = min(max(rect.height(), self.minimumHeight()), available.height())
        x = min(max(rect.x(), available.left()), available.right() - width + 1)
        y = min(max(rect.y(), available.top()), available.bottom() - height + 1)
        self.setGeometry(x, y, width, height)

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
        target = self._find_restore_screen(screens, saved_screen, self.frameGeometry())
        if target is not None:
            self._fit_window_to_screen(target)

    def _save_window_layout(self) -> None:
        settings = self._qt_settings()
        screen = self.screen() or QApplication.primaryScreen()
        settings.setValue(self._GEOMETRY_KEY, self.saveGeometry())
        settings.setValue(self._STATE_KEY, self.saveState())
        if screen is not None:
            settings.setValue(self._SCREEN_KEY, self._get_screen_key(screen))
            geometry = screen.geometry()
            settings.setValue(self._SCREEN_GEOMETRY_KEY, f"{geometry.x()},{geometry.y()},{geometry.width()},{geometry.height()}")
        settings.sync()

    def _build_ui(self) -> None:
        root = QWidget(self)
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
        for label, description, style_icon in self.NAV_ITEMS:
            item = QListWidgetItem(self.style().standardIcon(getattr(QStyle, style_icon)), label)
            item.setToolTip(description)
            item.setData(Qt.ItemDataRole.UserRole, description)
            item.setSizeHint(QSize(0, 46))
            self.navigation.addItem(item)
        sidebar_layout.addWidget(self.navigation, 1)
        footer = QLabel("SERM V2\nSistema de Emulação e ROM Management")
        footer.setObjectName("navigationFooter")
        footer.setWordWrap(True)
        sidebar_layout.addWidget(footer)

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("pageStack")
        self.home_section = HomePage(self)
        self.directories_tab = DirectoriesPage(self)
        self.tools_tab = ToolsDirectoriesPage(self)
        self.settings_tab = EmulatorSettingsPage(self)
        self.visuals_tab = EmulatorShadersBezelsPage(self)
        self.scan_tab = ScanPhasePage(self)
        self.mame_scan_tab = MameScanPage(self)
        self.filter_tab = FilteringPhasePage(self)
        self.mame_filter_tab = MameFilterPage(self)
        self.reconstruction_tab = ReconstructionPhasePage(self)
        self.dat_scraper_tab = DatScraperPage(self)
        self.pages = (
            self.home_section,
            self.directories_tab,
            self.tools_tab,
            self.settings_tab,
            self.visuals_tab,
            self.scan_tab,
            self.mame_scan_tab,
            self.filter_tab,
            self.mame_filter_tab,
            self.reconstruction_tab,
            self.dat_scraper_tab,
        )
        for page in self.pages:
            self.page_stack.addWidget(page)
        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.page_stack, 1)
        self.setCentralWidget(root)
        self.navigation.currentRowChanged.connect(self._on_navigation_changed)
        self.navigation.setCurrentRow(0)

    def _on_navigation_changed(self, index: int) -> None:
        if 0 <= index < len(self.pages):
            self.page_stack.setCurrentIndex(index)
            self._refresh_page(index)
            item = self.navigation.item(index)
            self.status_bar.showMessage((item.data(Qt.ItemDataRole.UserRole) or item.text()) if item else "Pronto")

    def _refresh_page(self, index: int) -> None:
        page = self.pages[index]
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            refresh()

    def closeEvent(self, event) -> None:
        self._save_window_layout()
        self.log_viewer.close()
        self.database.dispose()
        super().closeEvent(event)


__all__ = ["MainWindow"]
