"""Widget de árvore de resultados do Scan Roms com filtro, ordenação e detalhes."""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

STATUS_COLORS = {
    "good": "#008000",
    "valid": "#008000",
    "bad": "#CC8800",
    "invalid": "#CC8800",
    "missing": "#808080",
    "error": "#CC0000",
    "cancelled": "#808080",
}

STATUS_LABELS = {
    "good": "OK",
    "valid": "OK",
    "bad": "INVÁLIDA",
    "invalid": "INVÁLIDA",
    "missing": "AUSENTE",
    "error": "ERRO",
    "cancelled": "CANCELADA",
}

_REPAIRABLE_STATUSES = {"missing", "invalid", "bad", "error"}


def value_of(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def format_size(value: Any) -> str:
    size = as_int(value)
    if size < 1024:
        return f"{size} B"
    if size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    if size < 1024 ** 3:
        return f"{size / (1024 ** 2):.1f} MB"
    if size < 1024 ** 4:
        return f"{size / (1024 ** 3):.2f} GB"
    return f"{size / (1024 ** 4):.2f} TB"


class RomTreeWidget(QWidget):
    """Árvore de máquinas/ROMs com filtro, ordenação, detalhes e reparo."""

    repair_requested = Signal(dict)
    population_finished = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Barra de filtro
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filtrar:"))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Digite o nome da máquina...")
        self.filter_edit.textChanged.connect(self.filter_items)
        filter_layout.addWidget(self.filter_edit)
        layout.addLayout(filter_layout)

        # Árvore
        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["ROM / Máquina", "Descrição / Caminho", "Tamanho", "CRC / SHA1", "Status"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)

        layout.addWidget(self.tree)

        self._machine_results: list[Any] = []
        self._populate_index = 0
        self._populate_batch_size = 50
        self._populating = False

    # --- Redirecionamentos para a tree interna ---
    def clear(self) -> None:
        self.tree.clear()

    def topLevelItem(self, index: int) -> QTreeWidgetItem | None:
        return self.tree.topLevelItem(index)

    def topLevelItemCount(self) -> int:
        return self.tree.topLevelItemCount()

    def itemAt(self, pos) -> QTreeWidgetItem | None:
        return self.tree.itemAt(pos)

    def setContextMenuPolicy(self, policy) -> None:
        self.tree.setContextMenuPolicy(policy)

    @property
    def populating(self) -> bool:
        return self._populating

    # --- Métodos principais ---

    def populate_async(
        self,
        machine_results: list[Any],
        *,
        batch_size: int = 50,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        start_time = time.monotonic()
        self._populating = True
        self.tree.clear()
        self.tree.setUpdatesEnabled(False)
        self._machine_results = machine_results
        self._populate_index = 0
        self._populate_batch_size = max(1, batch_size)
        total = len(machine_results)

        if total == 0:
            self.tree.setUpdatesEnabled(True)
            self._populating = False
            self.population_finished.emit(0.0)
            return

        def process_batch() -> None:
            if self._populate_index >= total:
                self.tree.setUpdatesEnabled(True)
                elapsed = time.monotonic() - start_time
                self._populating = False
                if self.tree.topLevelItemCount() > 0:
                    self.tree.topLevelItem(0).setExpanded(True)
                self.population_finished.emit(elapsed)
                return

            end_idx = min(self._populate_index + self._populate_batch_size, total)
            for idx in range(self._populate_index, end_idx):
                self._add_machine(self._machine_results[idx])
            self._populate_index = end_idx

            if on_progress is not None:
                on_progress(end_idx, total)

            if self._populate_index < total:
                QTimer.singleShot(5, process_batch)
            else:
                process_batch()

        QTimer.singleShot(0, process_batch)

    def filter_items(self, text: str) -> None:
        """Filtra as máquinas pelo nome (case-insensitive)."""
        text = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if text:
                show = text in item.text(0).lower()
                item.setHidden(not show)
            else:
                item.setHidden(False)

    # --- Construção dos itens ---

    def _add_machine(self, machine: Any) -> None:
        name = str(value_of(machine, "machine_name", ""))
        status = self._machine_status(machine)

        item = QTreeWidgetItem(self.tree)
        item.setText(0, f"📁 {name}")
        item.setText(1, "")
        item.setText(2, self._format_machine_size(machine))
        item.setText(3, "-")
        item.setText(4, STATUS_LABELS.get(status, status.upper()))
        item.setData(0, Qt.ItemDataRole.UserRole, {"kind": "machine", "machine": machine})
        self._apply_status_color(item, status)

        for rom in value_of(machine, "roms", []):
            self._add_rom(item, machine, rom)

    def _add_rom(self, parent: QTreeWidgetItem, machine: Any, rom: Any) -> None:
        name = str(value_of(rom, "rom_name", ""))
        status = str(value_of(rom, "status", "")).lower()
        expected_size = as_int(value_of(rom, "expected_size", 0))
        actual_size = as_int(value_of(rom, "actual_size", 0))
        expected_crc = str(value_of(rom, "expected_crc", "") or "")
        actual_crc = str(value_of(rom, "actual_crc", "") or "")
        path = value_of(rom, "path", None)

        child = QTreeWidgetItem(parent)
        child.setText(0, f"  ├─ {name}")
        child.setText(1, str(path) if path else "")
        child.setText(2, self._format_result_size(expected_size, actual_size, status))
        hash_value = actual_crc or expected_crc or "-"
        child.setText(3, hash_value[:40])
        child.setText(4, STATUS_LABELS.get(status, status.upper() if status else "N/D"))
        child.setData(
            0,
            Qt.ItemDataRole.UserRole,
            {"kind": "rom", "machine": machine, "rom": rom},
        )
        self._apply_status_color(child, status)
        child.setToolTip(0, f"Esperado: {expected_crc or '-'}\nEncontrado: {actual_crc or '-'}")
        child.setToolTip(1, str(path) if path else "")

    @staticmethod
    def _machine_status(machine: Any) -> str:
        if as_int(value_of(machine, "error", 0)) > 0:
            return "error"
        if as_int(value_of(machine, "bad", 0)) > 0:
            return "bad"
        if as_int(value_of(machine, "missing", 0)) > 0:
            return "missing"
        if as_int(value_of(machine, "valid", 0)) > 0:
            return "good"
        return "missing"

    @staticmethod
    def _format_machine_size(machine: Any) -> str:
        total = 0
        for rom in value_of(machine, "roms", []):
            total += as_int(value_of(rom, "expected_size", 0))
        return format_size(total)

    @staticmethod
    def _format_result_size(expected: int, actual: int, status: str) -> str:
        if status == "missing":
            return format_size(expected)
        if actual > 0:
            return f"{format_size(expected)} / {format_size(actual)}"
        return format_size(expected)

    def _apply_status_color(self, item: QTreeWidgetItem, status: str) -> None:
        color = STATUS_COLORS.get(status, "#000000")
        item.setForeground(4, QColor(color))

    # --- Interação ---

    def _on_double_click(self, item: QTreeWidgetItem, column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        kind = data.get("kind")

        if kind == "machine":
            machine = data.get("machine")
            if machine:
                total = as_int(value_of(machine, "total", 0))
                valid = as_int(value_of(machine, "valid", 0))
                missing = as_int(value_of(machine, "missing", 0))
                bad = as_int(value_of(machine, "bad", 0))
                error = as_int(value_of(machine, "error", 0))
                msg = (
                    f"Máquina: {value_of(machine, 'machine_name', '')}\n"
                    f"Descrição: {value_of(machine, 'description', '')}\n"
                    f"Clone de: {value_of(machine, 'cloneof', 'N/A')}\n\n"
                    f"Total de ROMs: {total}\n"
                    f"Válidas: {valid}\n"
                    f"Ausentes: {missing}\n"
                    f"Inválidas: {bad}\n"
                    f"Erros: {error}"
                )
                QMessageBox.information(self, "Detalhes da Máquina", msg)
        else:
            # ROM item
            details = [
                f"Item: {item.text(0)}",
                f"Descrição/caminho: {item.text(1)}",
                f"Tamanho: {item.text(2)}",
                f"CRC/SHA1: {item.text(3)}",
                f"Status: {item.text(4)}",
            ]
            QMessageBox.information(self, "Detalhes do item", "\n".join(details))

    def _on_context_menu(self, position) -> None:
        item = self.tree.itemAt(position)
        if item is None:
            return

        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if data.get("kind") != "rom":
            return

        rom = data.get("rom")
        status = str(value_of(rom, "status", "")).lower()

        menu = QMenu(self)
        action_copy = menu.addAction("Copiar nome da ROM")
        action_repair = None
        if status in _REPAIRABLE_STATUSES:
            action_repair = menu.addAction("Tentar reparar esta ROM...")

        chosen = menu.exec(self.tree.viewport().mapToGlobal(position))
        if chosen is None:
            return

        if chosen == action_copy:
            QApplication.clipboard().setText(str(value_of(rom, "rom_name", "")))
        elif action_repair is not None and chosen == action_repair:
            self.repair_requested.emit(data)