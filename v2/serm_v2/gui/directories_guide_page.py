"""Safe, editable emulator directory configuration for SERM V2."""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..integrations.launchbox import LaunchBoxIntegration
from ..runtime.paths import data_root, integrations_root
from ..services.emulator_manager import EmulatorManager


class ConfigFileEditor:
    """Edit only selected path-value lines while preserving config structure."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.encoding = "utf-8"
        self.newline = "\n"
        self._raw: bytes = b""
        self._text = ""
        self.reload()

    def reload(self) -> None:
        """Load the file and detect encoding/newline style without normalizing it."""
        self._raw = self.path.read_bytes()
        if self._raw.startswith(b"\xef\xbb\xbf"):
            self.encoding = "utf-8-sig"
        else:
            try:
                self._raw.decode("utf-8")
                self.encoding = "utf-8"
            except UnicodeDecodeError:
                self.encoding = "cp1252"
        self._text = self._raw.decode(self.encoding, errors="replace")
        if "\r\n" in self._text:
            self.newline = "\r\n"
        elif "\r" in self._text and "\n" not in self._text:
            self.newline = "\r"
        else:
            self.newline = "\n"

    def values(self, key: str, *, indexed: bool = False) -> list[str]:
        """Read all values for a configuration key, preserving their order."""
        result: list[str] = []
        pattern = self._key_pattern(key, indexed=indexed)
        for line in self._text.splitlines():
            if match := pattern.match(line):
                result.append(match.group("value").strip().strip('"'))
        return result

    def set_value(self, key: str, value: str, *, indexed: bool = False, index: int | None = None, separator: str = " ") -> None:
        """Replace one matching value in-place, preserving comments and spacing."""
        lines = self._text.splitlines(keepends=True)
        pattern = self._key_pattern(key, indexed=indexed)
        seen = 0
        for pos, line in enumerate(lines):
            match = pattern.match(line.rstrip("\r\n"))
            if not match:
                continue
            if index is not None and seen != index:
                seen += 1
                continue
            prefix = match.group("prefix")
            suffix = match.group("suffix")
            ending = line[len(line.rstrip("\r\n")) :]
            raw_value = match.group("value").strip()
            quoted = len(raw_value) >= 2 and raw_value[0] == '"' and raw_value[-1] == '"'
            formatted = self._format_value(value, separator=separator)
            if quoted:
                formatted = '"' + formatted.replace('"', "'") + '"'
            lines[pos] = f"{prefix}{formatted}{suffix}{ending}"
            self._text = "".join(lines)
            return
        raise KeyError(f"Configuração não encontrada: {key}[{index}]")

    def save(self, *, backup_dir: Path | None = None) -> Path:
        """Create a timestamped backup and atomically replace the original file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        backup_root = backup_dir or (self.path.parent / ".serm-backups")
        backup_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = backup_root / f"{self.path.name}.{stamp}.bak"
        shutil.copy2(self.path, backup)
        data = self._text.encode(self.encoding, errors="replace")
        fd, tmp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise
        return backup

    @staticmethod
    def _format_value(value: str, *, separator: str = " ") -> str:
        """Return the selected value without changing its semantic content."""
        return value

    @staticmethod
    def _key_pattern(key: str, *, indexed: bool) -> re.Pattern[str]:
        """Build a tolerant pattern for supported emulator configuration lines."""
        escaped = re.escape(key)
        key_expr = rf"{escaped}\[\d+\]" if indexed else escaped
        return re.compile(rf"^(?P<prefix>\s*{key_expr}\s*(?:=\s*|\s+))(?P<value>.*?)(?P<suffix>\s*(?:#.*)?)$")


