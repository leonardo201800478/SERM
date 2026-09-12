"""Executáveis auxiliares usados pelo SERM V2."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ..integrations.launchbox import LaunchBoxIntegration
from ..runtime.paths import integrations_root
from ..services.emulator_manager import EmulatorManager


class ToolsDirectoriesPage(QWidget):
    """Centraliza somente executáveis externos auxiliares do SERM."""

    CONFIG_PATH = integrations_root() / "tools.json"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.launchbox = LaunchBoxIntegration()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        intro = QLabel("Ferramentas auxiliares")
        intro.setProperty("role", "title")
        layout.addWidget(intro)
        hint = QLabel("Aponte aqui executáveis externos que o SERM utiliza para tarefas de apoio. Pastas dos emuladores permanecem em Diretórios.")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        group = QGroupBox("LaunchBox")
        form = QFormLayout(group); form.setContentsMargins(10, 8, 10, 9); form.setVerticalSpacing(6); form.setHorizontalSpacing(10)
        self.launchbox_edit = QLineEdit(); self.launchbox_edit.setReadOnly(True)
        browse = QPushButton("Selecionar .exe"); browse.setMaximumWidth(130); browse.clicked.connect(self.select_launchbox)
        launch = QPushButton("Abrir"); launch.setMaximumWidth(90); launch.clicked.connect(self.launch_launchbox)
        row = QHBoxLayout(); row.setSpacing(5); row.addWidget(self.launchbox_edit, 1); row.addWidget(browse, 0); row.addWidget(launch, 0)
        form.addRow("Executável:", row)
        self.launchbox_status = QLabel(); form.addRow("Status:", self.launchbox_status)
        layout.addWidget(group)

        group7 = QGroupBox("7-Zip")
        form7 = QFormLayout(group7); form7.setContentsMargins(10, 8, 10, 9); form7.setVerticalSpacing(6); form7.setHorizontalSpacing(10)
        self.sevenzip_edit = QLineEdit(); self.sevenzip_edit.setReadOnly(True)
        browse7 = QPushButton("Selecionar .exe"); browse7.setMaximumWidth(130); browse7.clicked.connect(self.select_7zip)
        row7 = QHBoxLayout(); row7.setSpacing(5); row7.addWidget(self.sevenzip_edit, 1); row7.addWidget(browse7, 0)
        form7.addRow("Executável:", row7)
        self.sevenzip_status = QLabel(); form7.addRow("Status:", self.sevenzip_status)
        layout.addWidget(group7)

        actions = QHBoxLayout(); actions.setSpacing(5)
        refresh = QPushButton("Redetectar"); refresh.setMaximumWidth(110); refresh.clicked.connect(self.refresh)
        save = QPushButton("Salvar"); save.setMaximumWidth(100); save.clicked.connect(self.save)
        actions.addWidget(refresh); actions.addWidget(save); actions.addStretch(); layout.addLayout(actions); layout.addStretch()
        self.setStyleSheet("QPushButton{min-height:25px;padding:3px 10px;} QLineEdit{min-height:25px;padding:2px 7px;} QGroupBox{margin-top:8px;padding-top:8px;}")

    def _load_tools(self) -> dict:
        if not self.CONFIG_PATH.is_file(): return {}
        try: data = json.loads(self.CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError): return {}
        return data if isinstance(data, dict) else {}

    def refresh(self) -> None:
        configured = self._load_tools()
        launchbox = self.launchbox.discover()
        launchbox_path = str(launchbox or configured.get("launchbox") or "")
        self.launchbox_edit.setText(launchbox_path)
        found = bool(launchbox_path) and Path(launchbox_path).is_file()
        self.launchbox_status.setText("● Encontrado" if found else "● Não encontrado")
        sevenzip = configured.get("sevenzip")
        detected = Path(sevenzip) if sevenzip and Path(sevenzip).is_file() else EmulatorManager.find_7zip()
        self.sevenzip_edit.setText(str(detected or ""))
        self.sevenzip_status.setText("● Encontrado" if detected and Path(detected).is_file() else "● Não encontrado")

    def select_launchbox(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar LaunchBox.exe", self._initial_launchbox_directory(), "LaunchBox (LaunchBox.exe);;Executáveis (*.exe)")
        if not path: return
        try: self.launchbox.set_executable(Path(path))
        except (OSError, ValueError) as exc: QMessageBox.warning(self, "LaunchBox", str(exc)); return
        self.refresh()

    def _initial_launchbox_directory(self) -> str:
        executable = self.launchbox.executable
        if executable is not None and executable.parent.is_dir(): return str(executable.parent)
        configured = self._load_tools().get("launchbox")
        if configured and Path(str(configured)).parent.is_dir(): return str(Path(str(configured)).parent)
        return str(Path.home())

    def launch_launchbox(self) -> None:
        try: self.launchbox.launch()
        except (OSError, ValueError) as exc: QMessageBox.warning(self, "LaunchBox", str(exc))

    def select_7zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar 7z.exe", str(Path.home()), "7-Zip (7z.exe);;Executáveis (*.exe)")
        if path: self.sevenzip_edit.setText(path); self.save()

    def save(self) -> None:
        payload = self._load_tools(); payload["launchbox"] = self.launchbox_edit.text().strip() or None; payload["sevenzip"] = self.sevenzip_edit.text().strip() or None
        self.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.CONFIG_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self.refresh()


__all__ = ["ToolsDirectoriesPage"]
