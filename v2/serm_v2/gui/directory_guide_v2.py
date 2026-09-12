"""Stable directory configuration implementation used by SERM V2."""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget

from ..integrations.launchbox import LaunchBoxIntegration
from ..runtime.paths import data_root, integrations_root
from ..services.emulator_manager import EmulatorManager


class ConfigFileEditor:
    """Edit supported path values without rewriting unrelated configuration."""
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        raw = self.path.read_bytes()
        self.encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
        if self.encoding == "utf-8":
            try: raw.decode("utf-8")
            except UnicodeDecodeError: self.encoding = "cp1252"
        self._text = raw.decode(self.encoding, errors="replace")

    def values(self, key: str, *, indexed: bool = False) -> list[str]:
        pattern = self._pattern(key, indexed)
        return [m.group("value").strip().strip('"') for line in self._text.splitlines() if (m := pattern.match(line))]

    def set_value(self, key: str, value: str, *, indexed: bool = False, index: int | None = None, separator: str = " ") -> None:
        lines = self._text.splitlines(keepends=True)
        pattern = self._pattern(key, indexed)
        seen = 0
        for pos, line in enumerate(lines):
            match = pattern.match(line.rstrip("\r\n"))
            if not match: continue
            if index is not None and seen != index:
                seen += 1; continue
            raw_value = match.group("value").strip()
            replacement = value
            if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] == '"':
                replacement = '"' + value.replace('"', "'") + '"'
            ending = line[len(line.rstrip("\r\n")):]
            lines[pos] = f"{match.group('prefix')}{replacement}{match.group('suffix')}{ending}"
            self._text = "".join(lines)
            return
        raise KeyError(key)

    def save(self, *, backup_dir: Path | None = None) -> Path:
        backup_root = backup_dir or self.path.parent / ".serm-backups"
        backup_root.mkdir(parents=True, exist_ok=True)
        backup = backup_root / f"{self.path.name}.{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.bak"
        shutil.copy2(self.path, backup)
        fd, tmp = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(self._text.encode(self.encoding, errors="replace")); handle.flush(); os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        except Exception:
            with contextlib.suppress(OSError): os.unlink(tmp)
            raise
        return backup

    @staticmethod
    def _pattern(key: str, indexed: bool) -> re.Pattern[str]:
        expr = rf"{re.escape(key)}\[\d+\]" if indexed else re.escape(key)
        return re.compile(rf"^(?P<prefix>\s*{expr}\s*(?:=\s*|\s+))(?P<value>.*?)(?P<suffix>\s*(?:#.*)?)$")


class PathListWidget(QWidget):
    """Compact multi-directory selector."""
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.list = QListWidget()
        add = QPushButton("Adicionar pasta")
        remove = QPushButton("Remover selecionada")
        add.clicked.connect(self.add_folder); remove.clicked.connect(self.remove_selected)
        buttons = QHBoxLayout(); buttons.setSpacing(5); buttons.addWidget(add); buttons.addWidget(remove)
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(5); layout.addWidget(self.list); layout.addLayout(buttons)
        self.setStyleSheet("QPushButton{min-height:25px;max-width:150px;padding:3px 10px;} QListWidget{min-height:56px;}")

    def set_paths(self, paths) -> None:
        self.list.clear(); self.list.addItems([str(p) for p in paths if p])

    def paths(self) -> list[str]:
        return [self.list.item(i).text().strip() for i in range(self.list.count())]

    def add_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Selecionar diretório", str(Path.home()))
        if selected: self.list.addItem(str(Path(selected).resolve()))

    def remove_selected(self) -> None:
        row = self.list.currentRow()
        if row >= 0: self.list.takeItem(row)


