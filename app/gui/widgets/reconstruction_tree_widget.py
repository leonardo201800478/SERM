"""Widget reutilizável para a árvore da aba Reconstrução de ROMs."""
from __future__ import annotations

from typing import Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QLineEdit, QMenu, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget


class ReconstructionTreeWidget(QWidget):
    """Árvore de machines/ROMs com menu contextual centralizado no widget."""
    repair_requested = Signal(dict)
    copy_requested = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filtrar:"))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Machine, jogo ou ROM...")
        self.filter_edit.textChanged.connect(self._filter)
        filter_layout.addWidget(self.filter_edit)
        layout.addLayout(filter_layout)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["Machine / ROM", "Jogo", "Tamanho", "CRC / SHA1", "Estado"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.tree)

    def clear(self) -> None:
        """Remove todos os itens da árvore."""
        self.tree.clear()

    def set_data(self, machines: list[Any]) -> None:
        """Popula a árvore com todas as ROMs do manifesto físico."""
        self.tree.clear()
        for machine in machines:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, f"📁 {machine.name}")
            item.setText(1, machine.description)
            item.setText(4, self._machine_state(machine))
            item.setData(0, Qt.ItemDataRole.UserRole, {"kind": "machine", "machine": machine})
            for rom in machine.roms:
                child = QTreeWidgetItem(item)
                child.setText(0, f"  ├─ {rom.rom_name}")
                child.setText(2, self._size(rom.expected_size))
                child.setText(3, rom.expected_crc or rom.expected_sha1 or "-")
                child.setText(4, self._rom_state(rom))
                child.setData(0, Qt.ItemDataRole.UserRole, {"kind": "rom", "machine": machine, "rom": rom})
            item.setExpanded(False)

    @staticmethod
    def _size(value: int) -> str:
        """Formata bytes para leitura humana."""
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(value or 0)
        unit = 0
        while size >= 1024 and unit < len(units) - 1:
            size /= 1024
            unit += 1
        return f"{size:.1f} {units[unit]}"

    @staticmethod
    def _rom_state(rom: Any) -> str:
        """Converte o status físico do manifesto em estado visual."""
        state = str(getattr(rom, "status", "missing")).lower()
        return {"valid": "OK", "ok": "OK", "good": "OK", "missing": "AUSENTE", "invalid": "REPARÁVEL", "corrupted": "REPARÁVEL"}.get(state, state.upper())

    @classmethod
    def _machine_state(cls, machine: Any) -> str:
        """Calcula o estado usando TODAS as ROMs, inclusive optional do schema v2."""
        roms = list(getattr(machine, "roms", []) or [])
        if not roms:
            return "SEM ROMS"
        states = {cls._rom_state(r) for r in roms}
        if states == {"OK"}:
            return "COMPLETA"
        if "AUSENTE" in states:
            return "INCOMPLETA"
        return "REPARÁVEL"

    def _filter(self, text: str) -> None:
        """Filtra machines pela identificação ou descrição."""
        needle = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            data = item.data(0, Qt.ItemDataRole.UserRole) or {}
            machine = data.get("machine")
            if not machine:
                item.setHidden(True)
                continue
            match = not needle or needle in machine.name.lower() or needle in machine.description.lower()
            item.setHidden(not match)

    def _context_menu(self, position) -> None:
        """Centraliza as ações contextuais de ROM e machine."""
        item = self.tree.itemAt(position)
        if item is None:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole) or {}
        menu = QMenu(self)
        if data.get("kind") == "rom":
            rom = data["rom"]
            copy_action = menu.addAction("Copiar nome da ROM")
            repair_action = menu.addAction("Tentar reparar esta ROM")
            menu.addSeparator()
            info_action = menu.addAction("Ver detalhes")
            chosen = menu.exec(self.tree.viewport().mapToGlobal(position))
            if chosen == copy_action:
                QApplication.clipboard().setText(rom.rom_name)
                self.copy_requested.emit(data)
            elif chosen == repair_action:
                self.repair_requested.emit(data)
            elif chosen == info_action:
                self.repair_requested.emit({**data, "action": "details"})
        elif data.get("kind") == "machine":
            reconstruct_action = menu.addAction("Reconstruir machine")
            chosen = menu.exec(self.tree.viewport().mapToGlobal(position))
            if chosen == reconstruct_action:
                self.repair_requested.emit({**data, "action": "machine_reconstruct"})
