"""Directory guide with explicit emulator executable selection."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QBoxLayout,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from .altirra_directories_page import AltirraDirectoriesPage
from .amiberry_directories_page import AmiberryDirectoriesPage
from .ares_directories_page import AresDirectoriesPage
from .ares_firmware_page import AresFirmwarePage
from .directories_guide_page import DirectoryGuidePage
from .directory_dialogs import get_existing_directory
from .winuae_directories_page import WinUAEDirectoriesPage

MAME_EXECUTABLE_TITLE = "Executável do MAME"


class DirectoriesPage(DirectoryGuidePage):
    """Expose emulator directories with compact controls and MAME executable selection."""

    def _build_emulator_directory_settings(self, emulator: str, page) -> None:
        if emulator == "ares":
            self.ares_paths_page = AresDirectoriesPage(self)
            paths_group = QGroupBox("Paths do ares")
            paths_layout = QVBoxLayout(paths_group)
            paths_layout.addWidget(self.ares_paths_page)
            page.layout().addWidget(paths_group)
            self.ares_firmware_page = AresFirmwarePage(self)
            firmware_group = QGroupBox("Scan e reconstrução de firmware ares")
            firmware_layout = QVBoxLayout(firmware_group)
            firmware_layout.addWidget(self.ares_firmware_page)
            page.layout().addWidget(firmware_group)
            group = QGroupBox("Pastas de recursos do ares")
            form = QFormLayout(group)
            self.ares_resource_fields = {}
            for name in ("Database", "hiro", "Nintendo 64", "Shaders", "Systems"):
                key = f"ares_{name.casefold().replace(' ', '_')}"
                field = QLineEdit()
                field.setReadOnly(True)
                button = QPushButton("Selecionar pasta")
                button.setToolTip(
                    f"Seleciona e registra a pasta de recursos {name} do ares nas configurações do SERM."
                )
                button.clicked.connect(
                    lambda _=False, k=key, n=name, f=field: self._browse_ares_resource(k, n, f)
                )
                row = QHBoxLayout()
                row.addWidget(field, 1)
                row.addWidget(button)
                form.addRow(name, row)
                self.ares_resource_fields[key] = field
            form.addRow(
                "Bibliotecas", QLabel("librashader.dll e SDL3.dll permanecem junto ao ares.exe.")
            )
            page.layout().addWidget(group)
            self.refresh()
            return
        elif emulator == "altirra":
            self.altirra_paths_page = AltirraDirectoriesPage(self)
            widget = self.altirra_paths_page
        elif emulator == "amiberry":
            self.amiberry_paths_page = AmiberryDirectoriesPage(self)
            widget = self.amiberry_paths_page
        elif emulator == "winuae":
            self.winuae_paths_page = WinUAEDirectoriesPage(self)
            widget = self.winuae_paths_page
        else:
            return
        layout = page.layout()
        if isinstance(layout, QBoxLayout):
            layout.addWidget(widget)

    def _build_mame_tab(self, page) -> None:
        super()._build_mame_tab(page)
        layout = page.layout()
        if not isinstance(layout, QBoxLayout):
            return
        group = QGroupBox(MAME_EXECUTABLE_TITLE)
        form = QFormLayout(group)
        self.mame_executable_edit = QLineEdit()
        self.mame_executable_edit.setReadOnly(True)
        self.mame_executable_edit.setPlaceholderText(
            "Selecione o mame.exe que o SERM deve utilizar"
        )
        select = QPushButton("Selecionar mame.exe")
        select.setMaximumWidth(150)
        select.clicked.connect(self.select_mame_executable)
        row = QHBoxLayout()
        row.setSpacing(5)
        row.addWidget(self.mame_executable_edit, 1)
        row.addWidget(select, 0)
        form.addRow("Executável:", row)
        info = QLabel(
            "O diretório de instalação e o executável são independentes. "
            "O executável selecionado será usado para versão, DAT/ListXML e testes."
        )
        info.setWordWrap(True)
        form.addRow("", info)
        layout.insertWidget(1, group)

    def _browse_ares_resource(self, key: str, label: str, field: QLineEdit) -> None:
        selected = get_existing_directory(
            self, f"Selecionar pasta {label} do ares", field.text() or str(Path.home())
        )
        if not selected:
            return
        data = self._load_json(self.PATHS_FILE)
        data[key] = str(Path(selected).resolve())
        self._save_json(self.PATHS_FILE, data)
        field.setText(data[key])

    def select_mame_executable(self) -> None:
        current = self.mame_executable_edit.text().strip()
        start = str(Path(current).parent) if current else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar executável do MAME",
            start,
            "MAME (mame.exe);;Executáveis (*.exe);;Todos os arquivos (*)",
        )
        if not path:
            return
        executable = Path(path).resolve()
        if executable.suffix.casefold() != ".exe" or not executable.is_file():
            QMessageBox.warning(
                self,
                MAME_EXECUTABLE_TITLE,
                "Selecione um arquivo executável válido.",
            )
            return
        try:
            result = subprocess.run(
                [str(executable), "-noreadconfig", "-version"],
                cwd=str(executable.parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            QMessageBox.warning(
                self,
                MAME_EXECUTABLE_TITLE,
                f"Não foi possível consultar o executável selecionado.\n\n{exc}",
            )
            return
        data = self._load_json(self.PATHS_FILE)
        data["mame_executable"] = str(executable)
        self._save_json(self.PATHS_FILE, data)
        self.mame_executable_edit.setText(str(executable))
        output = (result.stdout or "").strip().splitlines()
        version = output[0] if output else "versão não identificada"
        if result.returncode != 0:
            QMessageBox.warning(
                self,
                "Executável do MAME selecionado",
                f"O caminho foi salvo, mas o MAME retornou código {result.returncode}.\n\n"
                f"Executável:\n{executable}\n\nSaída:\n{version}",
            )
            return
        QMessageBox.information(
            self,
            "Executável do MAME selecionado",
            f"Executável salvo:\n{executable}\n\nResposta do MAME:\n{version}",
        )

    def refresh(self) -> None:
        super().refresh()
        if hasattr(self, "altirra_paths_page"):
            self.altirra_paths_page.refresh()
        if hasattr(self, "amiberry_paths_page"):
            self.amiberry_paths_page.refresh()
        if hasattr(self, "winuae_paths_page"):
            self.winuae_paths_page.refresh()
        if hasattr(self, "ares_paths_page"):
            self.ares_paths_page.refresh()
        if hasattr(self, "mame_executable_edit"):
            paths = self._load_json(self.PATHS_FILE)
            raw = paths.get("mame_executable") or paths.get("mame_exe")
            self.mame_executable_edit.setText(str(raw) if raw else "")
        for key, field in getattr(self, "ares_resource_fields", {}).items():
            field.setText(str(self._load_json(self.PATHS_FILE).get(key) or ""))


__all__ = ["DirectoriesPage"]
