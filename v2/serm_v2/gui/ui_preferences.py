"""Preferências visuais e de idioma da interface SERM V2."""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from .retro_arcade_theme import apply_retro_arcade_theme
from .ui_density import apply_compact_density


LANGUAGES = {
    "pt-BR": "Português (Brasil)",
    "en": "English",
    "es": "Español",
}

TRANSLATIONS = {
    "pt-BR": {
        "home": "Início", "configuration": "Configuração", "sources": "Fontes e Dados",
        "mame": "MAME Studio", "other_systems": "Outros Sistemas", "ready": "Pronto",
        "logs": "Logs", "settings": "Aparência e Idioma", "directories": "Diretórios",
        "tools": "Ferramentas", "emulators": "Emuladores", "video": "Vídeo",
    },
    "en": {
        "home": "Home", "configuration": "Settings", "sources": "Sources & Data",
        "mame": "MAME Studio", "other_systems": "Other Systems", "ready": "Ready",
        "logs": "Logs", "settings": "Appearance & Language", "directories": "Directories",
        "tools": "Tools", "emulators": "Emulators", "video": "Video",
    },
    "es": {
        "home": "Inicio", "configuration": "Configuración", "sources": "Fuentes y Datos",
        "mame": "MAME Studio", "other_systems": "Otros Sistemas", "ready": "Listo",
        "logs": "Registros", "settings": "Apariencia e Idioma", "directories": "Directorios",
        "tools": "Herramientas", "emulators": "Emuladores", "video": "Vídeo",
    },
}

LIGHT_THEME = """
QWidget { background:#f4f7fb; color:#1b2430; font-family:"Segoe UI"; font-size:10pt; }
QMainWindow, QWidget#centralWidget, QStackedWidget#pageStack { background:#f4f7fb; }
QLabel { color:#273444; background:transparent; }
QLabel[role="title"] { color:#132238; font-size:20pt; font-weight:900; }
QLabel[role="section"] { color:#1769aa; font-size:11pt; font-weight:800; }
QFrame#navigationSidebar { background:#ffffff; border:1px solid #d7e0ea; border-radius:12px; }
QLabel#navigationBrand { color:#10243b; font-size:23pt; font-weight:900; letter-spacing:2px; }
QLabel#navigationVersion { color:#1677c8; font-size:8pt; font-weight:800; }
QListWidget#navigationList { background:transparent; border:0; outline:none; }
QListWidget#navigationList::item { color:#5b6877; background:transparent; border:1px solid transparent; border-radius:8px; padding:8px 10px; min-height:30px; font-weight:700; }
QListWidget#navigationList::item:hover { color:#16324f; background:#edf4fb; border-color:#d5e5f4; }
QListWidget#navigationList::item:selected { color:#ffffff; background:#1976d2; border-color:#1976d2; }
QLabel#navigationFooter { color:#8290a0; font-size:7.5pt; }
QGroupBox { background:#ffffff; border:1px solid #d7e0ea; border-radius:9px; margin-top:12px; padding:15px 10px 10px; }
QGroupBox::title { color:#1769aa; background:#f4f7fb; padding:0 6px; font-weight:800; }
QFrame#panel { background:#ffffff; border:1px solid #d7e0ea; }
QPushButton { background:#ffffff; color:#26384b; border:1px solid #c7d3df; border-radius:7px; padding:7px 13px; min-height:22px; font-weight:700; }
QPushButton:hover { background:#edf5fc; border-color:#1976d2; color:#125b98; }
QPushButton:pressed { background:#dbeeff; }
QPushButton:disabled { color:#9aa6b2; background:#eef1f4; border-color:#d8dee5; }
QPushButton[role="primary"] { background:#1976d2; color:#ffffff; border-color:#1976d2; }
QPushButton[role="primary"]:hover { background:#1565c0; }
QLineEdit, QComboBox, QSpinBox { background:#ffffff; color:#26384b; border:1px solid #c7d3df; border-radius:6px; padding:7px 9px; selection-background-color:#1976d2; selection-color:#ffffff; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border:2px solid #1976d2; }
QCheckBox, QRadioButton { color:#34475a; spacing:7px; }
QCheckBox::indicator, QRadioButton::indicator { width:13px; height:13px; border:1px solid #9aaaba; background:#ffffff; }
QCheckBox::indicator:checked, QRadioButton::indicator:checked { background:#1976d2; border-color:#1976d2; }
QTabWidget::pane { background:#ffffff; border:1px solid #d7e0ea; }
QTabBar::tab { background:#edf2f7; color:#637386; border:1px solid #d7e0ea; padding:8px 16px; }
QTabBar::tab:selected { background:#1976d2; color:#ffffff; border-color:#1976d2; }
QListWidget, QTreeWidget, QTableWidget { background:#ffffff; color:#293b4d; border:1px solid #d2dce6; alternate-background-color:#f6f9fc; selection-background-color:#1976d2; selection-color:#ffffff; }
QHeaderView::section { background:#edf2f7; color:#42566b; border:0; padding:6px 8px; font-weight:800; }
QProgressBar { background:#e8edf2; border:1px solid #c7d3df; text-align:center; color:#26384b; min-height:13px; }
QProgressBar::chunk { background:#21a366; }
QScrollArea { background:#f4f7fb; border:0; }
QScrollBar:vertical { background:#e8edf2; width:12px; }
QScrollBar::handle:vertical { background:#b5c2cf; min-height:28px; border-radius:5px; }
QScrollBar::handle:vertical:hover { background:#1976d2; }
QStatusBar { background:#ffffff; color:#4e6174; border-top:1px solid #d7e0ea; }
QToolTip { background:#ffffff; color:#24364a; border:1px solid #1976d2; padding:5px; }
"""


class UiPreferences:
    """Acesso centralizado às preferências persistentes da UI."""

    _ORG = "SERM"
    _APP = "SERM V2"
    THEME_KEY = "ui/theme"
    LANGUAGE_KEY = "ui/language"

    @classmethod
    def settings(cls) -> QSettings:
        return QSettings(cls._ORG, cls._APP)

    @classmethod
    def theme(cls) -> str:
        value = str(cls.settings().value(cls.THEME_KEY, "dark")).lower()
        return value if value in {"dark", "light"} else "dark"

    @classmethod
    def language(cls) -> str:
        value = str(cls.settings().value(cls.LANGUAGE_KEY, "pt-BR"))
        return value if value in LANGUAGES else "pt-BR"

    @classmethod
    def set_theme(cls, value: str) -> None:
        cls.settings().setValue(cls.THEME_KEY, value if value in {"dark", "light"} else "dark")
        cls.settings().sync()

    @classmethod
    def set_language(cls, value: str) -> None:
        cls.settings().setValue(cls.LANGUAGE_KEY, value if value in LANGUAGES else "pt-BR")
        cls.settings().sync()

    @classmethod
    def text(cls, key: str, language: str | None = None) -> str:
        lang = language or cls.language()
        return TRANSLATIONS.get(lang, TRANSLATIONS["pt-BR"]).get(key, key)


def apply_user_theme(app: QApplication, mode: str | None = None) -> None:
    """Aplica o tema selecionado e, em seguida, a densidade compacta da GUI."""
    selected = mode or UiPreferences.theme()
    if selected == "light":
        app.setStyle("Fusion")
        app.setStyleSheet(LIGHT_THEME)
    else:
        apply_retro_arcade_theme(app)
    apply_compact_density(app)


__all__ = ["LANGUAGES", "LIGHT_THEME", "TRANSLATIONS", "UiPreferences", "apply_user_theme"]
