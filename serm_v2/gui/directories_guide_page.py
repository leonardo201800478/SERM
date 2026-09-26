"""Shared directory and emulator configuration helpers."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QScroller,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root
from .directory_dialogs import get_existing_directory
from .emulator_catalog import grouped_emulators


class ConfigFileEditor:
    """Read and safely update simple emulator ``key=value`` files."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._text = self.path.read_text(encoding="utf-8")
        self._lines = self._text.splitlines(keepends=True)

    def values(self, key: str) -> list[str]:
        """Return all values for an uncommented key."""
        values: list[str] = []
        if self.path.suffix.casefold() == ".bml":
            parents: list[tuple[int, str]] = []
            for line in self._lines:
                stripped = line.strip()
                if not stripped or stripped.startswith(("#", ";")):
                    continue
                indent = len(line) - len(line.lstrip())
                while parents and parents[-1][0] >= indent:
                    parents.pop()
                if ":" not in stripped:
                    parents.append((indent, stripped))
                    continue
                name, value = stripped.split(":", 1)
                full_key = ".".join([part for _, part in parents] + [name.strip()])
                if full_key == key:
                    values.append(value.strip())
                if not value.strip():
                    parents.append((indent, name.strip()))
            return values
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
        if self.path.suffix.casefold() == ".bml":
            parents: list[tuple[int, str]] = []
            for index, line in enumerate(self._lines):
                stripped = line.strip()
                if not stripped or stripped.startswith(("#", ";")):
                    continue
                indent = len(line) - len(line.lstrip())
                while parents and parents[-1][0] >= indent:
                    parents.pop()
                if ":" not in stripped:
                    parents.append((indent, stripped))
                    continue
                name, current = stripped.split(":", 1)
                full_key = ".".join([part for _, part in parents] + [name.strip()])
                if full_key == key:
                    newline = "\n" if line.endswith("\n") else ""
                    self._lines[index] = f"{line[:indent]}{name.strip()}: {value}{newline}"
                    return
                if not current.strip():
                    parents.append((indent, name.strip()))
            raise KeyError(key)
        for index, line in enumerate(self._lines):
            stripped = line.lstrip()
            if stripped.startswith(("#", ";")):
                continue
            name, separator, _ = stripped.partition("=")
            if separator and name.strip() == key:
                newline = "\n" if line.endswith("\n") else ""
                self._lines[index] = f"{line[: len(line) - len(stripped)]}{key}={value}{newline}"
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


