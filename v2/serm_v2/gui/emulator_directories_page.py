"""Directory guide with explicit emulator executable selection."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtWidgets import QBoxLayout, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton

from .directory_guide_v2 import DirectoryGuidePage

MAME_EXECUTABLE_TITLE = "Executável do MAME"


class DirectoriesPage(DirectoryGuidePage):
    """Expose emulator directories with compact controls and MAME executable selection."""

    def _build_mame_tab(self, page) -> None:
        super()._build_mame_tab(page)
        layout = page.layout()
        if not isinstance(layout, QBoxLayout):
            return
        group = QGroupBox(MAME_EXECUTABLE_TITLE)
        form = QFormLayout(group)
        self.mame_executable_edit = QLineEdit()
        self.mame_executable_edit.setReadOnly(True)
        self.mame_executable_edit.setPlaceholderText("Selecione o mame.exe que o SERM deve utilizar")
        select = QPushButton("Selecionar mame.exe")
        select.setMaximumWidth(150)
        select.clicked.connect(self.select_mame_executable)
        row = QHBoxLayout(); row.setSpacing(5); row.addWidget(self.mame_executable_edit, 1); row.addWidget(select, 0)
        form.addRow("Executável:", row)
        info = QLabel("O diretório de instalação e o executável são independentes. O executável selecionado será usado para versão, DAT/ListXML e testes.")
        info.setWordWrap(True)
        form.addRow("", info)
        layout.insertWidget(1, group)

    def select_mame_executable(self) -> None:
        current = self.mame_executable_edit.text().strip()
        start = str(Path(current).parent) if current else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar executável do MAME", start, "MAME (mame.exe);;Executáveis (*.exe);;Todos os arquivos (*)")
        if not path:
            return
        executable = Path(path).resolve()
        if executable.suffix.casefold() != ".exe" or not executable.is_file():
            QMessageBox.warning(self, MAME_EXECUTABLE_TITLE, "Selecione um arquivo executável válido.")
            return
        try:
            result = subprocess.run([str(executable), "-noreadconfig", "-version"], cwd=str(executable.parent), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=5, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            QMessageBox.warning(self, MAME_EXECUTABLE_TITLE, f"Não foi possível consultar o executável selecionado.\n\n{exc}")
            return
        data = self._load_json(self.PATHS_FILE); data["mame_executable"] = str(executable); self._save_json(self.PATHS_FILE, data); self.mame_executable_edit.setText(str(executable))
        output = (result.stdout or "").strip().splitlines(); version = output[0] if output else "versão não identificada"
        if result.returncode != 0:
            QMessageBox.warning(self, "Executável do MAME selecionado", f"O caminho foi salvo, mas o MAME retornou código {result.returncode}.\n\nExecutável:\n{executable}\n\nSaída:\n{version}")
            return
        QMessageBox.information(self, "Executável do MAME selecionado", f"Executável salvo:\n{executable}\n\nResposta do MAME:\n{version}")

    def refresh(self) -> None:
        super().refresh()
        if hasattr(self, "mame_executable_edit"):
            raw = self._load_json(self.PATHS_FILE).get("mame_executable")
            self.mame_executable_edit.setText(str(raw) if raw else "")


__all__ = ["DirectoriesPage"]
