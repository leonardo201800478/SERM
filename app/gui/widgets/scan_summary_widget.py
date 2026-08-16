"""Widget de resumo do Scan Roms.

Responsabilidades:
    * barra de progresso;
    * contadores agregados (máquinas, itens, encontrados, válidos,
      ausentes, inválidos, erros);
    * mensagem de status textual;
    * rótulo do perfil ativo.

Este widget é passivo: não calcula nada, apenas recebe valores já
prontos de quem orquestra o scan (``ScanRomsTab``) e os exibe.
"""

from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

_SUMMARY_FIELDS = [
    ("Máquinas", "machines"),
    ("Itens", "total"),
    ("Encontrados", "found"),
    ("Válidos", "valid"),
    ("Ausentes", "missing"),
    ("Inválidos", "bad"),
    ("Erros", "error"),
]


class ScanSummaryWidget(QWidget):
    """Progresso, contadores e status agregados do scan."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        layout.addWidget(self._build_summary_group())

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Aguardando scan...")
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Pronto.")
        layout.addWidget(self.status_label)

        self.profile_label = QLabel("Perfil ativo: (nenhum)")
        self.profile_label.setStyleSheet("color: #555; font-style: italic;")
        self.profile_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.profile_label)

    def _build_summary_group(self) -> QGroupBox:
        group = QGroupBox("Resumo")
        layout = QGridLayout(group)

        self.summary_labels: dict[str, QLabel] = {}
        for index, (text, key) in enumerate(_SUMMARY_FIELDS):
            row = index // 4
            column = (index % 4) * 2
            title = QLabel(text + ":")
            value = QLabel("0")
            value.setMinimumWidth(60)
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            layout.addWidget(title, row, column)
            layout.addWidget(value, row, column + 1)
            self.summary_labels[key] = value

        return group

    # ========================================================================
    # API PÚBLICA
    # ========================================================================

    def set_progress(self, value: int, text: str) -> None:
        self.progress_bar.setValue(max(0, min(100, value)))
        self.progress_bar.setFormat(text)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_profile_label(self, text: str) -> None:
        self.profile_label.setText(f"Perfil ativo: {text}" if text else "Perfil ativo: (nenhum)")

    def update_counts(self, counts: Mapping[str, Any]) -> None:
        """Atualiza somente as chaves presentes em ``counts``; chaves
        conhecidas ausentes permanecem com o valor atual."""
        for key, label in self.summary_labels.items():
            if key in counts:
                label.setText(str(counts[key]))

    def reset(self) -> None:
        for label in self.summary_labels.values():
            label.setText("0")
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Aguardando scan...")
        self.status_label.setText("Pronto.")
