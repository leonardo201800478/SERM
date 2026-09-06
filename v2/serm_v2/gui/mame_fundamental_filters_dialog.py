"""Janela popup dos filtros fundamentais do MAME."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..services.mame_fundamental_filter_service import (
    DEFAULT_FILTERS,
    FILTER_DEFINITIONS,
)


class MameFundamentalFiltersDialog(QDialog):
    """Editor modal compacto para as exclusões fundamentais da V1."""

    def __init__(self, values: dict[str, bool] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("MAME — Filtros fundamentais")
        self.setModal(True)
        self.setMinimumWidth(560)
        self._checks: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        title = QLabel("Filtros fundamentais do MAME")
        title.setProperty("role", "title")
        layout.addWidget(title)
        description = QLabel(
            "Estas exclusões reproduzem a finalidade dos filtros essenciais da V1. "
            "Elas retiram máquinas do conjunto selecionado; não alteram nem descartam "
            "o ListXML original. A configuração fica vinculada ao profile_id."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        current = {key: bool((values or {}).get(key, default)) for key, default in DEFAULT_FILTERS.items()}
        for key, definition in FILTER_DEFINITIONS.items():
            check = QCheckBox(str(definition["label"]))
            check.setChecked(current[key])
            check.setToolTip(str(definition["description"]))
            self._checks[key] = check
            layout.addWidget(check)

        note = QLabel(
            "Mecânicas/eletromecânicas e Fruit Machines incluem classificações derivadas "
            "quando o CATLIST as fornece. Categorias não classificadas não são removidas."
        )
        note.setWordWrap(True)
        note.setProperty("role", "subtitle")
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict[str, bool]:
        return {key: check.isChecked() for key, check in self._checks.items()}


__all__ = ["MameFundamentalFiltersDialog"]