class PathListWidget(QWidget):
    """Display folders with add/remove controls based on QFileDialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.list = QListWidget()
        add = QPushButton("Adicionar pasta")
        remove = QPushButton("Remover selecionada")
        add.clicked.connect(self.add_folder)
        remove.clicked.connect(self.remove_selected)
        buttons = QHBoxLayout()
        buttons.setSpacing(5)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addWidget(self.list)
        layout.addLayout(buttons)
        self.setStyleSheet(
            "QPushButton{max-width:150px;min-height:25px;padding:3px 10px;}"
            "QListWidget{min-height:58px;}"
        )

    def set_paths(self, paths: Iterable[str]) -> None:
        """Replace the displayed folder list."""
        self.list.clear()
        for path in paths:
            if path:
                self.list.addItem(str(path))

    def paths(self) -> list[str]:
        """Return the displayed folders in their current order."""
        return [self.list.item(i).text().strip() for i in range(self.list.count())]

    def add_folder(self) -> None:
        """Select and append one directory."""
        if selected := QFileDialog.getExistingDirectory(self, "Selecionar diretório", str(Path.home())):
            self.list.addItem(str(Path(selected).resolve()))

    def remove_selected(self) -> None:
        """Remove the currently selected directory."""
        row = self.list.currentRow()
        if row >= 0:
            self.list.takeItem(row)


class DirectoryGuidePage(QWidget):
    """Configure emulator directories through safe, format-preserving edits."""

    DIRECTORY_GROUP_TITLE = "Diretórios"
    FBNEO_ROMS_STORAGE = "fbneo:roms"
    SUPERMODEL_ROMS_STORAGE = "supermodel:roms"
    PATHS_FILE = data_root() / "emulator_paths.json"
    TOOLS_FILE = integrations_root() / "tools.json"
    EXECUTABLES = EmulatorManager.EXECUTABLES
    LABELS = EmulatorManager.LABELS
    RETROARCH_KEYS = (("content", "Conteúdo / ROMs", "content_directory"), ("system", "System / BIOS", "system_directory"), ("cores", "Cores libretro", "libretro_directory"), ("info", "Informações dos cores", "libretro_info_path"), ("assets", "Assets", "assets_directory"), ("core_assets", "Core assets", "core_assets_directory"), ("saves", "Saves", "savefile_directory"), ("states", "States", "savestate_directory"), ("screenshots", "Screenshots", "screenshot_directory"), ("shaders", "Shaders", "video_shader_dir"), ("cache", "Cache", "cache_directory"), ("playlists", "Playlists", "playlist_directory"), ("remaps", "Remaps", "input_remapping_directory"), ("autoconfig", "Autoconfig", "joypad_autoconfig_dir"), ("overlays", "Overlays", "overlay_directory"), ("thumbnails", "Thumbnails", "thumbnails_directory"), ("recordings", "Gravações", "recording_output_directory"), ("logs", "Logs", "log_dir"))
    MAME_KEYS = (("home", "Home", "homepath"), ("rompath", "ROMs", "rompath"), ("hash", "Hash", "hashpath"), ("samples", "Samples", "samplepath"), ("artwork", "Artwork", "artpath"), ("ctrlr", "Controladores", "ctrlrpath"), ("ini", "INIs", "inipath"), ("font", "Fontes", "fontpath"), ("cheat", "Cheats", "cheatpath"), ("crosshair", "Crosshair", "crosshairpath"), ("plugins", "Plugins", "pluginspath"), ("language", "Idiomas", "languagepath"), ("software", "Software lists", "swpath"), ("cfg", "Configurações por jogo", "cfg_directory"), ("nvram", "NVRAM", "nvram_directory"), ("input", "Inputs", "input_directory"), ("state", "States", "state_directory"), ("snapshot", "Snapshots", "snapshot_directory"), ("diff", "Diff", "diff_directory"), ("comments", "Comentários", "comment_directory"), ("share", "Share", "share_directory"))
    FBNEO_KEYS = (("neocd", "Neo Geo CD ISO", "szNeoCDGamesDir"), ("previews", "Previews", "szAppPreviewsPath"), ("titles", "Titles", "szAppTitlesPath"), ("cheats", "Cheats", "szAppCheatsPath"), ("hiscores", "Hiscores", "szAppHiscorePath"), ("samples", "Samples", "szAppSamplesPath"), ("hdd", "HDD", "szAppHDDPath"), ("ips", "IPS", "szAppIpsPath"), ("romdata", "ROM data", "szAppRomdataPath"), ("icons", "Icons", "szAppIconsPath"), ("cabinets", "Cabinets", "szAppCabinetsPath"), ("history", "History", "szAppHistoryPath"), ("commands", "Commands", "szAppCommandPath"), ("eeprom", "EEPROM / game config", "szAppEEPROMPath"))
    FLYCAST_KEYS = (("bios", "BIOS", "Dreamcast.BiosPath", True), ("boxart", "Boxart", "Dreamcast.BoxartPath", False), ("cheats", "Cheats", "Dreamcast.CheatPath", True), ("content", "Conteúdo / ROMs", "Dreamcast.ContentPath", True), ("mappings", "Mappings", "Dreamcast.MappingsPath", True), ("save", "Saves", "Dreamcast.SavePath", False), ("states", "Savestates", "Dreamcast.SavestatePath", True), ("textures", "Textures", "Dreamcast.TexturePath", True), ("vmu", "VMU", "Dreamcast.VMUPath", False), ("texture_dump", "Texture dump", "Dreamcast.TextureDumpPath", False))

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.launchbox = LaunchBoxIntegration()
        self._config_edits: dict[str, QLineEdit] = {}
        self._path_edits: dict[str, QLineEdit] = {}
        self._path_lists: dict[str, PathListWidget] = {}
        self._build_ui()
        self.refresh()

    @staticmethod
    def _load_json(path: Path) -> dict[str, object]:
        """Load SERM's persisted mapping safely."""
        try:
            value = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, ValueError, TypeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _save_json(path: Path, data: dict[str, object]) -> None:
        """Persist SERM-owned JSON atomically."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise

    @staticmethod
    def _config_base(config_path: Path, emulator: str) -> Path:
        """Return the native base used for relative paths in an emulator config."""
        if emulator in {"fbneo", "supermodel"} and config_path.parent.name.casefold() == "config":
            return config_path.parent.parent.resolve()
        return config_path.parent.resolve()

    @classmethod
    def _resolve_path(cls, raw: str, config_path: Path, *, emulator: str, retroarch: bool = False) -> str:
        """Resolve a configured path for display without changing its native meaning."""
        value = raw.strip().strip('"')
        if not value:
            return ""
        if value.casefold() == "default":
            return "default"
        base = cls._config_base(config_path, emulator)
        if retroarch and value.startswith(":\\"):
            suffix = value[2:].lstrip("\\/")
            return str((base / suffix).resolve()) if suffix else str(base)
        path = Path(value).expanduser()
        return str(path) if path.is_absolute() else str((base / path).resolve())

    @classmethod
    def _encode_path(cls, path: str, config_path: Path, original: str, *, emulator: str, retroarch: bool = False) -> str:
        """Encode a selected folder while preserving relative-path conventions."""
        selected = Path(path).expanduser().resolve()
        original = original.strip().strip('"')
        base = cls._config_base(config_path, emulator)
        if retroarch and original.startswith(":\\"):
            try:
                rel = selected.relative_to(base)
                return ":\\" + str(rel).replace("/", "\\")
            except ValueError:
                return str(selected)
        if original and not Path(original).is_absolute() and original.casefold() != "default":
            try:
                rel = selected.relative_to(base)
                return str(rel).replace("\\", "/")
            except ValueError:
                return str(selected)
        return str(selected)

    def _build_ui(self) -> None:
        """Build only emulator directory tabs; auxiliary executables live in Tools."""
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        title = QLabel("Diretórios dos Emuladores")
        title.setStyleSheet("font-size:17px;font-weight:700;")
        root.addWidget(title)
        info = QLabel("Configure apenas pastas e arquivos pertencentes às instalações e aos dados dos emuladores. Executáveis auxiliares do SERM ficam em Ferramentas.")
        info.setWordWrap(True)
        root.addWidget(info)
        self.tabs = QTabWidget()
        for key, label in (("mame", "MAME"), ("fbneo", "FBNeo"), ("flycast", "Flycast"), ("supermodel", "Supermodel"), ("retroarch", "RetroArch")):
            page = QWidget()
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.tabs.addTab(scroll, label)
            getattr(self, f"_build_{key}_tab")(page)
        root.addWidget(self.tabs, 1)
        self.setStyleSheet(
            "QPushButton{min-height:25px;padding:3px 10px;max-width:155px;}"
            "QLineEdit{min-height:25px;padding:2px 7px;}"
            "QFormLayout{}"
        )

    def _config_header(self, layout: QVBoxLayout, key: str, title: str) -> None:
        """Create the configuration-file selector and save controls."""
        group = QGroupBox(title)
        form = QFormLayout(group)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(5)
        edit = QLineEdit()
        edit.setReadOnly(True)
        select = QPushButton("Selecionar arquivo")
        select.clicked.connect(lambda: self.select_config(key))
        row = QHBoxLayout()
        row.setSpacing(5)
        row.addWidget(edit, 1)
        row.addWidget(select, 0)
        form.addRow("Arquivo:", row)
        save = QPushButton("💾 Salvar diretórios")
        save.clicked.connect(lambda: self.save_config(key))
        save.setMaximumWidth(170)
        form.addRow("", save)
        layout.addWidget(group)
        self._config_edits[key] = edit

    def _add_single(self, form: QFormLayout, storage: str, label: str) -> None:
        """Add one folder field controlled by QFileDialog."""
        edit = QLineEdit()
        edit.setReadOnly(True)
        button = QPushButton("Selecionar pasta")
        button.clicked.connect(lambda: self.select_single(storage))
        row = QHBoxLayout()
        row.setSpacing(5)
        row.addWidget(edit, 1)
        row.addWidget(button, 0)
        form.addRow(f"{label}:", row)
        self._path_edits[storage] = edit

    def _add_list(self, form: QFormLayout, storage: str, label: str) -> None:
        """Add a multi-folder field with add/remove controls."""
        widget = PathListWidget()
        form.addRow(f"{label}:", widget)
        self._path_lists[storage] = widget

    def _build_mame_tab(self, page: QWidget) -> None:
        """Build MAME's directory fields, including multi-root search paths."""
        layout = QVBoxLayout(page)
        self._config_header(layout, "mame", "mame.ini")
        group = QGroupBox(self.DIRECTORY_GROUP_TITLE)
        form = QFormLayout(group)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(5)
        for key, label, _ in self.MAME_KEYS:
            storage = f"mame:{key}"
            if key in {"rompath", "hash", "samples", "artwork", "ctrlr", "ini"}:
                self._add_list(form, storage, label)
            else:
                self._add_single(form, storage, label)
        layout.addWidget(group)
        note = QLabel("MAME aceita múltiplas raízes em search paths separados por ';'. A ordem é preservada.")
        note.setWordWrap(True)
        layout.addWidget(note)

    def _build_fbneo_tab(self, page: QWidget) -> None:
        """Build FBNeo's indexed ROM paths and support directories."""
        layout = QVBoxLayout(page)
        self._config_header(layout, "fbneo", "fbneo64.ini")
        group = QGroupBox(self.DIRECTORY_GROUP_TITLE)
        form = QFormLayout(group)
        form.setVerticalSpacing(5)
        self._add_list(form, self.FBNEO_ROMS_STORAGE, "ROMs")
        for key, label, _ in self.FBNEO_KEYS:
            self._add_single(form, f"fbneo:{key}", label)
        layout.addWidget(group)
        note = QLabel("Os slots szAppRomPaths[0..19] existentes são preservados; remover uma pasta apenas limpa o slot correspondente.")
        note.setWordWrap(True)
        layout.addWidget(note)

    def _build_flycast_tab(self, page: QWidget) -> None:
        """Build Flycast scalar and vector directory options."""
        layout = QVBoxLayout(page)
        self._config_header(layout, "flycast", "emu.cfg")
        group = QGroupBox(self.DIRECTORY_GROUP_TITLE)
        form = QFormLayout(group)
        form.setVerticalSpacing(5)
        for key, label, _, multi in self.FLYCAST_KEYS:
            storage = f"flycast:{key}"
            if multi:
                self._add_list(form, storage, label)
            else:
                self._add_single(form, storage, label)
        layout.addWidget(group)
        note = QLabel("Opções vetoriais do Flycast são apresentadas como listas; opções escalares continuam como uma única pasta.")
        note.setWordWrap(True)
        layout.addWidget(note)

    def _build_supermodel_tab(self, page: QWidget) -> None:
        """Build Supermodel's ROM directory field."""
        layout = QVBoxLayout(page)
        self._config_header(layout, "supermodel", "Supermodel.ini")
        group = QGroupBox(self.DIRECTORY_GROUP_TITLE)
        form = QFormLayout(group)
        self._add_single(form, self.SUPERMODEL_ROMS_STORAGE, "ROMs")
        layout.addWidget(group)
        note = QLabel("GameXMLFile e InitStateFile são arquivos e não são editados nesta guia.")
        note.setWordWrap(True)
        layout.addWidget(note)

    def _build_retroarch_tab(self, page: QWidget) -> None:
        """Build RetroArch directory fields using native configuration keys."""
        layout = QVBoxLayout(page)
        self._config_header(layout, "retroarch", "retroarch.cfg")
        group = QGroupBox(self.DIRECTORY_GROUP_TITLE)
        form = QFormLayout(group)
        form.setVerticalSpacing(5)
        for key, label, _ in self.RETROARCH_KEYS:
            self._add_single(form, f"retroarch:{key}", label)
        layout.addWidget(group)
        note = QLabel("Valores :\\... continuam relativos à instalação quando possível. Valores absolutos permanecem absolutos. O valor especial 'default' não é convertido até o usuário escolher uma pasta.")
        note.setWordWrap(True)
        layout.addWidget(note)

    def _build_tools_tab(self, page: QWidget) -> None:
        """Retained only for compatibility; tools are no longer part of Directories."""
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Ferramentas auxiliares"))
        layout.addWidget(QLabel("Esta seção foi movida para a área Ferramentas da Configuração."))


__all__ = ["ConfigFileEditor", "PathListWidget", "DirectoryGuidePage"]
