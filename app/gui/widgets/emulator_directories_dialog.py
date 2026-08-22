"""Diálogo padronizado para diretórios de instalação dos emuladores."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from app.config.app_config import AppConfig


class EmulatorDirectoriesDialog(QDialog):
    """Permite definir onde cada emulador deve ser instalado."""

    FIELDS = (
        ("mame", "MAME"),
        ("flycast", "Flycast"),
        ("supermodel", "Supermodel"),
        ("fbneo", "FBNeo"),
    )

    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.edits: dict[str, QLineEdit] = {}
        self.setWindowTitle("Diretórios dos emuladores")
        self.setModal(True)
        self.resize(760, 260)
        self._build_ui()

    def _build_ui(self) -> None:
        """Constrói o formulário de diretórios."""
        layout = QVBoxLayout(self)
        form = QFormLayout()

        for key, label in self.FIELDS:
            edit = QLineEdit()
            edit.setText(str(getattr(self.config, f"{key}_dir") or ""))
            edit.setPlaceholderText("Selecione a pasta onde os arquivos do emulador ficarão instalados")
            edit.setToolTip(
                "Diretório raiz da instalação. O arquivo baixado será extraído diretamente aqui, "
                "sem criar uma pasta adicional para o pacote."
            )
            button = QPushButton("Selecionar…")
            button.clicked.connect(lambda _checked=False, k=key: self._choose(k))
            row = QHBoxLayout()
            row.addWidget(edit)
            row.addWidget(button)
            form.addRow(f"{label}:", row)
            self.edits[key] = edit

        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _choose(self, key: str) -> None:
        """Seleciona a pasta de instalação do emulador informado."""
        current = self.edits[key].text().strip()
        selected = QFileDialog.getExistingDirectory(
            self,
            f"Selecionar diretório do {dict(self.FIELDS)[key]}",
            current,
        )
        if selected:
            self.edits[key].setText(selected)

    def _save(self) -> None:
        """Persiste os diretórios e fecha o diálogo."""
        for key, _label in self.FIELDS:
            value = self.edits[key].text().strip()
            setattr(self.config, f"{key}_dir", Path(value) if value else None)
        self.config.save()
        self.accept()
