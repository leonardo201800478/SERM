"""Diretórios auxiliares usados pelo SERM V2."""

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
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..integrations.launchbox import LaunchBoxIntegration
from ..runtime.paths import integrations_root
from ..services.emulator_manager import EmulatorManager


class ToolsDirectoriesPage(QWidget):
    """Configura LaunchBox e 7-Zip na mesma área de diretórios auxiliares."""

    CONFIG_PATH = integrations_root() / "tools.json"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
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
        row = QHBoxLayout()
        row.addWidget(self.launchbox_edit, 1)
        row.addWidget(browse)
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
        row7 = QHBoxLayout()
        row7.addWidget(self.sevenzip_edit, 1)
        row7.addWidget(browse7)
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

    def _load_tools(self) -> dict:
        """Carrega o registro auxiliar do SERM V2."""
        if not self.CONFIG_PATH.is_file():
            return {}
        try:
            return json.loads(self.CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}

    def refresh(self) -> None:
        """Atualiza descoberta local sem alterar configurações do usuário."""
        configured = self._load_tools()
        launchbox = self.launchbox.discover()
        launchbox_path = str(launchbox or configured.get("launchbox") or "")
        self.launchbox_edit.setText(launchbox_path)
        launchbox_found = bool(launchbox_path) and Path(launchbox_path).is_file()
        self.launchbox_status.setText("● Encontrado" if launchbox_found else "● Não encontrado")

        sevenzip = configured.get("sevenzip")
        detected = (
            Path(sevenzip) if sevenzip and Path(sevenzip).is_file() else EmulatorManager.find_7zip()
        )
        self.sevenzip_edit.setText(str(detected or ""))
        self.sevenzip_status.setText(
            "● Encontrado" if detected and Path(detected).is_file() else "● Não encontrado"
        )

    def select_launchbox(self) -> None:
        """Seleciona manualmente o executável do LaunchBox e persiste a integração."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar LaunchBox.exe",
            str(Path.home()),
            "LaunchBox (LaunchBox.exe);;Executáveis (*.exe)",
        )
        if path:
            self.launchbox.set_executable(Path(path))
            self.refresh()

    def select_7zip(self) -> None:
        """Seleciona manualmente o executável de linha de comando do 7-Zip."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar 7z.exe",
            str(Path.home()),
            "7-Zip (7z.exe);;Executáveis (*.exe)",
        )
        if path:
            self.sevenzip_edit.setText(path)
            self.save()

    def save(self) -> None:
        """Persiste somente os caminhos auxiliares."""
        payload = self._load_tools()
        payload["launchbox"] = self.launchbox_edit.text().strip() or None
        payload["sevenzip"] = self.sevenzip_edit.text().strip() or None
        self.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.CONFIG_PATH.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.refresh()


__all__ = ["ToolsDirectoriesPage"]
