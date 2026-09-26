"""Edit ares paths stored in settings.bml."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QWidget,
)

from ..runtime.paths import data_root
from .directory_dialogs import get_existing_directory
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
            choose.setToolTip(f"Seleciona o diretório para {label} no settings.bml do ares.")
            choose.clicked.connect(lambda _=False, k=key: self.choose(k))
            row = QHBoxLayout()
            row.addWidget(field, 1)
            row.addWidget(choose)
            form.addRow(label, row)
            self.fields[key] = field
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.save_button = QPushButton("Salvar configurações")
        self.save_button.setToolTip(
            "Grava os diretórios exibidos no settings.bml do ares e cria um backup do arquivo."
        )
        self.save_button.setProperty("role", "primary")
        self.save_button.clicked.connect(self.save)
        self.defaults_button = QPushButton("Restaurar padrão do ares")
        self.defaults_button.setToolTip(
            "Limpa os caminhos personalizados para o ares voltar a usar seus diretórios padrão; "
            "salva a alteração imediatamente e cria um backup."
        )
        self.defaults_button.clicked.connect(self.restore_defaults)
        actions.addWidget(self.defaults_button)
        actions.addWidget(self.save_button)
        form.addRow("", actions)
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
        selected = get_existing_directory(
            self, "Selecionar diretório", current or str(Path.home())
        )
        if not selected:
            return
        self.fields[key].setText(str(Path(selected).resolve()))
        self.status.setText("Alterações pendentes. Clique em Salvar configurações.")

    def restore_defaults(self) -> None:
        """Clear custom paths so ares resumes using its built-in paths."""
        for field in self.fields.values():
            field.clear()
        self.save()

    def save(self) -> None:
        """Persist all directory values to the selected native settings file."""
        editor = self.editor()
        if editor is None:
            QMessageBox.warning(
                self,
                "ares",
                "Selecione a pasta de instalação do ares em Diretórios para localizar o settings.bml.",
            )
            return
        missing = [key for key, _label in self.PATHS if not editor.values(key)]
        if missing:
            QMessageBox.warning(
                self,
                "ares",
                "O settings.bml não contém estas chaves de diretório: "
                + ", ".join(missing),
            )
            return
        try:
            for key, _label in self.PATHS:
                editor.set_value(key, self.fields[key].text().strip())
            backup = editor.save()
        except (OSError, KeyError, ValueError) as exc:
            QMessageBox.critical(self, "ares", f"Falha ao salvar as configurações.\n\n{exc}")
            return
        self.refresh()
        QMessageBox.information(
            self,
            "ares",
            f"Configurações salvas em:\n{editor.path}\n\nBackup:\n{backup}",
        )
