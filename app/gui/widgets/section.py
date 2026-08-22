"""Seção visual reutilizável para todas as abas."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from app.gui.design.dimensions import CONTROL_SPACING


class Section(QFrame):
    """Agrupa controles relacionados com título e descrição opcional."""

    def __init__(self, title: str, description: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("section")
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(CONTROL_SPACING)

        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)

        if description:
            description_label = QLabel(description)
            description_label.setObjectName("sectionDescription")
            description_label.setWordWrap(True)
            description_label.setStyleSheet("color: #9aa7b5;")
            layout.addWidget(description_label)

        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(CONTROL_SPACING)
        layout.addLayout(self.content_layout)

    def add_widget(self, widget: QWidget) -> QWidget:
        """Adiciona um controle à área de conteúdo e o devolve para composição."""
        self.content_layout.addWidget(widget)
        return widget

    def add_layout(self, layout) -> None:
        """Adiciona um layout à área de conteúdo."""
        self.content_layout.addLayout(layout)
