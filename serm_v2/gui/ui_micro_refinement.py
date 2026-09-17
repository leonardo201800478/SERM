"""Microajustes visuais que não alteram a composição funcional da GUI."""

from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTableWidget, QWidget


def refine_arcade_catalog_numbers(studio: QWidget) -> bool:
    """Reduz somente a tipografia dos números do cabeçalho vertical do catálogo."""
    table = getattr(studio, "catalog_table", None)
    if not isinstance(table, QTableWidget):
        return False

    font = QFont(table.verticalHeader().font())
    font.setPointSizeF(7.5)
    table.verticalHeader().setFont(font)
    table.verticalHeader().setMinimumWidth(34)
    table.verticalHeader().setDefaultAlignment(
        table.verticalHeader().defaultAlignment()
    )
    return True


__all__ = ["refine_arcade_catalog_numbers"]
