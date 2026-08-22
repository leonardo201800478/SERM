"""Infraestrutura comum para todas as abas da aplicação."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from app.gui.design.dimensions import MARGIN, SECTION_SPACING
from app.gui.widgets.footer import TabFooter
from app.gui.widgets.progress_bar import OperationProgress


class BaseTab(QWidget):
    """Fornece estrutura comum de conteúdo, progresso e rodapé.

    Subclasses devem implementar somente os grupos específicos da funcionalidade.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(MARGIN, MARGIN, MARGIN, MARGIN)
        self.main_layout.setSpacing(SECTION_SPACING)

        # Grupo comum: área de conteúdo da aba.
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(SECTION_SPACING)
        self.main_layout.addLayout(self.content_layout, 1)

        # Grupo comum: progresso de operações longas.
        self.operation_progress = OperationProgress(self)
        self.main_layout.addWidget(self.operation_progress)

        # Grupo comum: estado e contadores da aba.
        self.footer = TabFooter(self)
        self.main_layout.addWidget(self.footer)

    def add_content(self, widget: QWidget) -> QWidget:
        """Adiciona um widget à área principal da aba."""
        self.content_layout.addWidget(widget)
        return widget

    def add_content_layout(self, layout, stretch: int = 0) -> None:
        """Adiciona um layout à área principal da aba."""
        self.content_layout.addLayout(layout, stretch)

    def set_operation_progress(self, value: int, message: str = "") -> None:
        """Atualiza o progresso comum da aba."""
        self.operation_progress.set_progress(value, message)

    def set_busy(self, message: str = "Processando...") -> None:
        """Exibe operação indeterminada sem aparentar que a aplicação travou."""
        self.operation_progress.set_busy(message)

    def set_status(self, text: str, state: str = "info", details: str = "") -> None:
        """Atualiza o estado e os detalhes do rodapé."""
        self.footer.set_status(text, state)
        self.footer.set_details(details)
