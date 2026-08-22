"""Barra de progresso padronizada para operações longas."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QProgressBar, QVBoxLayout, QWidget, QLabel


class OperationProgress(QWidget):
    """Mostra percentual, etapa atual e mensagem da operação em execução."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.message = QLabel("Pronto")
        self.message.setStyleSheet("color: #9aa7b5;")
        self.bar = QProgressBar()
        self.bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        layout.addWidget(self.message)
        layout.addWidget(self.bar)

    def set_progress(self, value: int, message: str = "") -> None:
        """Atualiza progresso e mensagem sem alterar o contrato do worker."""
        self.bar.setValue(max(0, min(100, int(value))))
        if message:
            self.message.setText(message)

    def set_busy(self, message: str = "Processando...") -> None:
        """Coloca a barra em modo indeterminado para operações sem total conhecido."""
        self.bar.setRange(0, 0)
        self.message.setText(message)

    def reset(self, message: str = "Pronto") -> None:
        """Retorna a barra ao estado determinado inicial."""
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.message.setText(message)
