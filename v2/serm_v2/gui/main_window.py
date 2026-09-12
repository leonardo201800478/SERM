"""Janela principal do SERM V2."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings, QSize, Qt
from PySide6.QtWidgets import (
    QApplication, QDockWidget, QFrame, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMainWindow, QStackedWidget, QStyle, QVBoxLayout, QWidget,
)

from ..config.settings import Settings
from ..database.bootstrap import apply_migrations
from ..database.engine import create_sqlite_engine
from .configuration_page import ConfigurationPage
from .data_sources_page import DataSourcesPage
from .filter_phase_page import FilteringPhasePage
from .home import HomePage
from .log_handler import LogViewer
from .mame_studio_page import MameStudioPage
from .ui_preferences import UiPreferences
from .ui_translation_runtime import retranslate_widget_tree


class MainWindow(QMainWindow):
    """Shell da aplicação, organizada por domínios funcionais."""

    NAV_ITEMS = (
        ("home", "Visão geral do SERM e estado do ambiente", "SP_DirHomeIcon"),
        ("configuration", "Diretórios, ferramentas, emuladores e vídeo", "SP_FileDialogDetailedView"),
        ("sources", "Aquisição e atualização de DATs e recursos externos", "SP_FileIcon"),
        ("mame", "Catálogo, scan, filtros e reconstrução MAME", "SP_DriveHDIcon"),
        ("other_systems", "Filtragem pós-scan para No-Intro, Redump, WHLoader e C64", "SP_FileDialogInfoView"),
    )
    _GEOMETRY_KEY = "main_window/geometry"
    _STATE_KEY = "main_window/state"
    _SCREEN_KEY = "main_window/screen_key"
    _SCREEN_GEOMETRY_KEY = "main_window/screen_geometry"
    _DEFAULT_SIZE = QSize(1200, 700)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SERM V2")
        self.resize(self._DEFAULT_SIZE)
        self.setMinimumSize(1100, 620)
        self.status_bar = self.statusBar()
        self.status_bar.showMessage(UiPreferences.text("ready"))
        settings = Settings()
        database_path = Path(settings.database)
        applied = apply_migrations(database_path)
        if applied:
            logging.getLogger(__name__).info("[SERM][DB] migrations aplicadas=%s", ", ".join(applied))
        self.database = create_sqlite_engine(database_path)
        self.log_viewer = LogViewer()
        self._build_ui()
        self._build_log_dock()
        self.configuration_page.appearance_page.language_changed.connect(self._language_changed)
        self._retranslate_navigation()
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
        if screens:
            self._fit_window_to_screen(self._find_restore_screen(screens, saved_screen, self.frameGeometry()))

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
        root.setObjectName("centralWidget")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        sidebar = QFrame()
        sidebar.setObjectName("navigationSidebar")
        sidebar.setMinimumWidth(176)
        sidebar.setMaximumWidth(205)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(7, 8, 7, 8)
        sidebar_layout.setSpacing(4)

        brand = QLabel("SERM")
        brand.setObjectName("navigationBrand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(brand)
        version = QLabel("V2 • EMULATION MANAGER")
        version.setObjectName("navigationVersion")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(version)
        sidebar_layout.addSpacing(4)

        self.navigation = QListWidget()
        self.navigation.setObjectName("navigationList")
        self.navigation.setIconSize(QSize(18, 18))
        self.navigation.setSpacing(2)
        self.navigation.setFrameShape(QFrame.Shape.NoFrame)
        self.navigation.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.navigation.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        sidebar_layout.addWidget(self.navigation, 1)

        self.footer = QLabel("SERM V2\nSistema de Emulação e ROM Management")
        self.footer.setObjectName("navigationFooter")
        self.footer.setWordWrap(True)
        sidebar_layout.addWidget(self.footer)

        self.page_stack = QStackedWidget()
        self.page_stack.setObjectName("pageStack")
        self.home_section = HomePage(self)
        self.configuration_page = ConfigurationPage(self)
        self.data_sources_page = DataSourcesPage(self)
        self.mame_studio_page = MameStudioPage(self)
        self.other_systems_page = FilteringPhasePage(self)
        self.pages = (
            self.home_section, self.configuration_page, self.data_sources_page,
            self.mame_studio_page, self.other_systems_page,
        )
        for page in self.pages:
            self.page_stack.addWidget(page)
        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.page_stack, 1)
        self.setCentralWidget(root)
        self.navigation.currentRowChanged.connect(self._on_navigation_changed)

    def _build_log_dock(self) -> None:
        """Adiciona o painel de logs à janela principal em modo compacto."""
        self.log_dock = QDockWidget(UiPreferences.text("logs"), self)
        self.log_dock.setObjectName("logDock")
        self.log_dock.setMinimumHeight(72)
        self.log_dock.setMaximumHeight(150)
        console = self.log_viewer.create_console(self.log_dock)
        console.setObjectName("logConsole")
        self.log_dock.setWidget(console)
        self.log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.resizeDocks([self.log_dock], [118], Qt.Orientation.Vertical)

    def _retranslate_navigation(self) -> None:
        """Cria e atualiza a navegação sem depender de uma sobrecarga inexistente."""
        while self.navigation.count() < len(self.NAV_ITEMS):
            index = self.navigation.count()
            key, _, style_icon = self.NAV_ITEMS[index]
            icon = self.style().standardIcon(getattr(QStyle, style_icon))
            item = QListWidgetItem(icon, UiPreferences.text(key))
            item.setSizeHint(QSize(0, 38))
            self.navigation.addItem(item)
        for index, (key, description, _style_icon) in enumerate(self.NAV_ITEMS):
            item = self.navigation.item(index)
            item.setText(UiPreferences.text(key))
            item.setToolTip(description)
            item.setData(Qt.ItemDataRole.UserRole, description)
        if hasattr(self, "footer"):
            self.footer.setText("SERM V2\nSistema de Emulação e ROM Management")
        if hasattr(self, "log_dock"):
            self.log_dock.setWindowTitle(UiPreferences.text("logs"))
        self.status_bar.showMessage(UiPreferences.text("ready"))

    def _language_changed(self, language: str) -> None:
        self._retranslate_navigation()
        for page in self.pages:
            retranslate_widget_tree(page, language)
        self.configuration_page.retranslate_ui()

    def _on_navigation_changed(self, index: int) -> None:
        if 0 <= index < len(self.pages):
            self.page_stack.setCurrentIndex(index)
            self._refresh_page(index)
            item = self.navigation.item(index)
            self.status_bar.showMessage((item.data(Qt.ItemDataRole.UserRole) or item.text()) if item else UiPreferences.text("ready"))

    def _refresh_page(self, index: int) -> None:
        refresh = getattr(self.pages[index], "refresh", None)
        if callable(refresh):
            refresh()

    def closeEvent(self, event) -> None:
        self._save_window_layout()
        self.log_viewer.close()
        self.database.dispose()
        super().closeEvent(event)


__all__ = ["MainWindow"]
