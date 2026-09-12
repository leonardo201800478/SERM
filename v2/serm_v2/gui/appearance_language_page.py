"""Tela inicial de aparência e idioma do SERM V2."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QComboBox, QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from .ui_preferences import LANGUAGES, UiPreferences, apply_user_theme


class AppearanceLanguagePage(QWidget):
    """Configura tema e idioma persistentes, com layout sem sobreposição."""

    changed = Signal()
    language_changed = Signal(str)

    TRANSLATIONS = {
        "pt-BR": {
            "title": "Aparência e Idioma", "appearance": "APARÊNCIA", "theme": "Tema:",
            "language_group": "IDIOMA DA INTERFACE", "language": "Idioma:",
            "note": "O tema é aplicado imediatamente. O idioma é persistente e as telas preparadas para tradução são atualizadas sem alterar os dados do usuário.",
        },
        "en": {
            "title": "Appearance & Language", "appearance": "APPEARANCE", "theme": "Theme:",
            "language_group": "INTERFACE LANGUAGE", "language": "Language:",
            "note": "The theme is applied immediately. The language is persistent and translated screens update without changing user data.",
        },
        "es": {
            "title": "Apariencia e Idioma", "appearance": "APARIENCIA", "theme": "Tema:",
            "language_group": "IDIOMA DE LA INTERFAZ", "language": "Idioma:",
            "note": "El tema se aplica inmediatamente. El idioma es persistente y las pantallas traducidas se actualizan sin cambiar los datos del usuario.",
        },
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        self.title = QLabel()
        self.title.setProperty("role", "title")
        root.addWidget(self.title)

        self.appearance = QGroupBox()
        appearance_form = QFormLayout(self.appearance)
        appearance_form.setContentsMargins(10, 8, 10, 9)
        appearance_form.setHorizontalSpacing(12)
        appearance_form.setVerticalSpacing(5)
        self.theme_label = QLabel()
        self.theme = QComboBox()
        self.theme.addItem("Modo escuro", "dark")
        self.theme.addItem("Modo claro", "light")
        self.theme.setCurrentIndex(max(0, self.theme.findData(UiPreferences.theme())))
        self.theme.currentIndexChanged.connect(self._theme_changed)
        appearance_form.addRow(self.theme_label, self.theme)
        root.addWidget(self.appearance)

        self.language_group = QGroupBox()
        language_form = QFormLayout(self.language_group)
        language_form.setContentsMargins(10, 8, 10, 9)
        language_form.setHorizontalSpacing(12)
        language_form.setVerticalSpacing(5)
        self.language_label = QLabel()
        self.language = QComboBox()
        for code, name in LANGUAGES.items():
            self.language.addItem(name, code)
        self.language.setCurrentIndex(max(0, self.language.findData(UiPreferences.language())))
        self.language.currentIndexChanged.connect(self._language_changed)
        language_form.addRow(self.language_label, self.language)
        root.addWidget(self.language_group)

        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setMinimumHeight(34)
        root.addWidget(self.note)
        root.addStretch(1)

    def retranslate_ui(self) -> None:
        text = self.TRANSLATIONS.get(UiPreferences.language(), self.TRANSLATIONS["pt-BR"])
        self.title.setText(text["title"])
        self.appearance.setTitle(text["appearance"])
        self.theme_label.setText(text["theme"])
        self.language_group.setTitle(text["language_group"])
        self.language_label.setText(text["language"])
        self.note.setText(text["note"])

    def _theme_changed(self, *_args) -> None:
        value = str(self.theme.currentData())
        UiPreferences.set_theme(value)
        app = QApplication.instance()
        if app is not None:
            apply_user_theme(app, value)
        self.changed.emit()

    def _language_changed(self, *_args) -> None:
        value = str(self.language.currentData())
        UiPreferences.set_language(value)
        self.retranslate_ui()
        self.language_changed.emit(value)
        self.changed.emit()


__all__ = ["AppearanceLanguagePage"]
