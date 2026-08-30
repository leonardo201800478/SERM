"""Safe, editable emulator directory configuration for SERM V2."""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
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
            match = pattern.match(line)
            if match:
                result.append(match.group("value").strip().strip('"'))
        return result

    def set_value(
        self,
        key: str,
        value: str,
        *,
        indexed: bool = False,
        index: int | None = None,
        separator: str = " ",
    ) -> None:
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
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
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
        return re.compile(
            rf"^(?P<prefix>\s*{key_expr}\s*(?:=\s*|\s+))"
            rf"(?P<value>.*?)"
            rf"(?P<suffix>\s*(?:[;#].*)?)$"
        )


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
        buttons.addWidget(add)
        buttons.addWidget(remove)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list)
        layout.addLayout(buttons)

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
        selected = QFileDialog.getExistingDirectory(
            self,
            "Selecionar diretório",
            str(Path.home()),
        )
        if selected:
            self.list.addItem(str(Path(selected).resolve()))

    def remove_selected(self) -> None:
        """Remove the currently selected directory."""
        row = self.list.currentRow()
        if row >= 0:
            self.list.takeItem(row)


class DirectoryGuidePage(QWidget):
    """Configure emulator directories through safe, format-preserving edits."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    TOOLS_FILE = integrations_root() / "tools.json"
    EXECUTABLES = EmulatorManager.EXECUTABLES
    LABELS = EmulatorManager.LABELS

    RETROARCH_KEYS = (
        ("content", "Conteúdo / ROMs", "content_directory"),
        ("system", "System / BIOS", "system_directory"),
        ("cores", "Cores libretro", "libretro_directory"),
        ("info", "Informações dos cores", "libretro_info_path"),
        ("assets", "Assets", "assets_directory"),
        ("core_assets", "Core assets", "core_assets_directory"),
        ("saves", "Saves", "savefile_directory"),
        ("states", "States", "savestate_directory"),
        ("screenshots", "Screenshots", "screenshot_directory"),
        ("shaders", "Shaders", "video_shader_dir"),
        ("cache", "Cache", "cache_directory"),
        ("playlists", "Playlists", "playlist_directory"),
        ("remaps", "Remaps", "input_remapping_directory"),
        ("autoconfig", "Autoconfig", "joypad_autoconfig_dir"),
        ("overlays", "Overlays", "overlay_directory"),
        ("thumbnails", "Thumbnails", "thumbnails_directory"),
        ("recordings", "Gravações", "recording_output_directory"),
        ("logs", "Logs", "log_dir"),
    )
    MAME_KEYS = (
        ("home", "Home", "homepath"),
        ("rompath", "ROMs", "rompath"),
        ("hash", "Hash", "hashpath"),
        ("samples", "Samples", "samplepath"),
        ("artwork", "Artwork", "artpath"),
        ("ctrlr", "Controladores", "ctrlrpath"),
        ("ini", "INIs", "inipath"),
        ("font", "Fontes", "fontpath"),
        ("cheat", "Cheats", "cheatpath"),
        ("crosshair", "Crosshair", "crosshairpath"),
        ("plugins", "Plugins", "pluginspath"),
        ("language", "Idiomas", "languagepath"),
        ("software", "Software lists", "swpath"),
        ("cfg", "Configurações por jogo", "cfg_directory"),
        ("nvram", "NVRAM", "nvram_directory"),
        ("input", "Inputs", "input_directory"),
        ("state", "States", "state_directory"),
        ("snapshot", "Snapshots", "snapshot_directory"),
        ("diff", "Diff", "diff_directory"),
        ("comments", "Comentários", "comment_directory"),
        ("share", "Share", "share_directory"),
    )
    FBNEO_KEYS = (
        ("neocd", "Neo Geo CD ISO", "szNeoCDGamesDir"),
        ("previews", "Previews", "szAppPreviewsPath"),
        ("titles", "Titles", "szAppTitlesPath"),
        ("cheats", "Cheats", "szAppCheatsPath"),
        ("hiscores", "Hiscores", "szAppHiscorePath"),
        ("samples", "Samples", "szAppSamplesPath"),
        ("hdd", "HDD", "szAppHDDPath"),
        ("ips", "IPS", "szAppIpsPath"),
        ("romdata", "ROM data", "szAppRomdataPath"),
        ("icons", "Icons", "szAppIconsPath"),
        ("cabinets", "Cabinets", "szAppCabinetsPath"),
        ("history", "History", "szAppHistoryPath"),
        ("commands", "Commands", "szAppCommandPath"),
        ("eeprom", "EEPROM / game config", "szAppEEPROMPath"),
    )
    FLYCAST_KEYS = (
        ("bios", "BIOS", "Dreamcast.BiosPath", True),
        ("boxart", "Boxart", "Dreamcast.BoxartPath", False),
        ("cheats", "Cheats", "Dreamcast.CheatPath", True),
        ("content", "Conteúdo / ROMs", "Dreamcast.ContentPath", True),
        ("mappings", "Mappings", "Dreamcast.MappingsPath", True),
        ("save", "Saves", "Dreamcast.SavePath", False),
        ("states", "Savestates", "Dreamcast.SavestatePath", True),
        ("textures", "Textures", "Dreamcast.TexturePath", True),
        ("vmu", "VMU", "Dreamcast.VMUPath", False),
        ("texture_dump", "Texture dump", "Dreamcast.TextureDumpPath", False),
    )

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
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    @staticmethod
    def _config_base(config_path: Path, emulator: str) -> Path:
        """Return the native base used for relative paths in an emulator config."""
        if emulator in {"fbneo", "supermodel"} and config_path.parent.name.casefold() == "config":
            return config_path.parent.parent.resolve()
        return config_path.parent.resolve()

    @classmethod
    def _resolve_path(
        cls,
        raw: str,
        config_path: Path,
        *,
        emulator: str,
        retroarch: bool = False,
    ) -> str:
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
        if path.is_absolute():
            return str(path)
        return str((base / path).resolve())

    @classmethod
    def _encode_path(
        cls,
        path: str,
        config_path: Path,
        original: str,
        *,
        emulator: str,
        retroarch: bool = False,
    ) -> str:
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
        """Build the emulator-specific directory tabs."""
        root = QVBoxLayout(self)
        title = QLabel("Diretórios dos Emuladores")
        title.setStyleSheet("font-size:22px;font-weight:bold;")
        root.addWidget(title)
        info = QLabel(
            "Selecione pastas pelos botões. O SERM altera somente as linhas de diretório necessárias, "
            "preserva comentários/ordem/formatação e cria um backup antes de gravar."
        )
        info.setWordWrap(True)
        root.addWidget(info)
        self.tabs = QTabWidget()
        for key, label in (
            ("mame", "MAME"),
            ("fbneo", "FBNeo"),
            ("flycast", "Flycast"),
            ("supermodel", "Supermodel"),
            ("retroarch", "RetroArch"),
            ("tools", "Ferramentas"),
        ):
            page = QWidget()
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.tabs.addTab(scroll, label)
            getattr(self, f"_build_{key}_tab")(page)
        root.addWidget(self.tabs, 1)

    def _config_header(self, layout: QVBoxLayout, key: str, title: str) -> None:
        """Create the configuration-file selector and save controls."""
        group = QGroupBox(title)
        form = QFormLayout(group)
        edit = QLineEdit()
        edit.setReadOnly(True)
        select = QPushButton("Selecionar arquivo")
        select.clicked.connect(lambda: self.select_config(key))
        row = QHBoxLayout()
        row.addWidget(edit, 1)
        row.addWidget(select)
        form.addRow("Arquivo:", row)
        save = QPushButton("💾 Salvar diretórios")
        save.clicked.connect(lambda: self.save_config(key))
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
        row.addWidget(edit, 1)
        row.addWidget(button)
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
        group = QGroupBox("Diretórios")
        form = QFormLayout(group)
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
        group = QGroupBox("Diretórios")
        form = QFormLayout(group)
        self._add_list(form, "fbneo:roms", "ROMs")
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
        group = QGroupBox("Diretórios")
        form = QFormLayout(group)
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
        group = QGroupBox("Diretórios")
        form = QFormLayout(group)
        self._add_single(form, "supermodel:roms", "ROMs")
        layout.addWidget(group)
        note = QLabel("GameXMLFile e InitStateFile são arquivos e não são editados nesta guia.")
        note.setWordWrap(True)
        layout.addWidget(note)

    def _build_retroarch_tab(self, page: QWidget) -> None:
        """Build RetroArch directory fields using native configuration keys."""
        layout = QVBoxLayout(page)
        self._config_header(layout, "retroarch", "retroarch.cfg")
        group = QGroupBox("Diretórios")
        form = QFormLayout(group)
        for key, label, _ in self.RETROARCH_KEYS:
            self._add_single(form, f"retroarch:{key}", label)
        layout.addWidget(group)
        note = QLabel(
            "Valores :\\... continuam relativos à instalação quando possível. Valores absolutos permanecem absolutos. "
            "O valor especial 'default' não é convertido até o usuário escolher uma pasta."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

    def _build_tools_tab(self, page: QWidget) -> None:
        """Build SERM-owned auxiliary executable paths."""
        layout = QVBoxLayout(page)
        group = QGroupBox("Ferramentas auxiliares")
        form = QFormLayout(group)
        self.launchbox_edit = QLineEdit()
        self.launchbox_edit.setReadOnly(True)
        lb = QPushButton("Selecionar LaunchBox.exe")
        lb.clicked.connect(self.select_launchbox)
        row = QHBoxLayout()
        row.addWidget(self.launchbox_edit, 1)
        row.addWidget(lb)
        form.addRow("LaunchBox:", row)
        self.sevenzip_edit = QLineEdit()
        self.sevenzip_edit.setReadOnly(True)
        sz = QPushButton("Selecionar 7z.exe")
        sz.clicked.connect(self.select_7zip)
        row2 = QHBoxLayout()
        row2.addWidget(self.sevenzip_edit, 1)
        row2.addWidget(sz)
        form.addRow("7-Zip:", row2)
        layout.addWidget(group)
        layout.addStretch()

    def select_config(self, key: str) -> None:
        """Select a config file and persist its location in SERM's own JSON."""
        filters = {
            "mame": "MAME INI (*.ini);;Todos os arquivos (*)",
            "fbneo": "FBNeo INI (*.ini);;Todos os arquivos (*)",
            "flycast": "Flycast CFG (*.cfg);;Todos os arquivos (*)",
            "supermodel": "Supermodel INI (*.ini);;Todos os arquivos (*)",
            "retroarch": "RetroArch CFG (*.cfg);;Todos os arquivos (*)",
        }
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar configuração",
            str(Path.home()),
            filters[key],
        )
        if not path:
            return
        config = Path(path).resolve()
        data = self._load_json(self.PATHS_FILE)
        data[self._config_key(key)] = str(config)
        data[key] = str(self._infer_root(key, config))
        self._save_json(self.PATHS_FILE, data)
        self.refresh()

    def select_single(self, storage: str) -> None:
        """Select a folder for a scalar field without touching the config yet."""
        current = self._path_edits[storage].text()
        selected = QFileDialog.getExistingDirectory(
            self,
            "Selecionar diretório",
            current or str(Path.home()),
        )
        if selected:
            self._path_edits[storage].setText(str(Path(selected).resolve()))

    def select_launchbox(self) -> None:
        """Select and persist LaunchBox.exe through the existing integration."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar LaunchBox.exe",
            str(Path.home()),
            "LaunchBox (LaunchBox.exe);;Executáveis (*.exe)",
        )
        if path:
            self.launchbox.set_executable(Path(path).resolve())
            self.refresh()

    def select_7zip(self) -> None:
        """Select and persist 7-Zip's command-line executable."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar 7z.exe",
            str(Path.home()),
            "7-Zip (7z.exe);;Executáveis (*.exe)",
        )
        if path:
            data = self._load_json(self.TOOLS_FILE)
            data["sevenzip"] = str(Path(path).resolve())
            self._save_json(self.TOOLS_FILE, data)
            self.refresh()

    def _config_key(self, key: str) -> str:
        """Return the persisted SERM key for an emulator config."""
        return {
            "mame": "mame_config",
            "fbneo": "fbneo_config",
            "flycast": "flycast_config",
            "supermodel": "supermodel_config",
            "retroarch": "retroarch_cfg",
        }[key]

    def _infer_root(self, key: str, config: Path) -> Path:
        """Infer the emulator installation root from its config location."""
        if key in {"fbneo", "supermodel"} and config.parent.name.casefold() == "config":
            return config.parent.parent
        return config.parent

    def _load_editor(self, key: str) -> ConfigFileEditor | None:
        """Load the configured text file if it exists."""
        data = self._load_json(self.PATHS_FILE)
        raw = data.get(self._config_key(key))
        if not raw:
            return None
        path = Path(str(raw)).expanduser()
        if not path.is_file():
            return None
        try:
            return ConfigFileEditor(path)
        except OSError:
            return None

    def save_config(self, key: str) -> None:
        """Validate, back up and atomically save only supported directory settings."""
        data = self._load_json(self.PATHS_FILE)
        raw_config = data.get(self._config_key(key))
        if not raw_config:
            QMessageBox.warning(self, "Configuração", "Selecione primeiro o arquivo de configuração.")
            return
        config = Path(str(raw_config)).expanduser()
        if not config.is_file():
            QMessageBox.warning(self, "Configuração", f"Arquivo não encontrado:\n{config}")
            return
        answer = QMessageBox.question(
            self,
            "Confirmar alteração",
            "O SERM criará um backup e alterará somente as linhas de diretório suportadas.\n\nContinuar?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            editor = ConfigFileEditor(config)
            if key == "mame":
                self._save_mame(editor, config)
            elif key == "fbneo":
                self._save_fbneo(editor, config)
            elif key == "flycast":
                self._save_flycast(editor, config)
            elif key == "supermodel":
                self._save_supermodel(editor, config)
            elif key == "retroarch":
                self._save_retroarch(editor, config)
            backup = editor.save()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Falha ao salvar",
                f"Nenhuma alteração foi concluída com segurança.\n\n{exc}",
            )
            return
        self.refresh()
        QMessageBox.information(
            self,
            "Configuração salva",
            f"Alteração concluída.\nBackup criado em:\n{backup}",
        )

    def _save_mame(self, editor: ConfigFileEditor, config: Path) -> None:
        """Write MAME paths while retaining relative/absolute representation."""
        multi = {"rompath", "hash", "samples", "artwork", "ctrlr", "ini"}
        for key, _, cfg_key in self.MAME_KEYS:
            storage = f"mame:{key}"
            current = editor.values(cfg_key)
            if not current:
                continue
            if key in multi:
                old_parts = current[0].split(";")
                values = self._path_lists[storage].paths()
                encoded = [
                    self._encode_path(
                        value,
                        config,
                        old_parts[i] if i < len(old_parts) else "",
                        emulator="mame",
                    )
                    for i, value in enumerate(values)
                ]
                editor.set_value(cfg_key, ";".join(encoded))
            else:
                value = self._path_edits[storage].text().strip()
                if value:
                    editor.set_value(
                        cfg_key,
                        self._encode_path(value, config, current[0], emulator="mame"),
                    )

    def _save_fbneo(self, editor: ConfigFileEditor, config: Path) -> None:
        """Write FBNeo indexed ROM paths and scalar support directories."""
        current_roms = editor.values("szAppRomPaths", indexed=True)
        selected = self._path_lists["fbneo:roms"].paths()
        for index, old in enumerate(current_roms):
            value = selected[index] if index < len(selected) else ""
            encoded = (
                self._encode_path(value, config, old, emulator="fbneo")
                if value
                else ""
            )
            editor.set_value("szAppRomPaths", encoded, indexed=True, index=index)
        for key, _, cfg_key in self.FBNEO_KEYS:
            current = editor.values(cfg_key)
            value = self._path_edits[f"fbneo:{key}"].text().strip()
            if current and value:
                editor.set_value(
                    cfg_key,
                    self._encode_path(value, config, current[0], emulator="fbneo"),
                )

    def _save_flycast(self, editor: ConfigFileEditor, config: Path) -> None:
        """Write Flycast path options while retaining their existing key syntax."""
        for key, _, cfg_key, multi in self.FLYCAST_KEYS:
            current = editor.values(cfg_key)
            if not current:
                continue
            storage = f"flycast:{key}"
            if multi:
                selected = self._path_lists[storage].paths()
                original_parts = self._split_vector(current[0])
                encoded = [
                    self._encode_path(
                        value,
                        config,
                        original_parts[i] if i < len(original_parts) else "",
                        emulator="flycast",
                    )
                    for i, value in enumerate(selected)
                ]
                editor.set_value(cfg_key, ";".join(encoded))
            else:
                value = self._path_edits[storage].text().strip()
                if value:
                    editor.set_value(
                        cfg_key,
                        self._encode_path(value, config, current[0], emulator="flycast"),
                    )

    def _save_supermodel(self, editor: ConfigFileEditor, config: Path) -> None:
        """Write only Supermodel's ROM directory setting."""
        current = editor.values("RomsDirectory")
        value = self._path_edits["supermodel:roms"].text().strip()
        if current and value:
            editor.set_value(
                "RomsDirectory",
                self._encode_path(value, config, current[0], emulator="supermodel"),
            )

    def _save_retroarch(self, editor: ConfigFileEditor, config: Path) -> None:
        """Write RetroArch directory keys while preserving quotes and :\\ semantics."""
        for key, _, cfg_key in self.RETROARCH_KEYS:
            current = editor.values(cfg_key)
            value = self._path_edits[f"retroarch:{key}"].text().strip()
            if not current or not value or value.casefold() == "default":
                continue
            editor.set_value(
                cfg_key,
                self._encode_path(
                    value,
                    config,
                    current[0],
                    emulator="retroarch",
                    retroarch=True,
                ),
            )

    @staticmethod
    def _split_vector(value: str) -> list[str]:
        """Split a multi-path value without altering its path contents."""
        if ";" in value:
            return [part.strip().strip('"') for part in value.split(";") if part.strip()]
        return [value] if value.strip() else []

    def refresh(self) -> None:
        """Reload configured files and update the GUI without writing emulator configs."""
        data = self._load_json(self.PATHS_FILE)
        for key, edit in self._config_edits.items():
            edit.setText(str(data.get(self._config_key(key)) or ""))
        for key in ("mame", "fbneo", "flycast", "supermodel", "retroarch"):
            editor = self._load_editor(key)
            if editor is None:
                continue
            config = editor.path
            if key == "mame":
                self._refresh_mame(editor, config)
            elif key == "fbneo":
                self._refresh_fbneo(editor, config)
            elif key == "flycast":
                self._refresh_flycast(editor, config)
            elif key == "supermodel":
                self._refresh_supermodel(editor, config)
            elif key == "retroarch":
                self._refresh_retroarch(editor, config)
        tools = self._load_json(self.TOOLS_FILE)
        self.launchbox_edit.setText(str(tools.get("launchbox") or ""))
        self.sevenzip_edit.setText(str(tools.get("sevenzip") or ""))

    def _refresh_mame(self, editor: ConfigFileEditor, config: Path) -> None:
        """Load MAME path settings into folder selectors."""
        multi = {"rompath", "hash", "samples", "artwork", "ctrlr", "ini"}
        for key, _, cfg_key in self.MAME_KEYS:
            values = editor.values(cfg_key)
            if not values:
                continue
            parts = values[0].split(";") if key in multi else [values[0]]
            resolved = [
                self._resolve_path(part, config, emulator="mame")
                for part in parts
                if part.strip()
            ]
            storage = f"mame:{key}"
            if storage in self._path_lists:
                self._path_lists[storage].set_paths(resolved)
            else:
                self._path_edits[storage].setText(resolved[0] if resolved else "")

    def _refresh_fbneo(self, editor: ConfigFileEditor, config: Path) -> None:
        """Load FBNeo indexed ROM paths and support directories."""
        values = editor.values("szAppRomPaths", indexed=True)
        self._path_lists["fbneo:roms"].set_paths(
            [
                self._resolve_path(value, config, emulator="fbneo")
                for value in values
                if value.strip()
            ]
        )
        for key, _, cfg_key in self.FBNEO_KEYS:
            values = editor.values(cfg_key)
            if values:
                self._path_edits[f"fbneo:{key}"].setText(
                    self._resolve_path(values[0], config, emulator="fbneo")
                )

    def _refresh_flycast(self, editor: ConfigFileEditor, config: Path) -> None:
        """Load Flycast scalar and vector path options."""
        for key, _, cfg_key, multi in self.FLYCAST_KEYS:
            values = editor.values(cfg_key)
            if not values:
                continue
            storage = f"flycast:{key}"
            if multi:
                parts = self._split_vector(values[0])
                self._path_lists[storage].set_paths(
                    [
                        self._resolve_path(part, config, emulator="flycast")
                        for part in parts
                    ]
                )
            else:
                self._path_edits[storage].setText(
                    self._resolve_path(values[0], config, emulator="flycast")
                )

    def _refresh_supermodel(self, editor: ConfigFileEditor, config: Path) -> None:
        """Load Supermodel's ROM directory."""
        values = editor.values("RomsDirectory")
        if values:
            self._path_edits["supermodel:roms"].setText(
                self._resolve_path(values[0], config, emulator="supermodel")
            )

    def _refresh_retroarch(self, editor: ConfigFileEditor, config: Path) -> None:
        """Load RetroArch paths and resolve its :\\ notation."""
        for key, _, cfg_key in self.RETROARCH_KEYS:
            values = editor.values(cfg_key)
            if values:
                self._path_edits[f"retroarch:{key}"].setText(
                    self._resolve_path(
                        values[0],
                        config,
                        emulator="retroarch",
                        retroarch=True,
                    )
                )


__all__ = ["ConfigFileEditor", "DirectoryGuidePage", "PathListWidget"]
