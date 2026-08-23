"""Diretórios específicos do RetroArch."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.config.app_config import AppConfig


class RetroArchDirectoriesTab(QWidget):
    """Editor dos diretórios persistidos do RetroArch."""

    PATHS = (
        ("config", "Configuração"),
        ("cores", "Cores"),
        ("system", "System / BIOS"),
        ("assets", "Assets"),
        ("shaders", "Shaders"),
        ("saves", "Saves"),
        ("states", "Save states"),
        ("downloads", "Downloads"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = getattr(parent, "config", None) or AppConfig()
        self.edits: dict[str, QLineEdit] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Monta os campos de diretórios do RetroArch."""
        layout = QVBoxLayout(self)
        group = QGroupBox("Diretórios do RetroArch")
        form = QFormLayout(group)
        for key, label in self.PATHS:
            edit = QLineEdit()
            button = QPushButton("…")
            button.setFixedWidth(34)
            button.clicked.connect(lambda _=False, k=key: self._choose(k))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(button)
            form.addRow(f"{label}:", row)
            self.edits[key] = edit
        save = QPushButton("Salvar diretórios do RetroArch")
        save.setStyleSheet("font-weight:bold;padding:8px;")
        save.clicked.connect(self.save)
        form.addRow("", save)
        layout.addWidget(group)
        self.status_label = QLineEdit()
        self.status_label.setReadOnly(True)
        self.status_label.setPlaceholderText("Status")
        layout.addWidget(self.status_label)
        layout.addStretch()

    def refresh(self) -> None:
        """Carrega os caminhos persistidos no AppConfig."""
        self.config.load()
        for key, edit in self.edits.items():
            value = self.config.get_emulator_path("retroarch", key)
            edit.setText(str(value) if value else "")
        self.status_label.setText("Diretórios carregados.")

    def _choose(self, key: str) -> None:
        """Seleciona uma pasta para um diretório do RetroArch."""
        current = self.edits[key].text().strip() or str(Path.home())
        selected = QFileDialog.getExistingDirectory(self, f"Selecionar {key}", current)
        if selected:
            self.edits[key].setText(selected)

    def save(self) -> None:
        """Persiste os diretórios sem alterar o retroarch.cfg nativo."""
        for key, edit in self.edits.items():
            value = edit.text().strip()
            self.config.set_emulator_path("retroarch", key, Path(value) if value else None)
        self.config.save()
        self.status_label.setText("Diretórios do RetroArch salvos.")
        parent = self.parent_window
        if parent is not None and hasattr(parent, "retroarch_home_tab"):
            parent.retroarch_home_tab.refresh()
        if parent is not None and hasattr(parent, "retroarch_catalog_tab"):
            parent.retroarch_catalog_tab.refresh()


__all__ = ["RetroArchDirectoriesTab"]
