"""Diretórios auxiliares usados pelo SERM V2."""
from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.config.app_config import AppConfig
from app.core.services.retroarch_download_service import RetroArchDownloadService
from ..integrations.launchbox import LaunchBoxIntegration


class ToolsDirectoriesPage(QWidget):
    """Configura LaunchBox e 7-Zip na mesma área de diretórios auxiliares."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.config = getattr(parent, "config", None) or AppConfig()
        self.launchbox = LaunchBoxIntegration()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Monta os campos persistentes de LaunchBox e 7-Zip."""
        layout = QVBoxLayout(self)
        group = QGroupBox("LaunchBox")
        form = QFormLayout(group)
        self.launchbox_edit = QLineEdit()
        self.launchbox_edit.setReadOnly(True)
        browse = QPushButton("Selecionar LaunchBox.exe")
        browse.clicked.connect(self.select_launchbox)
        row = QHBoxLayout(); row.addWidget(self.launchbox_edit, 1); row.addWidget(browse)
        form.addRow("Executável:", row)
        self.launchbox_status = QLabel()
        form.addRow("Status:", self.launchbox_status)
        layout.addWidget(group)

        group7 = QGroupBox("7-Zip")
        form7 = QFormLayout(group7)
        self.sevenzip_edit = QLineEdit()
        self.sevenzip_edit.setReadOnly(True)
        browse7 = QPushButton("Selecionar 7z.exe")
        browse7.clicked.connect(self.select_7zip)
        row7 = QHBoxLayout(); row7.addWidget(self.sevenzip_edit, 1); row7.addWidget(browse7)
        form7.addRow("Executável:", row7)
        self.sevenzip_status = QLabel()
        form7.addRow("Status:", self.sevenzip_status)
        layout.addWidget(group7)

        actions = QHBoxLayout()
        refresh = QPushButton("Redetectar")
        refresh.clicked.connect(self.refresh)
        actions.addWidget(refresh)
        save = QPushButton("Salvar")
        save.clicked.connect(self.save)
        actions.addWidget(save)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addStretch()

    def refresh(self) -> None:
        """Atualiza descoberta local sem alterar configurações do usuário."""
        self.config.load()
        launchbox = getattr(self.config, "launchbox_path", None)
        if launchbox:
            self.launchbox_edit.setText(str(launchbox))
        else:
            discovered = self.launchbox.discover()
            self.launchbox_edit.setText(str(discovered or ""))
        self.launchbox_status.setText("● Encontrado" if self.launchbox_edit.text() and Path(self.launchbox_edit.text()).is_file() else "● Não encontrado")
        configured = getattr(self.config, "sevenzip_path", None)
        detected = Path(configured) if configured else RetroArchDownloadService.detect_7zip()
        self.sevenzip_edit.setText(str(detected or ""))
        self.sevenzip_status.setText("● Encontrado" if detected and Path(detected).is_file() else "● Não encontrado")

    def select_launchbox(self) -> None:
        """Seleciona manualmente o executável do LaunchBox."""
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar LaunchBox.exe", str(Path.home()), "LaunchBox (LaunchBox.exe);;Executáveis (*.exe)")
        if path:
            self.launchbox_edit.setText(path)
            self.save()

    def select_7zip(self) -> None:
        """Seleciona manualmente o executável de linha de comando do 7-Zip."""
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar 7z.exe", str(Path.home()), "7-Zip (7z.exe);;Executáveis (*.exe)")
        if path:
            self.sevenzip_edit.setText(path)
            self.save()

    def save(self) -> None:
        """Persiste LaunchBox e 7-Zip usando os atributos opcionais do AppConfig."""
        launchbox = self.launchbox_edit.text().strip()
        sevenzip = self.sevenzip_edit.text().strip()
        if hasattr(self.config, "launchbox_path"):
            self.config.launchbox_path = Path(launchbox) if launchbox else None
        if hasattr(self.config, "sevenzip_path"):
            self.config.sevenzip_path = Path(sevenzip) if sevenzip else None
        self.config.save()
        self.refresh()


__all__ = ["ToolsDirectoriesPage"]
