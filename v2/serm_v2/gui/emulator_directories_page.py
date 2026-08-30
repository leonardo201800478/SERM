"""Directory guide with explicit emulator executable selection."""
from __future__ import annotations

import subprocess
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
)

from . import directories_guide_page
from .directories_guide_page import DirectoryGuidePage

# Compatibility injection for the current directory-guide implementation.
# The guide instantiates QLineEdit in _config_header(); keeping the symbol
# available here prevents the startup NameError without changing its config
# editing/persistence logic.
directories_guide_page.QLineEdit = QLineEdit


class DirectoriesPage(DirectoryGuidePage):
    """Expose the directory guide and keep MAME root/executable independent.

    MAME installations may contain multiple binaries. The installation root is
    used to resolve relative configuration paths, while the explicitly selected
    executable is persisted separately and is used by SERM for version/DAT
    discovery. Selecting an executable never modifies ``mame.ini``.
    """

    def _build_mame_tab(self, page) -> None:
        """Add the MAME executable selector without replacing directory editing."""
        super()._build_mame_tab(page)
        layout = page.layout()
        if layout is None:
            return

        group = QGroupBox("Executável do MAME")
        form = QFormLayout(group)
        self.mame_executable_edit = QLineEdit()
        self.mame_executable_edit.setReadOnly(True)
        self.mame_executable_edit.setPlaceholderText(
            "Selecione o mame.exe que o SERM deve utilizar"
        )
        select = QPushButton("Selecionar mame.exe")
        select.clicked.connect(self.select_mame_executable)
        row = QHBoxLayout()
        row.addWidget(self.mame_executable_edit, 1)
        row.addWidget(select)
        form.addRow("Executável:", row)

        info = QLabel(
            "Independente do diretório de instalação. O SERM pode ter várias versões "
            "do MAME no mesmo computador; apenas este executável será usado para "
            "detecção de versão, DAT/ListXML e testes."
        )
        info.setWordWrap(True)
        form.addRow("", info)
        layout.insertWidget(1, group)

    def select_mame_executable(self) -> None:
        """Select and persist the exact MAME executable used by SERM.

        The selected path belongs to SERM's own ``emulator_paths.json``. No
        emulator configuration file is changed by this action.
        """
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
                "Executável do MAME",
                "Selecione um arquivo executável válido.",
            )
            return

        # Do not reject compatible MAME builds/forks just because their version
        # string is unusual. A successful process launch is enough to accept it.
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
        except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as exc:
            QMessageBox.warning(
                self,
                "Executável do MAME",
                f"Não foi possível consultar o executável selecionado.\n\n{exc}",
            )
            return

        data = self._load_json(self.PATHS_FILE)
        data["mame_executable"] = str(executable)
        self._save_json(self.PATHS_FILE, data)
        self.mame_executable_edit.setText(str(executable))

        output = (result.stdout or "").strip().splitlines()
        version = output[0] if output else "versão não identificada"
        self.statusTip = lambda: None  # type: ignore[method-assign]
        QMessageBox.information(
            self,
            "Executável do MAME selecionado",
            f"Executável salvo:\n{executable}\n\nResposta do MAME:\n{version}",
        )

    def refresh(self) -> None:
        """Refresh the inherited directory state and the selected MAME binary."""
        super().refresh()
        if hasattr(self, "mame_executable_edit"):
            data = self._load_json(self.PATHS_FILE)
            raw = data.get("mame_executable")
            self.mame_executable_edit.setText(str(raw) if raw else "")


__all__ = ["DirectoriesPage"]
