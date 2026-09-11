"""Tela de aparência e idioma do SERM V2."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QComboBox, QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from .ui_preferences import LANGUAGES, UiPreferences, apply_user_theme


class AppearanceLanguagePage(QWidget):
    """Configura tema claro/escuro e idioma persistentes da aplicação."""

    changed = Signal()
    language_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._building = False
        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self.title = QLabel()
        self.title.setProperty("role", "title")
        root.addWidget(self.title)

        self.appearance = QGroupBox()
        form = QFormLayout(self.appearance)
        form.setContentsMargins(10, 12, 10, 10)
        self.theme = QComboBox()
        self.theme.addItem("Modo escuro", "dark")
        self.theme.addItem("Modo claro", "light")
        self.theme.setCurrentIndex(max(0, self.theme.findData(UiPreferences.theme())))
        self.theme.currentIndexChanged.connect(self._theme_changed)
        form.addRow(self.theme)
        self.theme_form = form
        root.addWidget(self.appearance)

        self.language_group = QGroupBox()
        language_form = QFormLayout(self.language_group)
        language_form.setContentsMargins(10, 12, 10, 10)
        self.language = QComboBox()
        for code, name in LANGUAGES.items():
            self.language.addItem(name, code)
        self.language.setCurrentIndex(max(0, self.language.findData(UiPreferences.language())))
        self.language.currentIndexChanged.connect(self._language_changed)
        language_form.addRow(self.language)
        self.language_form = language_form
        root.addWidget(self.language_group)

        self.note = QLabel()
        self.note.setWordWrap(True)
        root.addWidget(self.note)
        root.addStretch(1)

    def retranslate_ui(self) -> None:
        language = UiPreferences.language()
        translations = {
            "pt-BR": ("Aparência e Idioma", "APARÊNCIA", "Tema:", "IDIOMA DA INTERFACE", "Idioma:", "O tema é aplicado imediatamente. O idioma é persistente e a interface já preparada para tradução é atualizada sem alterar os dados do usuário."),
            "en": ("Appearance & Language", "APPEARANCE", "Theme:", "INTERFACE LANGUAGE", "Language:", "The theme is applied immediately. The language is persistent and translated screens update without changing user data."),
            "es": ("Apariencia e Idioma", "APARIENCIA", "Tema:", "IDIOMA DE LA INTERFAZ", "Idioma:", "El tema se aplica inmediatamente. El idioma es persistente y las pantallas traducidas se actualizan sin cambiar los datos del usuario."),
        }
        title, appearance, theme_label, language_group, language_label, note = translations.get(language, translations["pt-BR"])
        self.title.setText(title)
        self.appearance.setTitle(appearance)
        self.theme_form.setWidget(0, QFormLayout.LabelRole, QLabel(theme_label, self.appearance))
        self.theme_form.labelForField(self.theme)
        self.language_group.setTitle(language_group)
        self.language_form.setWidget(0, QFormLayout.LabelRole, QLabel(language_label, self.language_group))
        self.note.setText(note)

    def _theme_changed(self, *_args) -> None:
        if self._building:
            return
        value = str(self.theme.currentData())
        UiPreferences.set_theme(value)
        app = QApplication.instance()
        if app is not None:
            apply_user_theme(app, value)
        self.changed.emit()

    def _language_changed(self, *_args) -> None:
        if self._building:
            return
        value = str(self.language.currentData())
        UiPreferences.set_language(value)
        self.retranslate_ui()
        self.language_changed.emit(value)
        self.changed.emit()


__all__ = ["AppearanceLanguagePage"]
