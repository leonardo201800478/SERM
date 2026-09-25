"""Editor for ares virtual gamepad mappings stored in settings.bml."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root
from .directories_guide_page import ConfigFileEditor


class AresControlsPage(QWidget):
    """Edit the five virtual gamepads without changing absent BML entries."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    INPUTS = (
        "Pad Up",
        "Pad Down",
        "Pad Left",
        "Pad Right",
        "Select",
        "Start",
        "A (South)",
        "B (East)",
        "X (West)",
        "Y (North)",
        "L-Bumper",
        "R-Bumper",
        "L-Trigger",
        "R-Trigger",
        "L-Stick (Click)",
        "R-Stick (Click)",
        "L-Up",
        "L-Down",
        "L-Left",
        "L-Right",
        "R-Up",
        "R-Down",
        "R-Left",
        "R-Right",
        "Rumble",
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        note = QLabel(
            "Mapeamentos dos Virtual Gamepads do ares. Cada célula corresponde a uma atribuição; "
            "mantenha vazio para limpar. Use a sintaxe de dispositivo que o ares grava no settings.bml."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.pad_selector = QComboBox()
        for pad in range(1, 6):
            self.pad_selector.addItem(f"Virtual Gamepad {pad}", pad)
        self.pad_selector.currentIndexChanged.connect(self.refresh)
        layout.addWidget(self.pad_selector)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(("Entrada", "Mapping #1", "Mapping #2", "Mapping #3"))
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout()
        self.status = QLabel()
        actions.addWidget(self.status, 1)
        reload_button = QPushButton("Recarregar")
        reload_button.clicked.connect(self.refresh)
        save_button = QPushButton("Salvar mapeamentos")
        save_button.setProperty("role", "primary")
        save_button.clicked.connect(self.save)
        actions.addWidget(reload_button)
        actions.addWidget(save_button)
        layout.addLayout(actions)
        self.refresh()

    @classmethod
    def _editor(cls) -> ConfigFileEditor | None:
        import json

        try:
            paths = json.loads(cls.PATHS_FILE.read_text(encoding="utf-8"))
            config = paths.get("ares_config") if isinstance(paths, dict) else None
            path = Path(config).expanduser() if config else None
            return ConfigFileEditor(path) if path and path.is_file() else None
        except (OSError, ValueError, TypeError):
            return None

    @staticmethod
    def _key(pad: int, name: str) -> str:
        field = name.replace(" ", ".").replace("(", ".").replace(")", "")
        return f"VirtualPad{pad}.{field}"

    def refresh(self) -> None:
        editor = self._editor()
        self.table.setRowCount(0)
        if editor is None:
            self.status.setText("Configure o settings.bml em Diretórios.")
            return
        pad = int(self.pad_selector.currentData())
        available = [(name, self._key(pad, name)) for name in self.INPUTS]
        available = [(name, key) for name, key in available if editor.values(key)]
        for name, key in available:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(name))
            raw = editor.values(key)[0]
            assignments = raw.split(";") if raw else []
            for column in range(1, 4):
                value = assignments[column - 1] if len(assignments) >= column else ""
                self.table.setItem(row, column, QTableWidgetItem(value))
                self.table.item(row, column).setData(256, key)
        self.status.setText(f"Virtual Gamepad {pad} · {len(available)} entradas encontradas")

    def save(self) -> None:
        editor = self._editor()
        if editor is None:
            QMessageBox.warning(self, "ares", "Configure o settings.bml em Diretórios primeiro.")
            return
        changed = 0
        try:
            for row in range(self.table.rowCount()):
                key = self.table.item(row, 1).data(256)
                values = [self.table.item(row, column).text().strip() for column in range(1, 4)]
                current = editor.values(key)
                if not current:
                    continue
                joined = ";".join(values).rstrip(";")
                if joined != current[0]:
                    editor.set_value(key, joined)
                    changed += 1
            if not changed:
                QMessageBox.information(self, "ares", "Nenhuma alteração pendente.")
                return
            backup = editor.save()
        except (OSError, KeyError, ValueError) as exc:
            QMessageBox.critical(self, "Falha ao salvar", str(exc))
            return
        self.refresh()
        QMessageBox.information(
            self, "ares", f"{changed} mapeamento(s) salvo(s).\nBackup:\n{backup}"
        )
