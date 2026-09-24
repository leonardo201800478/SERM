"""Directory settings kept in WinUAE's [WinUAE] INI section."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root
from .winuae_config import WinUAEConfigEditor


class WinUAEDirectoriesPage(QWidget):
    PATHS_FILE = data_root() / "emulator_paths.json"
    OPTIONS = (
        ("ConfigurationPath", "Configurações", "dir"),
        ("FloppyPath", "Disquetes / imagens WHDLoad", "dir"),
        ("hdfPath", "Discos rígidos", "dir"),
        ("InputPath", "Gravações de entrada", "dir"),
        ("KickstartPath", "Kickstart / ROMs", "dir"),
        ("LuaPath", "Scripts Lua", "dir"),
        ("RipperPath", "Ripper", "dir"),
        ("SaveimagePath", "Imagens de salvamento", "dir"),
        ("ScreenshotPath", "Capturas de tela", "dir"),
        ("StatefilePath", "Estados salvos", "dir"),
        ("VideoPath", "Vídeos", "dir"),
        ("ConfigFileFolder", "Pasta de configurações", "dir"),
        ("ConfigFileHardwareFolder", "Configurações de hardware", "dir"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fields = {}
        root = QVBoxLayout(self)
        group = QGroupBox("Diretórios definidos em winuae.ini")
        form = QFormLayout(group)
        for key, label, _kind in self.OPTIONS:
            edit = QLineEdit()
            edit.setEnabled(False)
            button = QPushButton("Selecionar pasta")
            button.clicked.connect(lambda _=False, k=key: self._browse(k))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(button)
            form.addRow(label, row)
            self.fields[key] = edit
        self.status = QLabel()
        self.status.setWordWrap(True)
        form.addRow("winuae.ini:", self.status)
        self.cache_status = QLabel()
        self.cache_status.setWordWrap(True)
        form.addRow("Cache (somente referência):", self.cache_status)
        choose_cache = QPushButton("Selecionar configuration.cache")
        choose_cache.clicked.connect(self._select_cache)
        form.addRow("Referência do cache:", choose_cache)
        root.addWidget(group)
        note = QLabel(
            "Os caminhos são alterados apenas na seção [WinUAE]. configuration.cache é um índice gerado pelo WinUAE e não é editado pelo SERM."
        )
        note.setWordWrap(True)
        root.addWidget(note)
        button = QPushButton("Aplicar diretórios")
        button.clicked.connect(self.save)
        root.addWidget(button)
        root.addStretch(1)
        self.refresh()

    @classmethod
    def _paths(cls):
        try:
            obj = json.loads(cls.PATHS_FILE.read_text(encoding="utf-8"))
            return obj if isinstance(obj, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _path(self, paths):
        raw = paths.get("winuae_ini")
        root = Path(str(paths.get("winuae", ""))) if paths.get("winuae") else None
        candidates = ([Path(str(raw))] if raw else []) + ([root / "winuae.ini"] if root else [])
        return next((p for p in candidates if p.is_file()), None)

    def _editor(self):
        path = self._path(self._paths())
        try:
            return WinUAEConfigEditor(path) if path else None
        except (OSError, UnicodeError):
            return None

    def refresh(self):
        paths = self._paths()
        editor = self._editor()
        self.status.setText(
            str(editor.path) if editor else "winuae.ini não configurado / não encontrado"
        )
        cache = paths.get("winuae_cache")
        if not cache and paths.get("winuae"):
            candidate = Path(str(paths["winuae"])) / "configuration.cache"
            cache = str(candidate) if candidate.is_file() else ""
        self.cache_status.setText(str(cache) if cache else "Não localizado")
        for key, field in self.fields.items():
            values = editor.values(key) if editor else []
            field.setEnabled(bool(values))
            field.setText(values[0] if values else "")

    def _browse(self, key):
        current = self.fields[key].text()
        path = QFileDialog.getExistingDirectory(
            self, "Selecionar diretório", current or str(Path.home())
        )
        if path:
            self.fields[key].setText(str(Path(path).resolve()))

    def _select_cache(self):
        current = self._paths().get("winuae_cache")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar cache do WinUAE",
            str(Path(str(current)).parent) if current else str(Path.home()),
            "Cache (configuration.cache);;Todos os arquivos (*)",
        )
        if not path:
            return
        cache = Path(path)
        if cache.name.casefold() != "configuration.cache":
            QMessageBox.warning(self, "WinUAE", "Selecione configuration.cache.")
            return
        data = self._paths()
        data["winuae_cache"] = str(cache.resolve())
        self.PATHS_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.PATHS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        self.refresh()

    def save(self):
        editor = self._editor()
        if not editor:
            QMessageBox.warning(self, "WinUAE", "Configure winuae.ini em 01-Diretórios.")
            return
        changed = 0
        try:
            for key, field in self.fields.items():
                old = editor.values(key)
                if old and field.isEnabled() and field.text().strip() != old[0]:
                    editor.set_value(key, field.text().strip())
                    changed += 1
            if not changed:
                QMessageBox.information(self, "WinUAE", "Nenhuma alteração pendente.")
                return
            backup = editor.save()
        except (OSError, KeyError, ValueError) as exc:
            QMessageBox.critical(self, "WinUAE", f"Falha ao aplicar diretórios.\n\n{exc}")
            return
        self.refresh()
        QMessageBox.information(
            self, "WinUAE", f"{changed} caminho(s) atualizados.\nBackup:\n{backup}"
        )
