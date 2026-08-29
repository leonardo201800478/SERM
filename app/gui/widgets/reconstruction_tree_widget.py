"""Widget reutilizável para a árvore da aba Reconstrução de ROMs."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ReconstructionTreeWidget(QWidget):
    """Árvore de machines/ROMs com diagnóstico físico detalhado."""
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
        """Popula a árvore e registra diagnóstico no tooltip de cada ROM."""
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
                child.setToolTip(0, self._rom_reason(rom))
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

    @staticmethod
    def _rom_reason(rom: Any) -> str:
        """Explica exatamente por que a ROM foi aceita ou rejeitada fisicamente."""
        state = str(getattr(rom, "status", "missing")).lower()
        expected_size = int(getattr(rom, "expected_size", 0) or 0)
        actual_size = int(getattr(rom, "actual_size", 0) or 0)
        expected_crc = str(getattr(rom, "expected_crc", "") or "").lower()
        actual_crc = str(getattr(rom, "actual_crc", "") or "").lower()
        expected_sha1 = str(getattr(rom, "expected_sha1", "") or "").lower()
        actual_sha1 = str(getattr(rom, "actual_sha1", "") or "").lower()
        optional = bool(getattr(rom, "optional", False))

        if state in {"valid", "ok", "good"}:
            return "ROM aceita: tamanho/CRC/SHA-1 disponíveis correspondem ao esperado."
        if state == "missing":
            return "ROM ausente. " + ("É opcional e não bloqueia a execução mínima." if optional else "É obrigatória e pode impedir a execução da machine.")
        if state in {"invalid", "corrupted", "sha1_mismatch"}:
            reasons: list[str] = []
            if expected_size > 0 and actual_size != expected_size:
                reasons.append(f"tamanho esperado={expected_size}, encontrado={actual_size}")
            if expected_crc and actual_crc and expected_crc != actual_crc:
                reasons.append(f"CRC esperado={expected_crc}, encontrado={actual_crc}")
            if expected_sha1 and actual_sha1 and expected_sha1 != actual_sha1:
                reasons.append("SHA-1 divergente")
            if not reasons:
                reasons.append("arquivo não corresponde aos identificadores do LISTXML")
            return "ROM invalidada: " + "; ".join(reasons) + "."
        error = getattr(rom, "error", None)
        if error:
            return f"ROM não validada por erro: {error}"
        return f"Estado físico: {state}"

    @classmethod
    def _machine_state(cls, machine: Any) -> str:
        """Calcula o estado usando todas as ROMs, inclusive optional."""
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
