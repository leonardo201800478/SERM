"""Configuration-aware directory guide for SERM V2.

The page is intentionally based on the directory semantics present in the
emulator configuration files used by the SERM setup: MAME, FBNeo, Flycast,
Supermodel and RetroArch. It keeps SERM's own integration paths separate from
emulator-owned runtime directories.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..integrations.launchbox import LaunchBoxIntegration
from ..runtime.paths import data_root, integrations_root
from ..services.emulator_manager import EmulatorManager


class DirectoryGuidePage(QWidget):
    """Show and persist emulator directory topology from their real configs."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    TOOLS_FILE = integrations_root() / "tools.json"
    EXECUTABLES = EmulatorManager.EXECUTABLES
    LABELS = EmulatorManager.LABELS

    CONFIG_KEYS = {
        "mame": "mame_config",
        "fbneo": "fbneo_config",
        "flycast": "flycast_config",
        "supermodel": "supermodel_config",
        "retroarch": "retroarch_cfg",
    }

    RETROARCH_KEYS = (
        ("content", "Conteúdo / ROMs", "content_directory"),
        ("system", "System / BIOS", "system_directory"),
        ("cores", "Cores libretro", "libretro_directory"),
        ("info", "Informações dos cores", "libretro_info_path"),
        ("assets", "Assets", "assets_directory"),
        ("core_assets", "Downloads de assets/cores", "core_assets_directory"),
        ("saves", "Saves", "savefile_directory"),
        ("states", "States", "savestate_directory"),
        ("screenshots", "Screenshots", "screenshot_directory"),
        ("shaders", "Shaders", "video_shader_dir"),
        ("cache", "Cache", "cache_directory"),
        ("playlists", "Playlists", "playlist_directory"),
        ("remaps", "Remaps", "input_remapping_directory"),
        ("autoconfig", "Autoconfig de controles", "joypad_autoconfig_dir"),
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
        ("roms", "ROMs", "szAppRomPaths"),
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
        ("bios", "BIOS", "Dreamcast.BiosPath"),
        ("boxart", "Boxart", "Dreamcast.BoxartPath"),
        ("cheats", "Cheats", "Dreamcast.CheatPath"),
        ("content", "Conteúdo / ROMs", "Dreamcast.ContentPath"),
        ("mappings", "Mappings", "Dreamcast.MappingsPath"),
        ("save", "Saves", "Dreamcast.SavePath"),
        ("states", "Savestates", "Dreamcast.SavestatePath"),
        ("textures", "Textures", "Dreamcast.TexturePath"),
        ("vmu", "VMU", "Dreamcast.VMUPath"),
        ("texture_dump", "Texture dump", "Dreamcast.TextureDumpPath"),
    )

    SUPERMODEL_KEYS = (
        ("games_xml", "Game XML", "GameXMLFile"),
        ("init_state", "Initial state", "InitStateFile"),
        ("roms", "ROMs", "RomsDirectory"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.launchbox = LaunchBoxIntegration()
        self._edits: dict[str, QLineEdit] = {}
        self._config_edits: dict[str, QLineEdit] = {}
        self._build_ui()
        self.refresh()

    @staticmethod
    def _load_json(path: Path) -> dict[str, object]:
        """Load SERM's persisted path mapping without failing on corrupt data."""
        try:
            value = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, ValueError, TypeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _save_json(path: Path, data: dict[str, object]) -> None:
        """Persist SERM's path mapping atomically enough for normal desktop use."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _resolve(value: str, base: Path, *, retroarch: bool = False) -> Path:
        """Resolve relative emulator paths and RetroArch's ``:\\`` notation."""
        value = value.strip().strip('"')
        if not value:
            return Path()
        if retroarch and value.startswith(":\\"):
            value = value[2:]
            return (base / value.lstrip("\\/")) if value else base
        path = Path(value).expanduser()
        return path if path.is_absolute() else (base / path).resolve()

    @staticmethod
    def _parse_key_values(text: str) -> dict[str, list[str]]:
        """Parse simple ``key = value`` or ``key value`` emulator config lines."""
        result: dict[str, list[str]] = {}
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("//") or line.startswith(";"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
            else:
                parts = line.split(None, 1)
                if len(parts) != 2:
                    continue
                key, value = parts
            key = key.strip()
            value = value.strip().strip('"')
            if key.startswith("szAppRomPaths["):
                result.setdefault("szAppRomPaths", []).append(value)
            else:
                result.setdefault(key, []).append(value)
        return result

    @staticmethod
    def _read_config(path: Path) -> dict[str, list[str]]:
        """Read a text configuration using tolerant UTF-8/legacy decoding."""
        try:
            return DirectoryGuidePage._parse_key_values(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            return {}

    @staticmethod
    def _group(title: str) -> tuple[QGroupBox, QFormLayout]:
        """Create a themed form group."""
        group = QGroupBox(title)
        return group, QFormLayout(group)

    def _build_ui(self) -> None:
        """Build scrollable emulator-specific directory tabs."""
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Diretórios dos Emuladores"))
        info = QLabel(
            "A configuração é apresentada conforme a estrutura real dos arquivos .ini/.cfg. "
            "Caminhos relativos são resolvidos a partir da pasta do arquivo de configuração; "
            "no RetroArch, :\\ aponta para a pasta da instalação."
        )
        info.setWordWrap(True)
        root.addWidget(info)
        self.tabs = QTabWidget()
        for key, label in (("mame", "MAME"), ("fbneo", "FBNeo"), ("flycast", "Flycast"), ("supermodel", "Supermodel"), ("retroarch", "RetroArch"), ("tools", "Ferramentas")):
            page = QWidget()
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.tabs.addTab(scroll, label)
            getattr(self, f"_build_{key}_tab")(page)
        root.addWidget(self.tabs, 1)

    def _config_header(self, layout: QVBoxLayout, key: str, title: str) -> QLineEdit:
        """Add a config-file selector/status row and return its field."""
        group, form = self._group(title)
        edit = QLineEdit()
        edit.setReadOnly(True)
        button = QPushButton("Selecionar arquivo")
        button.clicked.connect(lambda: self.select_config(key))
        row = QHBoxLayout(); row.addWidget(edit, 1); row.addWidget(button)
        form.addRow("Configuração:", row)
        layout.addWidget(group)
        self._config_edits[key] = edit
        return edit

    def _add_field(self, form: QFormLayout, storage_key: str, label: str, value: str = "") -> None:
        """Add a read-only path field used by the guide."""
        edit = QLineEdit(value); edit.setReadOnly(True)
        form.addRow(label + ":", edit)
        self._edits[storage_key] = edit

    def _build_mame_tab(self, page: QWidget) -> None:
        """Build MAME's ROM/support/runtime directory map."""
        layout = QVBoxLayout(page); self._config_header(layout, "mame", "mame.ini")
        group, form = self._group("Core / ROM / suporte")
        for key, label, cfg_key in self.MAME_KEYS:
            self._add_field(form, f"mame:{key}", label, "")
        layout.addWidget(group)
        note = QLabel("rompath pode conter múltiplas raízes separadas por ';'. O SERM preserva cada entrada separadamente.")
        note.setWordWrap(True); layout.addWidget(note)
        self._mame_cfg_fields = {key: cfg_key for key, _, cfg_key in self.MAME_KEYS}

    def _build_fbneo_tab(self, page: QWidget) -> None:
        """Build FBNeo's ROM and support-directory map."""
        layout = QVBoxLayout(page); self._config_header(layout, "fbneo", "fbneo64.ini")
        group, form = self._group("ROMs e suporte")
        for key, label, cfg_key in self.FBNEO_KEYS:
            self._add_field(form, f"fbneo:{key}", label, "")
        layout.addWidget(group)
        self._fbneo_cfg_fields = {key: cfg_key for key, _, cfg_key in self.FBNEO_KEYS}

    def _build_flycast_tab(self, page: QWidget) -> None:
        """Build Flycast's Dreamcast/Naomi content and runtime directory map."""
        layout = QVBoxLayout(page); self._config_header(layout, "flycast", "emu.cfg")
        group, form = self._group("Dreamcast / Naomi")
        for key, label, cfg_key in self.FLYCAST_KEYS:
            self._add_field(form, f"flycast:{key}", label, "")
        layout.addWidget(group)
        self._flycast_cfg_fields = {key: cfg_key for key, _, cfg_key in self.FLYCAST_KEYS}

    def _build_supermodel_tab(self, page: QWidget) -> None:
        """Build Supermodel's XML, state and ROM locations."""
        layout = QVBoxLayout(page); self._config_header(layout, "supermodel", "Supermodel.ini")
        group, form = self._group("Supermodel")
        for key, label, cfg_key in self.SUPERMODEL_KEYS:
            self._add_field(form, f"supermodel:{key}", label, "")
        layout.addWidget(group)
        self._supermodel_cfg_fields = {key: cfg_key for key, _, cfg_key in self.SUPERMODEL_KEYS}

    def _build_retroarch_tab(self, page: QWidget) -> None:
        """Build RetroArch's complete path topology relevant to SERM."""
        layout = QVBoxLayout(page); self._config_header(layout, "retroarch", "retroarch.cfg")
        group, form = self._group("Diretórios do RetroArch")
        for key, label, cfg_key in self.RETROARCH_KEYS:
            self._add_field(form, f"retroarch:{key}", label, "")
        layout.addWidget(group)
        note = QLabel("A configuração anexada usa content_directory em D:, saves/states/screenshots em G: e vários recursos internos no formato :\\...")
        note.setWordWrap(True); layout.addWidget(note)

    def _build_tools_tab(self, page: QWidget) -> None:
        """Build auxiliary LaunchBox and 7-Zip fields."""
        layout = QVBoxLayout(page)
        group, form = self._group("Ferramentas auxiliares")
        tools = self._load_json(self.TOOLS_FILE)
        self.launchbox_edit = QLineEdit(str(tools.get("launchbox") or "")); self.launchbox_edit.setReadOnly(True)
        button = QPushButton("Selecionar LaunchBox.exe"); button.clicked.connect(self.select_launchbox)
        row = QHBoxLayout(); row.addWidget(self.launchbox_edit, 1); row.addWidget(button); form.addRow("LaunchBox:", row)
        self.sevenzip_edit = QLineEdit(str(tools.get("sevenzip") or "")); self.sevenzip_edit.setReadOnly(True)
        button7 = QPushButton("Selecionar 7z.exe"); button7.clicked.connect(self.select_7zip)
        row7 = QHBoxLayout(); row7.addWidget(self.sevenzip_edit, 1); row7.addWidget(button7); form.addRow("7-Zip:", row7)
        layout.addWidget(group); layout.addStretch()

    def select_config(self, key: str) -> None:
        """Select an emulator configuration file and immediately parse its directories."""
        names = {"mame": "mame.ini", "fbneo": "fbneo64.ini", "flycast": "emu.cfg", "supermodel": "Supermodel.ini", "retroarch": "retroarch.cfg"}
        path, _ = QFileDialog.getOpenFileName(self, f"Selecionar {names[key]}", str(Path.home()), "Arquivos de configuração (*.ini *.cfg);;Todos os arquivos (*)")
        if not path:
            return
        data = self._load_json(self.PATHS_FILE); data[self.CONFIG_KEYS[key]] = str(Path(path).resolve())
        if key != "retroarch":
            data[key] = str(Path(path).resolve().parent)
        else:
            data["retroarch"] = str(Path(path).resolve().parent)
        self._save_json(self.PATHS_FILE, data); self.refresh()

    def _parse_and_store(self, key: str, cfg: Path, fields: tuple[tuple[str, str, str], ...], *, retroarch: bool = False, multi: set[str] | None = None) -> None:
        """Parse a config and populate the corresponding UI fields."""
        parsed = self._read_config(cfg); base = cfg.parent
        multi = multi or set()
        for field, _, cfg_key in fields:
            values = parsed.get(cfg_key, [])
            if cfg_key == "rompath":
                expanded = []
                for value in values:
                    expanded.extend(value.split(";"))
                values = expanded
            if cfg_key == "szAppRomPaths":
                values = values
            resolved = [str(self._resolve(v, base, retroarch=retroarch)) for v in values if v.strip()]
            if field in multi or len(resolved) > 1:
                value = "\n".join(resolved)
            else:
                value = resolved[0] if resolved else ""
            edit = self._edits.get(f"{key}:{field}")
            if edit: edit.setText(value)

    def _parse_flycast(self, cfg: Path) -> None:
        """Parse Flycast's [config] key/value file, including multi-root ContentPath."""
        parsed = self._read_config(cfg); base = cfg.parent
        for field, _, cfg_key in self.FLYCAST_KEYS:
            values = parsed.get(cfg_key, [])
            expanded = []
            for value in values:
                expanded.extend(value.split(";"))
            resolved = [str(self._resolve(v, base)) for v in expanded if v.strip()]
            if edit := self._edits.get(f"flycast:{field}"):
                edit.setText("\n".join(resolved))

    def _parse_retroarch(self, cfg: Path) -> None:
        """Parse RetroArch paths and correctly resolve the special :\\ prefix."""
        parsed = self._read_config(cfg); base = cfg.parent
        for field, _, cfg_key in self.RETROARCH_KEYS:
            values = parsed.get(cfg_key, [])
            resolved = [str(self._resolve(v, base, retroarch=True)) for v in values if v.strip()]
            if edit := self._edits.get(f"retroarch:{field}"):
                edit.setText("\n".join(resolved))

    def refresh(self) -> None:
        """Refresh configured files, parse their directory topology and update tools."""
        data = self._load_json(self.PATHS_FILE)
        for key in self.CONFIG_KEYS:
            value = data.get(self.CONFIG_KEYS[key])
            if value and key in self._config_edits:
                self._config_edits[key].setText(str(value))
            if not value:
                continue
            cfg = Path(str(value)).expanduser()
            if not cfg.is_file():
                continue
            if key == "mame": self._parse_and_store("mame", cfg, self.MAME_KEYS, multi={"rompath", "ini"})
            elif key == "fbneo": self._parse_and_store("fbneo", cfg, self.FBNEO_KEYS, multi={"roms"})
            elif key == "flycast": self._parse_flycast(cfg)
            elif key == "supermodel": self._parse_and_store("supermodel", cfg, self.SUPERMODEL_KEYS)
            elif key == "retroarch": self._parse_retroarch(cfg)
        tools = self._load_json(self.TOOLS_FILE)
        if hasattr(self, "launchbox_edit"): self.launchbox_edit.setText(str(tools.get("launchbox") or ""))
        if hasattr(self, "sevenzip_edit"): self.sevenzip_edit.setText(str(tools.get("sevenzip") or ""))

    def select_launchbox(self) -> None:
        """Select and persist LaunchBox.exe."""
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar LaunchBox.exe", str(Path.home()), "LaunchBox (LaunchBox.exe);;Executáveis (*.exe)")
        if path:
            self.launchbox.set_executable(Path(path)); self.refresh()

    def select_7zip(self) -> None:
        """Select and persist 7z.exe."""
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar 7z.exe", str(Path.home()), "7-Zip (7z.exe);;Executáveis (*.exe)")
        if path:
            data = self._load_json(self.TOOLS_FILE); data["sevenzip"] = str(Path(path).resolve()); self._save_json(self.TOOLS_FILE, data); self.refresh()


__all__ = ["DirectoryGuidePage"]
