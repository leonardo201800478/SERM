"""Aplicador de traduções reversíveis para a árvore Qt."""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractButton, QComboBox, QGroupBox, QLabel, QTabWidget, QWidget

from .ui_preferences import UiPreferences
from .ui_translation import TEXTS


_SOURCE_PROPERTY = "serm_translation_source"


def _translated(source: str, language: str) -> str:
    return TEXTS.get(language, TEXTS["pt-BR"]).get(source, source)


def retranslate_widget_tree(root: QWidget, language: str | None = None) -> int:
    """Traduz widgets e mantém o texto original para futuras trocas de idioma."""
    lang = language or UiPreferences.language()
    changed = 0
    for widget in root.findChildren(QWidget):
        if isinstance(widget, QLabel):
            source = widget.property(_SOURCE_PROPERTY) or widget.text()
            if widget.property(_SOURCE_PROPERTY) is None:
                widget.setProperty(_SOURCE_PROPERTY, source)
            value = _translated(str(source), lang)
            if widget.text() != value:
                widget.setText(value)
                changed += 1
        elif isinstance(widget, QGroupBox):
            source = widget.property(_SOURCE_PROPERTY) or widget.title()
            if widget.property(_SOURCE_PROPERTY) is None:
                widget.setProperty(_SOURCE_PROPERTY, source)
            value = _translated(str(source), lang)
            if widget.title() != value:
                widget.setTitle(value)
                changed += 1
        elif isinstance(widget, QAbstractButton):
            source = widget.property(_SOURCE_PROPERTY) or widget.text()
            if widget.property(_SOURCE_PROPERTY) is None:
                widget.setProperty(_SOURCE_PROPERTY, source)
            value = _translated(str(source), lang)
            if widget.text() != value:
                widget.setText(value)
                changed += 1
        elif isinstance(widget, QComboBox):
            sources = widget.property(_SOURCE_PROPERTY)
            if not isinstance(sources, list) or len(sources) != widget.count():
                sources = [widget.itemText(index) for index in range(widget.count())]
                widget.setProperty(_SOURCE_PROPERTY, sources)
            for index, source in enumerate(sources):
                value = _translated(str(source), lang)
                if widget.itemText(index) != value:
                    widget.setItemText(index, value)
                    changed += 1
        elif isinstance(widget, QTabWidget):
            sources = widget.property(_SOURCE_PROPERTY)
            if not isinstance(sources, list) or len(sources) != widget.count():
                sources = [widget.tabText(index) for index in range(widget.count())]
                widget.setProperty(_SOURCE_PROPERTY, sources)
            for index, source in enumerate(sources):
                value = _translated(str(source), lang)
                if widget.tabText(index) != value:
                    widget.setTabText(index, value)
                    changed += 1
    return changed


__all__ = ["retranslate_widget_tree"]
