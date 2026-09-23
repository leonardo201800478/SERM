"""Shared directory and emulator configuration helpers."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root


class ConfigFileEditor:
    """Read and safely update simple emulator ``key=value`` files."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._text = self.path.read_text(encoding="utf-8")
        self._lines = self._text.splitlines(keepends=True)

    def values(self, key: str) -> list[str]:
        """Return all values for an uncommented key."""
        values: list[str] = []
        for line in self._lines:
            stripped = line.strip()
            if stripped.startswith(("#", ";")):
                continue
            name, separator, value = stripped.partition("=")
            if separator and name.strip() == key:
                values.append(value.strip().strip('"'))
        return values

    def set_value(self, key: str, value: str) -> None:
        """Replace the first occurrence of an existing key."""
        for index, line in enumerate(self._lines):
            stripped = line.lstrip()
            if stripped.startswith(("#", ";")):
                continue
            name, separator, _ = stripped.partition("=")
            if separator and name.strip() == key:
                newline = "\n" if line.endswith("\n") else ""
                self._lines[index] = f"{line[:len(line) - len(stripped)]}{key}={value}{newline}"
                return
        raise KeyError(key)

    def save(self) -> Path:
        """Create a backup and atomically replace the configuration file."""
        backup = self.path.with_name(f"{self.path.name}.bak")
        shutil.copy2(self.path, backup)
        content = "".join(self._lines)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, self.path)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise
        return backup


class DirectoryGuidePage(QWidget):
    """Base page for paths shared by the emulator-related configuration screens."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    EMULATORS = (
        ("mame", "MAME", "mame_config"),
        ("fbneo", "FBNeo", "fbneo_config"),
        ("flycast", "Flycast", "flycast_config"),
        ("supermodel", "Supermodel", "supermodel_config"),
        ("ymir", "Ymir · Sega Saturn", None),
        ("duckstation", "DuckStation · PlayStation 1", None),
        ("pcsx2", "PCSX2 · PlayStation 2", None),
        ("ppsspp", "PPSSPP · PSP", None),
        ("dolphin", "Dolphin · GameCube / Wii", None),
        ("xemu", "Xemu · Xbox", None),
        ("azaharplus", "AzaharPlus · Nintendo 3DS", None),
        ("rpcs3", "RPCS3 · PlayStation 3", None),
        ("xenia_canary", "Xenia Canary · Xbox 360", None),
        ("cemu", "Cemu · Wii U", None),
        ("melonds", "melonDS · Nintendo DS", None),
        ("mgba", "mGBA · Game Boy Advance", None),
        ("shadps4", "shadPS4 · PlayStation 4", None),
        ("ares", "ares · Multi-sistema", None),
        ("dosbox_staging", "DOSBox Staging · DOS", None),
        ("scummvm", "ScummVM · Aventuras gráficas", None),
        ("mesence", "MesenCE · Multi-sistema 8/16-bit", None),
        ("sameboy", "SameBoy · Game Boy", None),
        ("ryujinx_nextendo", "Ryujinx-Nextendo · Nintendo Switch", None),
        ("super_zsnes", "SUPER ZSNES · Super Nintendo", None),
        ("winuae", "WinUAE · Amiga", None),
        ("vice", "VICE · Commodore", None),
        ("xm6pro68k", "XM6 Pro-68k · Sharp X68000", None),
        ("dosbox_x", "DOSBox-X · DOS / PC-98", None),
        ("stella", "Stella · Atari 2600", None),
        ("altirra", "Altirra · Atari 8-bit", None),
        ("rmg", "RMG · Nintendo 64", None),
        ("retroarch", "RetroArch", "retroarch_cfg"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._directory_fields: dict[str, QLineEdit] = {}
        self._fields: dict[str, QLineEdit] = {}
        self._build_ui()
        self.refresh()

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, ValueError, TypeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _save_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        for _key, label, config_key in self.EMULATORS:
            page = QWidget()
            form = QFormLayout(page)
            directory_field = QLineEdit()
            directory_field.setReadOnly(True)
            browse_directory = QPushButton("Selecionar diretório")
            browse_directory.clicked.connect(
                lambda _checked=False, name=_key: self._browse_directory(name)
            )
            form.addRow("Diretório de instalação:", directory_field)
            form.addRow("", browse_directory)
            self._directory_fields[_key] = directory_field
            if config_key:
                field = QLineEdit()
                field.setReadOnly(True)
                browse = QPushButton("Selecionar arquivo")
                browse.clicked.connect(lambda _checked=False, name=config_key: self._browse(name))
                form.addRow("Arquivo de configuração:", field)
                form.addRow("", browse)
                self._fields[config_key] = field
            self.tabs.addTab(page, label)
        root.addWidget(self.tabs, 1)
        mame_page = self.tabs.widget(0)
        if mame_page is not None:
            self._build_mame_tab(mame_page)

    def _build_mame_tab(self, _page: QWidget) -> None:
        """Hook for the MAME executable selector supplied by DirectoriesPage."""

    def _browse(self, config_key: str) -> None:
        current = self._fields[config_key].text()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar arquivo de configuração",
            str(Path(current).parent) if current else str(Path.home()),
            "Arquivos de configuração (*.ini *.cfg *.conf);;Todos os arquivos (*)",
        )
        if not path:
            return
        data = self._load_json(self.PATHS_FILE)
        data[config_key] = str(Path(path).resolve())
        self._save_json(self.PATHS_FILE, data)
        self.refresh()

    def _browse_directory(self, emulator: str) -> None:
        current = self._directory_fields[emulator].text()
        selected = QFileDialog.getExistingDirectory(
            self,
            f"Selecionar diretório do {dict((key, label) for key, label, _ in self.EMULATORS)[emulator]}",
            current or str(Path.home()),
        )
        if not selected:
            return
        data = self._load_json(self.PATHS_FILE)
        data[emulator] = str(Path(selected).resolve())
        self._save_json(self.PATHS_FILE, data)
        self.refresh()

    def refresh(self) -> None:
        data = self._load_json(self.PATHS_FILE)
        for emulator, field in self._directory_fields.items():
            field.setText(str(data.get(emulator) or ""))
        for config_key, field in self._fields.items():
            field.setText(str(data.get(config_key) or ""))


__all__ = ["ConfigFileEditor", "DirectoryGuidePage"]