class DirectoryGuidePage(QWidget):
    """Configure emulator data directories and native configuration files."""
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

    def __init__(self, parent=None) -> None:
        super().__init__(parent); self._config_edits = {}; self._path_edits = {}; self._path_lists = {}; self.launchbox = LaunchBoxIntegration(); self._build_ui(); self.refresh()

    @staticmethod
    def _load_json(path: Path) -> dict:
        try: value = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, ValueError, TypeError): return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _save_json(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True); fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle: json.dump(data, handle, indent=2, ensure_ascii=False); handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
            os.replace(tmp, path)
        except Exception:
            with contextlib.suppress(OSError): os.unlink(tmp)
            raise

    @staticmethod
    def _base(config: Path, emulator: str) -> Path:
        return config.parent.parent.resolve() if emulator in {"fbneo", "supermodel"} and config.parent.name.casefold() == "config" else config.parent.resolve()

    @classmethod
    def _resolve(cls, raw: str, config: Path, emulator: str, retroarch=False) -> str:
        value = raw.strip().strip('"')
        if not value: return ""
        if value.casefold() == "default": return "default"
        base = cls._base(config, emulator)
        if retroarch and value.startswith(":\\"): return str((base / value[2:].lstrip("\\/")).resolve())
        p = Path(value).expanduser(); return str(p) if p.is_absolute() else str((base / p).resolve())

    @classmethod
    def _encode(cls, selected: str, config: Path, original: str, emulator: str, retroarch=False) -> str:
        path = Path(selected).expanduser().resolve(); original = original.strip().strip('"'); base = cls._base(config, emulator)
        if retroarch and original.startswith(":\\"):
            try: return ":\\" + str(path.relative_to(base)).replace("/", "\\")
            except ValueError: return str(path)
        if original and not Path(original).is_absolute() and original.casefold() != "default":
            try: return str(path.relative_to(base)).replace("\\", "/")
            except ValueError: pass
        return str(path)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self); root.setContentsMargins(8, 8, 8, 8); root.setSpacing(6)
        title = QLabel("Diretórios dos Emuladores"); title.setStyleSheet("font-size:17px;font-weight:700;"); root.addWidget(title)
        info = QLabel("Configure somente pastas e arquivos pertencentes aos emuladores. Executáveis auxiliares do SERM ficam em Ferramentas."); info.setWordWrap(True); root.addWidget(info)
        self.tabs = QTabWidget()
        for key, label in (("mame", "MAME"), ("fbneo", "FBNeo"), ("flycast", "Flycast"), ("supermodel", "Supermodel"), ("retroarch", "RetroArch")):
            page = QWidget(); scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(page); self.tabs.addTab(scroll, label); getattr(self, f"_build_{key}_tab")(page)
        root.addWidget(self.tabs, 1); self.setStyleSheet("QPushButton{min-height:25px;padding:3px 10px;max-width:155px;} QLineEdit{min-height:25px;padding:2px 7px;} QGroupBox{margin-top:8px;padding-top:8px;}")

    def _header(self, layout, key, title) -> None:
        group = QGroupBox(title); form = QFormLayout(group); form.setHorizontalSpacing(8); form.setVerticalSpacing(5); edit = QLineEdit(); edit.setReadOnly(True); select = QPushButton("Selecionar arquivo"); select.clicked.connect(lambda: self.select_config(key)); row = QHBoxLayout(); row.addWidget(edit, 1); row.addWidget(select, 0); form.addRow("Arquivo:", row); save = QPushButton("💾 Salvar diretórios"); save.setMaximumWidth(170); save.clicked.connect(lambda: self.save_config(key)); form.addRow("", save); layout.addWidget(group); self._config_edits[key] = edit

    def _single(self, form, storage, label) -> None:
        edit = QLineEdit(); edit.setReadOnly(True); button = QPushButton("Selecionar pasta"); button.clicked.connect(lambda: self.select_single(storage)); row = QHBoxLayout(); row.addWidget(edit, 1); row.addWidget(button, 0); form.addRow(label + ":", row); self._path_edits[storage] = edit

    def _list(self, form, storage, label) -> None:
        widget = PathListWidget(); form.addRow(label + ":", widget); self._path_lists[storage] = widget

    def _build_mame_tab(self, page) -> None:
        layout = QVBoxLayout(page); self._header(layout, "mame", "mame.ini"); group = QGroupBox("Diretórios"); form = QFormLayout(group)
        for key, label, _ in self.MAME_KEYS: self._list(form, f"mame:{key}", label) if key in {"rompath", "hash", "samples", "artwork", "ctrlr", "ini"} else self._single(form, f"mame:{key}", label)
        layout.addWidget(group); note = QLabel("Search paths múltiplos são preservados na ordem original."); note.setWordWrap(True); layout.addWidget(note)

    def _build_fbneo_tab(self, page) -> None:
        layout = QVBoxLayout(page); self._header(layout, "fbneo", "fbneo64.ini"); group = QGroupBox("Diretórios"); form = QFormLayout(group); self._list(form, self.FBNEO_ROMS_STORAGE, "ROMs")
        for key, label, _ in self.FBNEO_KEYS: self._single(form, f"fbneo:{key}", label)
        layout.addWidget(group)

    def _build_flycast_tab(self, page) -> None:
        layout = QVBoxLayout(page); self._header(layout, "flycast", "emu.cfg"); group = QGroupBox("Diretórios"); form = QFormLayout(group)
        for key, label, _, multi in self.FLYCAST_KEYS: self._list(form, f"flycast:{key}", label) if multi else self._single(form, f"flycast:{key}", label)
        layout.addWidget(group)

    def _build_supermodel_tab(self, page) -> None:
        layout = QVBoxLayout(page); self._header(layout, "supermodel", "Supermodel.ini"); group = QGroupBox("Diretórios"); form = QFormLayout(group); self._single(form, self.SUPERMODEL_ROMS_STORAGE, "ROMs"); layout.addWidget(group)

    def _build_retroarch_tab(self, page) -> None:
        layout = QVBoxLayout(page); self._header(layout, "retroarch", "retroarch.cfg"); group = QGroupBox("Diretórios"); form = QFormLayout(group)
        for key, label, _ in self.RETROARCH_KEYS: self._single(form, f"retroarch:{key}", label)
        layout.addWidget(group)

    def select_config(self, key: str) -> None:
        filters = {"mame":"MAME INI (*.ini);;Todos os arquivos (*)", "fbneo":"FBNeo INI (*.ini);;Todos os arquivos (*)", "flycast":"Flycast CFG (*.cfg);;Todos os arquivos (*)", "supermodel":"Supermodel INI (*.ini);;Todos os arquivos (*)", "retroarch":"RetroArch CFG (*.cfg);;Todos os arquivos (*)"}
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar configuração", str(Path.home()), filters[key])
        if not path: return
        config = Path(path).resolve(); data = self._load_json(self.PATHS_FILE); data[self._config_key(key)] = str(config); data[key] = str(self._infer_root(key, config)); self._save_json(self.PATHS_FILE, data); self.refresh()

    def select_single(self, storage: str) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Selecionar diretório", self._path_edits[storage].text() or str(Path.home()))
        if selected: self._path_edits[storage].setText(str(Path(selected).resolve()))

    def _config_key(self, key): return {"mame":"mame_config", "fbneo":"fbneo_config", "flycast":"flycast_config", "supermodel":"supermodel_config", "retroarch":"retroarch_cfg"}[key]
    def _infer_root(self, key, config): return config.parent.parent if key in {"fbneo", "supermodel"} and config.parent.name.casefold() == "config" else config.parent
    def _editor(self, key):
        raw = self._load_json(self.PATHS_FILE).get(self._config_key(key)); path = Path(str(raw)).expanduser() if raw else None
        if not path or not path.is_file(): return None
        try: return ConfigFileEditor(path)
        except OSError: return None

    def save_config(self, key) -> None:
        data = self._load_json(self.PATHS_FILE); raw = data.get(self._config_key(key))
        if not raw: QMessageBox.warning(self, "Configuração", "Selecione primeiro o arquivo de configuração."); return
        config = Path(str(raw)).expanduser()
        if not config.is_file(): QMessageBox.warning(self, "Configuração", f"Arquivo não encontrado:\n{config}"); return
        if QMessageBox.question(self, "Confirmar alteração", "O SERM criará um backup e alterará somente as linhas de diretório suportadas.\n\nContinuar?") != QMessageBox.StandardButton.Yes: return
        try:
            editor = ConfigFileEditor(config); getattr(self, f"_save_{key}")(editor, config); backup = editor.save()
        except Exception as exc: QMessageBox.critical(self, "Falha ao salvar", f"Nenhuma alteração foi concluída com segurança.\n\n{exc}"); return
        self.refresh(); QMessageBox.information(self, "Configuração salva", f"Alteração concluída.\nBackup criado em:\n{backup}")

    def _save_mame(self, editor, config):
        multi = {"rompath", "hash", "samples", "artwork", "ctrlr", "ini"}
        for key, _, cfg in self.MAME_KEYS:
            current = editor.values(cfg)
            if not current: continue
            storage = f"mame:{key}"
            if key in multi:
                old = current[0].split(";"); vals = self._path_lists[storage].paths(); editor.set_value(cfg, ";".join(self._encode(v, config, old[i] if i < len(old) else "", "mame") for i, v in enumerate(vals)))
            else:
                value = self._path_edits[storage].text().strip()
                if value: editor.set_value(cfg, self._encode(value, config, current[0], "mame"))

    def _save_fbneo(self, editor, config):
        current = editor.values("szAppRomPaths", indexed=True); selected = self._path_lists[self.FBNEO_ROMS_STORAGE].paths()
        for i, old in enumerate(current): editor.set_value("szAppRomPaths", self._encode(selected[i], config, old, "fbneo") if i < len(selected) else "", indexed=True, index=i)
        for key, _, cfg in self.FBNEO_KEYS:
            current = editor.values(cfg); value = self._path_edits[f"fbneo:{key}"].text().strip()
            if current and value: editor.set_value(cfg, self._encode(value, config, current[0], "fbneo"))

    def _save_flycast(self, editor, config):
        for key, _, cfg, multi in self.FLYCAST_KEYS:
            current = editor.values(cfg)
            if not current: continue
            storage = f"flycast:{key}"
            if multi: editor.set_value(cfg, ";".join(self._encode(v, config, "", "flycast") for v in self._path_lists[storage].paths()))
            else:
                value = self._path_edits[storage].text().strip()
                if value: editor.set_value(cfg, self._encode(value, config, current[0], "flycast"))

    def _save_supermodel(self, editor, config):
        current = editor.values("RomsDirectory"); value = self._path_edits[self.SUPERMODEL_ROMS_STORAGE].text().strip()
        if current and value: editor.set_value("RomsDirectory", self._encode(value, config, current[0], "supermodel"))

    def _save_retroarch(self, editor, config):
        for key, _, cfg in self.RETROARCH_KEYS:
            current = editor.values(cfg); value = self._path_edits[f"retroarch:{key}"].text().strip()
            if current and value and value.casefold() != "default": editor.set_value(cfg, self._encode(value, config, current[0], "retroarch", True))

    def refresh(self) -> None:
        data = self._load_json(self.PATHS_FILE)
        for key, edit in self._config_edits.items(): edit.setText(str(data.get(self._config_key(key)) or ""))
        for key in ("mame", "fbneo", "flycast", "supermodel", "retroarch"):
            editor = self._editor(key)
            if editor is not None: getattr(self, f"_refresh_{key}")(editor, editor.path)

    def _refresh_mame(self, editor, config):
        multi = {"rompath", "hash", "samples", "artwork", "ctrlr", "ini"}
        for key, _, cfg in self.MAME_KEYS:
            values = editor.values(cfg)
            if not values: continue
            parts = values[0].split(";") if key in multi else values; resolved = [self._resolve(v, config, "mame") for v in parts if v.strip()]
            storage = f"mame:{key}"
            self._path_lists[storage].set_paths(resolved) if storage in self._path_lists else self._path_edits[storage].setText(resolved[0] if resolved else "")

    def _refresh_fbneo(self, editor, config):
        values = editor.values("szAppRomPaths", indexed=True); self._path_lists[self.FBNEO_ROMS_STORAGE].set_paths([self._resolve(v, config, "fbneo") for v in values if v.strip()])
        for key, _, cfg in self.FBNEO_KEYS:
            values = editor.values(cfg)
            if values: self._path_edits[f"fbneo:{key}"].setText(self._resolve(values[0], config, "fbneo"))

    def _refresh_flycast(self, editor, config):
        for key, _, cfg, multi in self.FLYCAST_KEYS:
            values = editor.values(cfg)
            if not values: continue
            storage = f"flycast:{key}"
            if multi: self._path_lists[storage].set_paths([self._resolve(v, config, "flycast") for v in values[0].split(";") if v.strip()])
            else: self._path_edits[storage].setText(self._resolve(values[0], config, "flycast"))

    def _refresh_supermodel(self, editor, config):
        values = editor.values("RomsDirectory")
        if values: self._path_edits[self.SUPERMODEL_ROMS_STORAGE].setText(self._resolve(values[0], config, "supermodel"))

    def _refresh_retroarch(self, editor, config):
        for key, _, cfg in self.RETROARCH_KEYS:
            values = editor.values(cfg)
            if values: self._path_edits[f"retroarch:{key}"].setText(self._resolve(values[0], config, "retroarch", True))


__all__ = ["ConfigFileEditor", "DirectoryGuidePage", "PathListWidget"]
