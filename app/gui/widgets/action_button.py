"""Botão de ação padronizado; evita botões ocupando toda a largura."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QWidget

from app.gui.design.dimensions import BUTTON_HEIGHT, MIN_BUTTON_WIDTH


class ActionButton(QPushButton):
    """Botão compacto com tooltip explicativo e tamanho previsível."""

    def __init__(self, text: str, tooltip: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setMinimumWidth(MIN_BUTTON_WIDTH)
        self.setMinimumHeight(BUTTON_HEIGHT)
        self.setMaximumWidth(220)
        if tooltip:
            self.setToolTip(tooltip)