class SmoothScrollArea(QScrollArea):
    """Scrollable page with automatic bars and fine-grained wheel movement."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.verticalScrollBar().setSingleStep(24)
        QScroller.grabGesture(self.viewport(), QScroller.ScrollerGestureType.TouchGesture)


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
        ("azahar", "Azahar · Nintendo 3DS", "azahar_config"),
        ("rpcs3", "RPCS3 · PlayStation 3", None),
        ("xenia_canary", "Xenia Canary · Xbox 360", None),
        ("cemu", "Cemu · Wii U", None),
        ("melonds", "melonDS · Nintendo DS", None),
        ("mgba", "mGBA · Game Boy Advance", None),
        ("shadps4", "shadPS4 · PlayStation 4", None),
        ("ares", "ares · Multi-sistema", "ares_config"),
        ("dosbox_staging", "DOSBox Staging · DOS", None),
        ("scummvm", "ScummVM · Aventuras gráficas", None),
        ("mesence", "MesenCE · Multi-sistema 8/16-bit", None),
        ("sameboy", "SameBoy · Game Boy", None),
        ("ryujinx_nextendo", "Ryujinx-Nextendo · Nintendo Switch", None),
        ("super_zsnes", "SUPER ZSNES · Super Nintendo", None),
        ("winuae", "WinUAE · Amiga", "winuae_ini"),
        ("vice", "VICE · Commodore", None),
        ("xm6pro68k", "XM6 Pro-68k · Sharp X68000", None),
        ("dosbox_x", "DOSBox-X · DOS / PC-98", None),
        ("stella", "Stella · Atari 2600", None),
        ("altirra", "Altirra · Atari 8-bit", "altirra_config"),
        ("rmg", "RMG · Nintendo 64", None),
        ("retroarch", "RetroArch", "retroarch_cfg"),
        ("bigpemu", "BigPEmu · Atari Jaguar / Jaguar CD", None),
        ("blastem", "BlastEm · Sega Genesis / Mega Drive + CD / 32X", None),
        ("bizhawk", "BizHawk · Multi-sistema / TAS", None),
        ("dosbox_pure", "DOSBox Pure Unleashed · DOS / Windows 9x", None),
        ("yabasanshiro", "YabaSanshiro 2 · Sega Saturn", None),
        ("amiberry", "Amiberry · Amiga", "amiberry_ini"),
    )

    CATEGORIES = grouped_emulators((key for key, _label, _config in EMULATORS))

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._directory_fields: dict[str, QLineEdit] = {}
        self._fields: dict[str, QLineEdit] = {}
        self._executable_fields: dict[str, QLineEdit] = {}
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
        self.category_tabs = QTabWidget()
        self.emulator_tabs: dict[str, QTabWidget] = {}
        for category, members in self.CATEGORIES:
            category_page = QWidget()
            category_layout = QVBoxLayout(category_page)
            category_layout.setContentsMargins(0, 0, 0, 0)
            tabs = QTabWidget()
            self.emulator_tabs[category] = tabs
            for _key, label, config_key in self.EMULATORS:
                if _key not in members:
                    continue
                page = QWidget()
                page.setProperty("serm_emulator_key", _key)
                page_layout = QVBoxLayout(page)
                page_layout.setContentsMargins(8, 8, 8, 8)
                path_group = QGroupBox("Diretórios e arquivos")
                form = QFormLayout(path_group)
                directory_field = QLineEdit()
                directory_field.setReadOnly(True)
                browse_directory = QPushButton("Selecionar diretório")
                browse_directory.clicked.connect(
                    lambda _checked=False, name=_key: self._browse_directory(name)
                )
                form.addRow("Diretório de instalação:", directory_field)
                form.addRow("", browse_directory)
                self._directory_fields[_key] = directory_field
                if _key != "mame":
                    executable_key = self._executable_key(_key)
                    executable_field = QLineEdit()
                    executable_field.setReadOnly(True)
                    browse_executable = QPushButton("Selecionar executável")
                    browse_executable.clicked.connect(
                        lambda _checked=False, name=_key: self._browse_executable(name)
                    )
                    executable_row = QHBoxLayout()
                    executable_row.addWidget(executable_field, 1)
                    executable_row.addWidget(browse_executable)
                    form.addRow("Executável:", executable_row)
                    self._executable_fields[executable_key] = executable_field
                config_key = config_key or f"{_key}_config"
                field = QLineEdit()
                field.setReadOnly(True)
                browse = QPushButton("Selecionar arquivo de configuração")
                browse.clicked.connect(lambda _checked=False, name=config_key: self._browse(name))
                form.addRow("Arquivo de configuração:", field)
                form.addRow("", browse)
                self._fields[config_key] = field
                page_layout.addWidget(path_group)
                self._build_emulator_directory_settings(_key, page)
                page_layout.addStretch(1)
                scroll_area = SmoothScrollArea()
                scroll_area.setWidget(page)
                tabs.addTab(scroll_area, label)
                if _key == "mame":
                    self._build_mame_tab(page)
            category_layout.addWidget(tabs)
            self.category_tabs.addTab(category_page, category)
        root.addWidget(self.category_tabs, 1)

    def _build_mame_tab(self, _page: QWidget) -> None:
        """Hook for the MAME executable selector supplied by DirectoriesPage."""

    def _build_emulator_directory_settings(self, _emulator: str, _page: QWidget) -> None:
        """Hook for emulator-specific paths stored inside its configuration file."""

    def _browse(self, config_key: str) -> None:
        current = self._fields[config_key].text()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar arquivo de configuração",
            str(Path(current).parent) if current else str(Path.home()),
            "Arquivos de configuração (*.ini *.cfg *.conf *.bml);;Todos os arquivos (*)",
        )
        if not path:
            return
        data = self._load_json(self.PATHS_FILE)
        data[config_key] = str(Path(path).resolve())
        self._save_json(self.PATHS_FILE, data)
        self.refresh()

    @staticmethod
    def _executable_key(emulator: str) -> str:
        if emulator == "mame":
            return "mame_executable"
        return f"{emulator}_exe"

    def _browse_executable(self, emulator: str) -> None:
        key = self._executable_key(emulator)
        current = self._load_json(self.PATHS_FILE).get(key)
        start = str(Path(str(current)).parent) if current else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Selecionar executável do {dict((item, label) for item, label, _ in self.EMULATORS)[emulator]}",
            start,
            "Executáveis (*.exe);;Todos os arquivos (*)",
        )
        if not path:
            return
        executable = Path(path).resolve()
        if not executable.is_file() or executable.suffix.casefold() != ".exe":
            return
        data = self._load_json(self.PATHS_FILE)
        data[key] = str(executable)
        self._save_json(self.PATHS_FILE, data)
        self.refresh()

    def _browse_directory(self, emulator: str) -> None:
        current = self._directory_fields[emulator].text()
        selected = get_existing_directory(
            self,
            f"Selecionar diretório do {dict((key, label) for key, label, _ in self.EMULATORS)[emulator]}",
            current or str(Path.home()),
        )
        if not selected:
            return
        data = self._load_json(self.PATHS_FILE)
        data[emulator] = str(Path(selected).resolve())
        if emulator == "altirra":
            config_file = Path(selected) / "Altirra.ini"
            if config_file.is_file():
                data["altirra_config"] = str(config_file.resolve())
        elif emulator == "amiberry":
            for key, candidate in (
                ("amiberry_exe", Path(selected) / "Amiberry.exe"),
                ("amiberry_ini", Path(selected) / "Settings" / "amiberry.ini"),
                ("amiberry_conf", Path(selected) / "Settings" / "amiberry.conf"),
            ):
                if candidate.is_file():
                    data[key] = str(candidate.resolve())
            if not data.get("amiberry_conf"):
                candidate = Path(selected) / "amiberry.conf"
                if candidate.is_file():
                    data["amiberry_conf"] = str(candidate.resolve())
        elif emulator == "winuae":
            for key, candidate in (
                ("winuae_ini", Path(selected) / "winuae.ini"),
                ("winuae_cache", Path(selected) / "configuration.cache"),
            ):
                if candidate.is_file():
                    data[key] = str(candidate.resolve())
        elif emulator == "ares":
            candidate = Path(selected) / "settings.bml"
            if candidate.is_file():
                data["ares_config"] = str(candidate.resolve())
            for name in ("Database", "hiro", "Nintendo 64", "Shaders", "Systems"):
                candidate_dir = Path(selected) / name
                if candidate_dir.is_dir():
                    data[f"ares_{name.casefold().replace(' ', '_')}"] = str(candidate_dir.resolve())
        elif emulator == "azahar":
            candidate = Path(selected) / "user" / "config" / "qt-config.ini"
            if candidate.is_file():
                data["azahar_config"] = str(candidate.resolve())
        self._save_json(self.PATHS_FILE, data)
        self.refresh()

    def refresh(self) -> None:
        data = self._load_json(self.PATHS_FILE)
        for emulator, field in self._directory_fields.items():
            field.setText(str(data.get(emulator) or ""))
        for config_key, field in self._fields.items():
            field.setText(str(data.get(config_key) or ""))
        for executable_key, field in self._executable_fields.items():
            field.setText(str(data.get(executable_key) or ""))


__all__ = ["ConfigFileEditor", "DirectoryGuidePage"]
