"""Widget de árvore de resultados do Scan Roms.

Responsabilidades:
    * exibir machines e suas ROMs/CHDs em árvore;
    * mostrar origem física, tamanho, CRC/SHA1 e status;
    * popular a árvore em lotes, sem travar a GUI, para scans grandes;
    * menu contextual de reparo sobre ROMs com problema.

Este widget não decide COMO reparar uma ROM — não conhece RomScanner,
outros sets nem o filesystem além do necessário para exibição. Ele
apenas identifica o item selecionado e emite ``repair_requested`` com
os dados da ROM/máquina, deixando a ação real para quem orquestra o
scan (``ScanRomsTab``).
"""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QTreeWidget, QTreeWidgetItem


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

# ROMs nesses status são candidatas a reparo; ROMs válidas não exibem o menu.
_REPAIRABLE_STATUSES = {"missing", "invalid", "bad", "error"}


def value_of(obj: Any, name: str, default: Any = None) -> Any:
    """Lê um atributo de objeto ou uma chave de dicionário, com fallback.

    Permite que o widget trate uniformemente tanto os dataclasses do
    RomScanner (``MachineScanResult``/``RomScanResult``) quanto os
    dicionários lidos diretamente de um LISTXML filtrado em disco.
    """
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


class RomTreeWidget(QTreeWidget):
    """Árvore de máquinas/ROMs com origem física, hash, status e reparo."""

    # Emitido quando o usuário escolhe "Tentar reparar" no menu contextual.
    # payload: {"kind": "rom", "machine": <machine>, "rom": <rom>}
    repair_requested = Signal(dict)

    # Emitido ao concluir populate_async(); argumento = segundos decorridos.
    population_finished = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setColumnCount(5)
        self.setHeaderLabels([
            "ROM / Máquina",
            "Descrição / Caminho",
            "Tamanho",
            "CRC / SHA1",
            "Status",
        ])
        self.setAlternatingRowColors(True)
        self.setUniformRowHeights(True)
        self.itemDoubleClicked.connect(self._on_double_click)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

        self._machine_results: list[Any] = []
        self._populate_index = 0
        self._populate_batch_size = 50
        self._populating = False

    # ========================================================================
    # POPULAÇÃO EM LOTE
    # ========================================================================

    def populate_async(
        self,
        machine_results: list[Any],
        *,
        batch_size: int = 50,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """Popula a árvore em lotes, sem travar a GUI.

        Emite ``population_finished(elapsed_seconds)`` ao concluir,
        inclusive quando ``machine_results`` está vazio.
        """
        print(f"[DEBUG] populate_async chamado com {len(machine_results)} máquinas")
        start_time = time.monotonic()

        self._populating = True
        self.clear()
        self.setUpdatesEnabled(False)

        self._machine_results = machine_results
        self._populate_index = 0
        self._populate_batch_size = max(1, batch_size)

        total = len(machine_results)

        if total == 0:
            self.setUpdatesEnabled(True)
            self._populating = False
            self.population_finished.emit(0.0)
            return

        def process_batch() -> None:
            print(f"[DEBUG] process_batch: índice {self._populate_index}/{total}")
            if self._populate_index >= total:
                self.setUpdatesEnabled(True)
                elapsed = time.monotonic() - start_time
                self._populating = False
                if self.topLevelItemCount() > 0:
                    self.topLevelItem(0).setExpanded(True)
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

    @property
    def populating(self) -> bool:
        return self._populating

    # ========================================================================
    # CONSTRUÇÃO DOS ITENS
    # ========================================================================

    def _add_machine(self, machine: Any) -> None:
        name = str(value_of(machine, "machine_name", ""))
        status = self._machine_status(machine)

        item = QTreeWidgetItem(self)
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

    # ========================================================================
    # INTERAÇÃO
    # ========================================================================

    def _on_double_click(self, item: QTreeWidgetItem, column: int) -> None:
        details = [
            f"Item: {item.text(0)}",
            f"Descrição/caminho: {item.text(1)}",
            f"Tamanho: {item.text(2)}",
            f"CRC/SHA1: {item.text(3)}",
            f"Status: {item.text(4)}",
        ]
        QMessageBox.information(self, "Detalhes do item", "\n".join(details))

    def _on_context_menu(self, position) -> None:
        item = self.itemAt(position)
        if item is None:
            return

        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if data.get("kind") != "rom":
            return  # reparo só se aplica a itens de ROM/CHD, não a machines

        rom = data.get("rom")
        status = str(value_of(rom, "status", "")).lower()

        menu = QMenu(self)
        action_copy = menu.addAction("Copiar nome da ROM")
        action_repair = None
        if status in _REPAIRABLE_STATUSES:
            action_repair = menu.addAction("Tentar reparar esta ROM...")

        chosen = menu.exec(self.viewport().mapToGlobal(position))
        if chosen is None:
            return

        if chosen == action_copy:
            QApplication.clipboard().setText(str(value_of(rom, "rom_name", "")))
        elif action_repair is not None and chosen == action_repair:
            self.repair_requested.emit(data)
