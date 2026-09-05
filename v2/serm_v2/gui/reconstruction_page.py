"""Guia reservada para a reconstrução do SET após o scan."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ReconstructionPage(QWidget):
    """Superfície separada para o planejador de reconstrução."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("SERM V2 — Reconstrução")
        title.setProperty("role", "title")
        layout.addWidget(title)
        description = QLabel(
            "A reconstrução é uma etapa posterior ao scan. Esta guia receberá o planejador "
            "de ações para restaurar ROMs, arquivos compartilhados, archives e CHDs sem "
            "misturar sua lógica com o filtro ou com a verificação física."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        status = QLabel("Estado: arquitetura reservada; o planner será conectado ao resultado persistido do scan.")
        status.setWordWrap(True)
        layout.addWidget(status)
        layout.addStretch()


__all__ = ["ReconstructionPage"]
