"""Rodapé comum das abas."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app.gui.design.colors import Colors


class TabFooter(QWidget):
    """Exibe estado, contagem e mensagem operacional de forma consistente."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        self.status = QLabel("Pronto")
        self.details = QLabel("")
        self.details.setStyleSheet(f"color: {Colors.MUTED};")
        layout.addWidget(self.status)
        layout.addStretch()
        layout.addWidget(self.details)

    def set_status(self, text: str, state: str = "info") -> None:
        """Define texto e cor semântica do estado da aba."""
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {Colors.state(state)}; font-weight: 600;")

    def set_details(self, text: str) -> None:
        """Atualiza a informação secundária do rodapé."""
        self.details.setText(text)
