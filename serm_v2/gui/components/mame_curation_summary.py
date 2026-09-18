"""Painel lateral de resumo da curadoria MAME."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout


class MameCurationSummary(QFrame):
    """Resumo compacto e visual dos resultados da curadoria."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("mameCurationSummary")
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(7)
        self.title = QLabel("🛡 Curadoria")
        self.title.setObjectName("summaryTitle")
        root.addWidget(self.title)
        self.total = QLabel("Total de máquinas\n—")
        self.selected = QLabel("Selecionadas\n—")
        self.excluded = QLabel("Excluídas\n—")
        for widget in (self.total, self.selected, self.excluded):
            widget.setObjectName("summaryMetric")
            root.addWidget(widget)
        self.selected_bar = QProgressBar()
        self.selected_bar.setRange(0, 100)
        self.selected_bar.setTextVisible(False)
        self.selected_bar.setFixedHeight(5)
        root.addWidget(self.selected_bar)
        self.excluded_bar = QProgressBar()
        self.excluded_bar.setRange(0, 100)
        self.excluded_bar.setTextVisible(False)
        self.excluded_bar.setFixedHeight(5)
        root.addWidget(self.excluded_bar)
        criteria_title = QLabel("Principais critérios aplicados")
        criteria_title.setObjectName("summarySection")
        root.addWidget(criteria_title)
        self.criteria = QLabel("Nenhum critério aplicado.")
        self.criteria.setObjectName("summaryCriteria")
        self.criteria.setWordWrap(True)
        root.addWidget(self.criteria)
        excluded_title = QLabel("Últimas exclusões")
        excluded_title.setObjectName("summarySection")
        root.addWidget(excluded_title)
        self.last_exclusions = QLabel("Nenhuma exclusão registrada.")
        self.last_exclusions.setObjectName("summaryCriteria")
        self.last_exclusions.setWordWrap(True)
        root.addWidget(self.last_exclusions)
        root.addStretch(1)

    def update_counts(self, total: int, selected: int, excluded: int, criteria=None, exclusions=None) -> None:
        total = max(0, int(total))
        selected = max(0, int(selected))
        excluded = max(0, int(excluded))
        self.total.setText(f"Total de máquinas\n{total:,}".replace(",", "."))
        selected_pct = (selected / total * 100) if total else 0
        excluded_pct = (excluded / total * 100) if total else 0
        self.selected.setText(f"Selecionadas  {selected:,} ({selected_pct:.1f}%)".replace(",", "."))
        self.excluded.setText(f"Excluídas  {excluded:,} ({excluded_pct:.1f}%)".replace(",", "."))
        self.selected_bar.setValue(round(selected_pct))
        self.excluded_bar.setValue(round(excluded_pct))
        self.criteria.setText("\n".join(f"✓  {item}" for item in (criteria or [])) or "Nenhum critério aplicado.")
        self.last_exclusions.setText("\n".join(f"×  {item}" for item in (exclusions or [])) or "Nenhuma exclusão registrada.")


__all__ = ["MameCurationSummary"]
