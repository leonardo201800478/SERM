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

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("Aparência e Idioma")
        title.setProperty("role", "title")
        root.addWidget(title)

        appearance = QGroupBox("APARÊNCIA")
        form = QFormLayout(appearance)
        form.setContentsMargins(10, 12, 10, 10)
        self.theme = QComboBox()
        self.theme.addItem("Modo escuro", "dark")
        self.theme.addItem("Modo claro", "light")
        self.theme.setCurrentIndex(max(0, self.theme.findData(UiPreferences.theme())))
        self.theme.currentIndexChanged.connect(self._theme_changed)
        form.addRow("Tema:", self.theme)
        root.addWidget(appearance)

        language = QGroupBox("IDIOMA DA INTERFACE")
        language_form = QFormLayout(language)
        language_form.setContentsMargins(10, 12, 10, 10)
        self.language = QComboBox()
        for code, name in LANGUAGES.items():
            self.language.addItem(name, code)
        self.language.setCurrentIndex(max(0, self.language.findData(UiPreferences.language())))
        self.language.currentIndexChanged.connect(self._language_changed)
        language_form.addRow("Idioma:", self.language)
        root.addWidget(language)

        self.note = QLabel(
            "O tema é aplicado imediatamente. O idioma é persistente e a interface já preparada para tradução é atualizada sem alterar os dados do usuário."
        )
        self.note.setWordWrap(True)
        root.addWidget(self.note)
        root.addStretch(1)

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
        self.language_changed.emit(value)
        self.changed.emit()


__all__ = ["AppearanceLanguagePage"]
