"""Edit ares paths stored in settings.bml."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from ..runtime.paths import data_root
from .directories_guide_page import ConfigFileEditor


class AresDirectoriesPage(QWidget):
    PATHS_FILE = data_root() / "emulator_paths.json"
    PATHS = (
        ("Paths.Home", "Home / Systems"),
        ("Paths.Firmware", "Firmware"),
        ("Paths.Saves", "Saves"),
        ("Paths.Screenshots", "Screenshots"),
        ("Paths.Debugging", "Debugging files"),
        ("Paths.ArcadeRoms", "Arcade ROMs"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        form = QFormLayout(self)
        self.fields: dict[str, QLineEdit] = {}
        for key, label in self.PATHS:
            field = QLineEdit()
            field.setReadOnly(True)
            choose = QPushButton("Selecionar pasta")
            choose.clicked.connect(lambda _=False, k=key: self.choose(k))
            reset = QPushButton("Padrão")
            reset.clicked.connect(lambda _=False, k=key: self.reset(k))
            row = QHBoxLayout()
            row.addWidget(field, 1)
            row.addWidget(choose)
            row.addWidget(reset)
            form.addRow(label, row)
            self.fields[key] = field
        self.status = QLabel()
        form.addRow("Estado", self.status)
        self.refresh()

    @classmethod
    def editor(cls) -> ConfigFileEditor | None:
        try:
            paths = json.loads(cls.PATHS_FILE.read_text(encoding="utf-8"))
            raw = paths.get("ares_config") if isinstance(paths, dict) else None
            path = Path(raw).expanduser() if raw else None
            return ConfigFileEditor(path) if path and path.is_file() else None
        except (OSError, ValueError, TypeError):
            return None

    def refresh(self) -> None:
        editor = self.editor()
        self.status.setText(f"Arquivo: {editor.path}" if editor else "settings.bml não configurado")
        for key, field in self.fields.items():
            values = editor.values(key) if editor else []
            field.setText(values[0].strip('"') if values else "")
            field.setEnabled(bool(values))

    def choose(self, key: str) -> None:
        current = self.fields[key].text()
        selected = QFileDialog.getExistingDirectory(
            self, "Selecionar diretório", current or str(Path.home())
        )
        if not selected:
            return
        self._write(key, str(Path(selected).resolve()))

    def reset(self, key: str) -> None:
        self._write(key, "")

    def _write(self, key: str, value: str) -> None:
        editor = self.editor()
        if editor is None or not editor.values(key):
            QMessageBox.warning(self, "ares", "A chave não existe no settings.bml atual.")
            return
        try:
            editor.set_value(key, value)
            backup = editor.save()
        except (OSError, KeyError, ValueError) as exc:
            QMessageBox.critical(self, "ares", f"Falha ao salvar o caminho.\n\n{exc}")
            return
        self.refresh()
        QMessageBox.information(self, "ares", f"Caminho salvo. Backup:\n{backup}")
