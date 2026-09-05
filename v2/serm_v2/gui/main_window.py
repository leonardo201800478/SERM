"""Janela principal do SERM V2."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings, QSize, Qt
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QStackedWidget, QStyle, QVBoxLayout, QWidget,
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
from .rom_scan_page import RomScanPage


class MainWindow(QMainWindow):
    """Janela principal com navegação lateral persistente e conteúdo empilhado."""

    NAV_ITEMS = (
        ("Home", "Página inicial e estado dos emuladores", "SP_DirHomeIcon"),
        ("Diretórios", "Gerenciar diretórios dos emuladores", "SP_DirIcon"),
        ("Configurações", "Configurações dos emuladores", "SP_FileDialogDetailedView"),
        ("Shaders / Bezels", "Aparência, shaders e bezels", "SP_ComputerIcon"),
        ("Scan de ROMs", "Verificação física de ROMs e mídias", "SP_DriveHDIcon"),
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
        current = self.screen()
        target = next((screen for screen in screens if self._screen_key(screen) == saved_screen), None)
        if target is None and saved_screen:
            saved_name = saved_screen.split("|", 1)[0]
            target = next((screen for screen in screens if screen.name().strip() == saved_name), None)
        window_rect = self.frameGeometry()
        if target is None:
            best_area = 0
            for screen in screens:
                area = self._intersection_area(window_rect, screen.availableGeometry())
                if area > best_area:
                    best_area = area
                    target = screen
            if best_area == 0:
                target = current or QApplication.primaryScreen() or screens[0]
        if target is None:
            return
        available = target.availableGeometry()
        width = min(max(window_rect.width(), self.minimumWidth()), available.width())
        height = min(max(window_rect.height(), self.minimumHeight()), available.height())
        x = min(max(window_rect.x(), available.left()), available.right() - width + 1)
        y = min(max(window_rect.y(), available.top()), available.bottom() - height + 1)
        self.setGeometry(x, y, width, height)
        if saved_screen and self._screen_key(target) != saved_screen:
            logging.getLogger(__name__).info("[SERM][GUI] monitor salvo indisponível; fallback para '%s'", target.name())

    def _save_window_layout(self) -> None:
        settings = self._qt_settings()
        screen = self.screen() or QApplication.primaryScreen()
        settings.setValue(self._GEOMETRY_KEY, self.saveGeometry())
        settings.setValue(self._STATE_KEY, self.saveState())
        if screen is not None:
            settings.setValue(self._SCREEN_KEY, self._screen_key(screen))
            geometry = screen.geometry()
            settings.setValue(self._SCREEN_GEOMETRY_KEY, f"{geometry.x()},{geometry.y()},{geometry.width()},{geometry.height()}")
        settings.sync()

    def _build_ui(self) -> None:
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
        for label, description, style_icon in self.NAV_ITEMS:
            icon = self.style().standardIcon(getattr(QStyle, style_icon))
            item = QListWidgetItem(icon, label)
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
        self.rom_scan_tab = RomScanPage(self)
        self.dat_scraper_tab = DatScraperPage(self)
        self.pages = (
            self.home_section, self.directories_tab, self.settings_tab,
            self.visuals_tab, self.rom_scan_tab, self.dat_scraper_tab,
        )
        for page in self.pages:
            self.page_stack.addWidget(page)
        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.page_stack, 1)
        self.setCentralWidget(root)
        self.navigation.setCurrentRow(0)

    def _on_navigation_changed(self, index: int) -> None:
        if index < 0 or index >= len(self.pages):
            return
        self.page_stack.setCurrentIndex(index)
        self._refresh_page(index)
        item = self.navigation.item(index)
        if item is not None:
            self.status_bar.showMessage(item.data(Qt.ItemDataRole.UserRole) or item.text())

    def _refresh_page(self, index: int) -> None:
        page = self.pages[index]
        if page is self.home_section:
            self.home_section.refresh()
        elif page is self.directories_tab:
            self.directories_tab.refresh()
        elif page is self.settings_tab:
            self.settings_tab.refresh()
        elif page is self.visuals_tab:
            self.visuals_tab.refresh()
        elif page is self.rom_scan_tab:
            self.rom_scan_tab.refresh()
        elif page is self.dat_scraper_tab:
            self.dat_scraper_tab.setFocus()

    def _on_tab_changed(self, index: int) -> None:
        self._on_navigation_changed(index)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_window_layout()
        self.log_viewer.close()
        self.database.dispose()
        super().closeEvent(event)


__all__ = ["MainWindow"]
