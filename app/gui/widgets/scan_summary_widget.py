# app/gui/widgets/scan_summary_widget.py
"""Widget de resumo do Scan Roms (layout compacto)."""

from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
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
    """Progresso, contadores e status agregados do scan (layout compacto)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        group = QGroupBox("Resumo")
        grid_layout = QGridLayout()
        grid_layout.setContentsMargins(6, 6, 6, 6)
        grid_layout.setHorizontalSpacing(10)
        grid_layout.setVerticalSpacing(2)

        self.summary_labels: dict[str, QLabel] = {}

        # Distribuição em 4 colunas: (rótulo, valor) pares
        for index, (text, key) in enumerate(_SUMMARY_FIELDS):
            row = index // 4
            col = (index % 4) * 2
            title = QLabel(text + ":")
            title.setStyleSheet("font-weight: bold;")
            value = QLabel("0")
            value.setMinimumWidth(50)
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid_layout.addWidget(title, row, col)
            grid_layout.addWidget(value, row, col + 1)
            self.summary_labels[key] = value

        group.setLayout(grid_layout)
        layout.addWidget(group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Aguardando scan...")
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Pronto.")
        self.status_label.setStyleSheet("font-style: italic;")
        layout.addWidget(self.status_label)

        self.profile_label = QLabel("Perfil ativo: (nenhum)")
        self.profile_label.setStyleSheet("color: #555; font-style: italic;")
        self.profile_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.profile_label)

    # ------------------------------------------------------------------------
    # API PÚBLICA
    # ------------------------------------------------------------------------

    def set_progress(self, value: int, text: str) -> None:
        self.progress_bar.setValue(max(0, min(100, value)))
        self.progress_bar.setFormat(text)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_profile_label(self, text: str) -> None:
        self.profile_label.setText(f"Perfil ativo: {text}" if text else "Perfil ativo: (nenhum)")

    def update_counts(self, counts: Mapping[str, Any]) -> None:
        for key, label in self.summary_labels.items():
            if key in counts:
                label.setText(str(counts[key]))

    def reset(self) -> None:
        for label in self.summary_labels.values():
            label.setText("0")
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Aguardando scan...")
        self.status_label.setText("Pronto.")