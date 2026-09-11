"""Hub visual compacto de configuração do SERM V2."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QTabWidget, QVBoxLayout, QWidget

from .appearance_language_page import AppearanceLanguagePage
from .emulator_directories_page import DirectoriesPage
from .emulator_settings_page import EmulatorSettingsPage
from .emulator_shaders_bezels_page import EmulatorShadersBezelsPage
from .tools_directories import ToolsDirectoriesPage
from .ui_preferences import UiPreferences


class _ConfigCard(QFrame):
    """Entrada compacta para um domínio de configuração."""

    def __init__(self, number: str, title: str, description: str, action, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("configCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(4)
        number_label = QLabel(number)
        number_label.setObjectName("configCardNumber")
        title_label = QLabel(title)
        title_label.setObjectName("configCardTitle")
        description_label = QLabel(description)
        description_label.setObjectName("configCardDescription")
        description_label.setWordWrap(True)
        button = QPushButton("ABRIR")
        button.clicked.connect(action)
        layout.addWidget(number_label)
        layout.addWidget(title_label)
        layout.addWidget(description_label, 1)
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)


class ConfigurationPage(QWidget):
    """Centraliza configuração em domínios visuais compactos."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(7)
        title = QLabel("CONFIGURAÇÃO")
        title.setProperty("role", "title")
        subtitle = QLabel("Diretórios, executáveis, ferramentas, vídeo e aparência do ambiente SERM.")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.directories_page = DirectoriesPage(self)
        self.tools_page = ToolsDirectoriesPage(self)
        self.emulators_page = EmulatorSettingsPage(self)
        self.video_page = EmulatorShadersBezelsPage(self)
        self.appearance_page = AppearanceLanguagePage(self)
        self.tabs.addTab(self.directories_page, "")
        self.tabs.addTab(self.tools_page, "")
        self.tabs.addTab(self.emulators_page, "")
        self.tabs.addTab(self.video_page, "")
        self.tabs.addTab(self.appearance_page, "")
        self.tabs.hide()

        cards = QGridLayout()
        cards.setContentsMargins(0, 0, 0, 0)
        cards.setHorizontalSpacing(7)
        cards.setVerticalSpacing(7)
        entries = (
            ("01", "Diretórios", "MAME, ROMs, BIOS e artwork.", 0),
            ("02", "Ferramentas", "Executáveis e integrações auxiliares.", 1),
            ("03", "Emuladores", "Executáveis, versões e parâmetros.", 2),
            ("04", "Vídeo e shaders", "Shaders, bezels e apresentação.", 3),
            ("05", "Aparência e idioma", "Tema, idioma e preferências visuais.", 4),
        )
        for pos, (number, card_title, description, index) in enumerate(entries):
            cards.addWidget(
                _ConfigCard(number, card_title, description, lambda i=index: self._open(i), self),
                pos // 3, pos % 3,
            )
        root.addLayout(cards)
        root.addWidget(self.tabs, 1)
        self.appearance_page.language_changed.connect(lambda _language: self.retranslate_ui())
        self.retranslate_ui()

    def _open(self, index: int) -> None:
        self.tabs.show()
        self.tabs.setCurrentIndex(index)
        self._refresh_current()

    def _refresh_current(self) -> None:
        page = self.tabs.currentWidget()
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            refresh()

    def retranslate_ui(self) -> None:
        labels = ("directories", "tools", "emulators", "video", "settings")
        for index, key in enumerate(labels):
            self.tabs.setTabText(index, UiPreferences.text(key))

    def refresh(self) -> None:
        self._refresh_current()


__all__ = ["ConfigurationPage"]
