"""Editor avançado de filtros MAME usando a classificação CATLIST."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services.mame_category_filter_service import MameCategoryFilterService


class MameAdvancedFiltersDialog(QDialog):
    """Seleciona categorias e subcategorias CATLIST para exclusão do set."""

    def __init__(
        self,
        values: dict[str, list[str]] | None = None,
        database=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("MAME — Filtros avançados CATLIST")
        self.setModal(True)
        self.resize(900, 650)
        self._database = database
        current = values or {"categories": [], "subcategories": []}
        self._categories = set(current.get("categories", []))
        self._subcategories = set(current.get("subcategories", []))

        root = QVBoxLayout(self)
        title = QLabel("Filtros avançados do MAME — classificação CATLIST")
        title.setProperty("role", "title")
        root.addWidget(title)
        root.addWidget(
            QLabel(
                "Selecione o que deve ser EXCLUÍDO do set. As opções abaixo vêm diretamente "
                "da tabela mame_classification, criada a partir do CATLIST. O scan bruto não é alterado."
            )
        )

        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Pesquisar categoria ou subcategoria…")
        self.search.textChanged.connect(self._filter_tree)
        tools.addWidget(self.search, 1)
        select_all = QPushButton("SELECIONAR VISÍVEIS")
        clear_all = QPushButton("LIMPAR SELEÇÃO")
        select_all.clicked.connect(self._select_visible)
        clear_all.clicked.connect(self._clear)
        tools.addWidget(select_all)
        tools.addWidget(clear_all)
        root.addLayout(tools)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Categoria / subcategoria", "Machines"])
        self.tree.setColumnWidth(0, 500)
        self.tree.itemChanged.connect(self._item_changed)
        splitter.addWidget(self.tree)

        self.selected_list = QListWidget()
        splitter.addWidget(self.selected_list)
        splitter.setSizes([620, 280])
        root.addWidget(splitter, 1)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._populate()
        self._refresh_summary()

    def _populate(self) -> None:
        rows = MameCategoryFilterService.tree(self._database)
        grouped: dict[str, list[dict[str, object]]] = {}
        for row in rows:
            grouped.setdefault(str(row["category"]), []).append(row)
        self.tree.blockSignals(True)
        self.tree.clear()
        for category, children in grouped.items():
            category_item = QTreeWidgetItem(
                [category, str(sum(int(str(c["machines"])) for c in children))]
            )
            category_item.setData(0, Qt.ItemDataRole.UserRole, ("category", category))
            category_item.setFlags(category_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            category_item.setCheckState(
                0,
                Qt.CheckState.Checked if category in self._categories else Qt.CheckState.Unchecked,
            )
            self.tree.addTopLevelItem(category_item)
            for child in children:
                sub = str(child["subcategory"])
                if not sub:
                    continue
                item = QTreeWidgetItem([sub, str(child["machines"])])
                item.setData(0, Qt.ItemDataRole.UserRole, ("subcategory", sub))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    0,
                    Qt.CheckState.Checked
                    if sub in self._subcategories
                    else Qt.CheckState.Unchecked,
                )
                category_item.addChild(item)
            category_item.setExpanded(True)
        self.tree.blockSignals(False)
        self._refresh_selected_list()

    def _item_changed(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, tuple) or len(data) != 2:
            return
        kind, value = data
        checked = item.checkState(0) == Qt.CheckState.Checked
        target = self._categories if kind == "category" else self._subcategories
        if checked:
            target.add(value)
        else:
            target.discard(value)
        self._refresh_selected_list()
        self._refresh_summary()

    def _filter_tree(self, text: str) -> None:
        needle = text.casefold().strip()
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            if parent is None:
                continue
            parent_match = needle in parent.text(0).casefold()
            visible_child = False
            for j in range(parent.childCount()):
                child = parent.child(j)
                if child is None:
                    continue
                match = parent_match or needle in child.text(0).casefold()
                child.setHidden(not match)
                visible_child |= match
            parent.setHidden(bool(needle) and not (parent_match or visible_child))

    def _select_visible(self) -> None:
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            if parent is not None and not parent.isHidden():
                self._select_visible_parent(parent)
        self.tree.blockSignals(False)
        self._refresh_selected_list()
        self._refresh_summary()

    def _select_visible_parent(self, parent: QTreeWidgetItem) -> None:
        if self.search.text().casefold() in parent.text(0).casefold():
            parent.setCheckState(0, Qt.CheckState.Checked)
            self._categories.add(str(parent.data(0, Qt.ItemDataRole.UserRole)[1]))
        for j in range(parent.childCount()):
            child = parent.child(j)
            if child is not None and not child.isHidden():
                child.setCheckState(0, Qt.CheckState.Checked)
                self._subcategories.add(str(child.data(0, Qt.ItemDataRole.UserRole)[1]))

    def _clear(self) -> None:
        self._categories.clear()
        self._subcategories.clear()
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            if parent is None:
                continue
            parent.setCheckState(0, Qt.CheckState.Unchecked)
            for j in range(parent.childCount()):
                child = parent.child(j)
                if child is not None:
                    child.setCheckState(0, Qt.CheckState.Unchecked)
        self.tree.blockSignals(False)
        self._refresh_selected_list()
        self._refresh_summary()

    def _refresh_selected_list(self) -> None:
        self.selected_list.clear()
        for value in sorted(self._categories):
            self.selected_list.addItem(QListWidgetItem(f"Categoria: {value}"))
        for value in sorted(self._subcategories):
            self.selected_list.addItem(QListWidgetItem(f"Subcategoria: {value}"))

    def _refresh_summary(self) -> None:
        self.summary.setText(
            f"Exclusões CATLIST: {len(self._categories)} categorias + {len(self._subcategories)} subcategorias. "
            "Uma machine que pertencer a qualquer seleção será excluída."
        )

    def values(self) -> dict[str, list[str]]:
        return {
            "categories": sorted(self._categories),
            "subcategories": sorted(self._subcategories),
        }


__all__ = ["MameAdvancedFiltersDialog"]
