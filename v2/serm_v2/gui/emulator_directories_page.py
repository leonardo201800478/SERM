"""Standalone-emulator directory configuration for SERM V2."""
from __future__ import annotations

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

from ..services.emulator_manager import EmulatorManager
from .directories_page import DirectoriesPage as BaseDirectoriesPage


class DirectoriesPage(BaseDirectoriesPage):
    """Configure installation roots separately from integration executables."""

    def _emulators_tab(self) -> QWidget:
        """Build standalone emulator fields for installation and integration."""
        page = QWidget()
        layout = QVBoxLayout(page)
        paths = self._load_json(self.PATHS_FILE)
        self.emulator_edits: dict[str, QLineEdit] = {}
        self.emulator_exe_edits: dict[str, QLineEdit] = {}

        group = QGroupBox("Emuladores standalone")
        form = QFormLayout(group)
        for key, label in self.EMULATOR_PATHS.items():
            install_edit = QLineEdit(str(paths.get(key) or ""))
            install_edit.setReadOnly(True)
            install_edit.setPlaceholderText("Diretório de instalação")
            browse_install = QPushButton("Selecionar diretório")
            browse_install.clicked.connect(lambda _=False, k=key: self._select_installation(k))
            row_install = QHBoxLayout()
            row_install.addWidget(install_edit, 1)
            row_install.addWidget(browse_install)
            form.addRow(f"{label} — instalação:", row_install)
            self.emulator_edits[key] = install_edit

            exe_edit = QLineEdit(str(paths.get(f"{key}_exe") or ""))
            exe_edit.setReadOnly(True)
            exe_edit.setPlaceholderText(EmulatorManager.EXECUTABLES[key])
            browse_exe = QPushButton("Selecionar .exe")
            browse_exe.clicked.connect(lambda _=False, k=key: self.select_emulator_executable(k))
            row_exe = QHBoxLayout()
            row_exe.addWidget(exe_edit, 1)
            row_exe.addWidget(browse_exe)
            form.addRow(f"{label} — executável de integração:", row_exe)
            self.emulator_exe_edits[key] = exe_edit

        layout.addWidget(group)
        hint = QLabel(
            "A instalação/download trabalha exclusivamente com o diretório de instalação. "
            "O .exe é configurado separadamente nesta aba para integração, permitindo que o SERM use o arquivo de configuração próprio de cada emulador."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888;")
        layout.addWidget(hint)
        refresh = QPushButton("🔄 Atualizar detecção")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        layout.addStretch()
        return page

    def _select_installation(self, key: str) -> None:
        """Select and persist only the standalone emulator installation directory."""
        selected = QFileDialog.getExistingDirectory(
            self,
            f"Diretório de instalação — {self.EMULATOR_PATHS[key]}",
            str(Path.home()),
        )
        if not selected:
            return
        data = self._load_json(self.PATHS_FILE)
        data[key] = str(Path(selected).resolve())
        self._save_json(self.PATHS_FILE, data)
        self.refresh()

    def select_emulator_executable(self, key: str) -> None:
        """Select and persist the exact executable used for emulator integration."""
        label = self.EMULATOR_PATHS[key]
        expected = EmulatorManager.EXECUTABLES[key]
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Selecionar executável de integração — {label}",
            str(Path.home()),
            f"{expected};;Executáveis (*.exe)",
        )
        if not path:
            return
        executable = Path(path).resolve()
        data = self._load_json(self.PATHS_FILE)
        data[f"{key}_exe"] = str(executable)
        self._save_json(self.PATHS_FILE, data)
        self.refresh()

    def refresh(self) -> None:
        """Refresh both installation directories and integration executables."""
        super().refresh()
        paths = self._load_json(self.PATHS_FILE)
        for key, edit in getattr(self, "emulator_exe_edits", {}).items():
            edit.setText(str(paths.get(f"{key}_exe") or ""))


__all__ = ["DirectoriesPage"]
