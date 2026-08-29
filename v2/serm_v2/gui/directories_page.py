"""Unified directory configuration for SERM V2."""
from __future__ import annotations

import json
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..integrations.launchbox import LaunchBoxIntegration
from ..runtime.paths import data_root, integrations_root
from ..services.emulator_manager import EmulatorManager, RetroArchManager


class DirectoriesPage(QWidget):
    """Centralize emulator, RetroArch, LaunchBox and 7-Zip paths."""

    EMULATOR_PATHS = EmulatorManager.LABELS
    PATHS_FILE = data_root() / "emulator_paths.json"
    TOOLS_FILE = integrations_root() / "tools.json"
    RETROARCH_KEYS = {
        "system": "system_directory",
        "cores": "libretro_directory",
        "info": "libretro_info_path",
        "assets": "assets_directory",
        "saves": "savefile_directory",
        "states": "savestate_directory",
        "shaders": "video_shader_dir",
        "downloads": "downloads_directory",
        "screenshots": "screenshot_directory",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.launchbox = LaunchBoxIntegration()
        self.retro_edits: dict[str, QLineEdit] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Build the unified directory tabs."""
        layout = QVBoxLayout(self)
        title = QLabel("Diretórios")
        title.setStyleSheet("font-size:22px;font-weight:bold;")
        layout.addWidget(title)
        description = QLabel(
            "Configuração central compartilhada pela Home, RetroArch, emuladores, LaunchBox, 7-Zip e Scraper de DATs."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color:#888;")
        layout.addWidget(description)
        tabs = QTabWidget()
        tabs.addTab(self._emulators_tab(), "Emuladores")
        tabs.addTab(self._retroarch_tab(), "RetroArch")
        tabs.addTab(self._tools_tab(), "LaunchBox / 7-Zip")
        layout.addWidget(tabs, 1)

    @staticmethod
    def _load_json(path: Path) -> dict[str, object]:
        """Load a JSON mapping safely."""
        try:
            value = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, ValueError, TypeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _save_json(path: Path, data: dict[str, object]) -> None:
        """Persist a JSON mapping under the V2 data tree."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _path_group(title: str) -> tuple[QGroupBox, QFormLayout]:
        """Create a standard labeled form group."""
        group = QGroupBox(title)
        return group, QFormLayout(group)

    def _emulators_tab(self) -> QWidget:
        """Configure installation roots and executables for standalone emulators."""
        page = QWidget()
        layout = QVBoxLayout(page)
        paths = self._load_json(self.PATHS_FILE)
        self.emulator_edits: dict[str, QLineEdit] = {}
        group, form = self._path_group("Emuladores standalone")
        for key, label in self.EMULATOR_PATHS.items():
            edit = QLineEdit(str(paths.get(key) or ""))
            edit.setReadOnly(True)
            button = QPushButton("Selecionar .exe")
            button.clicked.connect(lambda _=False, k=key: self.select_emulator(k))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(button)
            form.addRow(f"{label}:", row)
            self.emulator_edits[key] = edit
        layout.addWidget(group)
        hint = QLabel(
            "A Home usa exatamente estes diretórios. O executável é detectado dentro do diretório selecionado."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888;")
        layout.addWidget(hint)
        refresh = QPushButton("🔄 Atualizar detecção")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        layout.addStretch()
        return page

    def _retroarch_tab(self) -> QWidget:
        """Configure RetroArch root and paths derived from retroarch.cfg."""
        page = QWidget()
        layout = QVBoxLayout(page)
        paths = self._load_json(self.PATHS_FILE)
        group, form = self._path_group("Instalação do RetroArch")
        self.retroarch_edit = QLineEdit(str(paths.get("retroarch") or ""))
        self.retroarch_edit.setReadOnly(True)
        select = QPushButton("Selecionar diretório")
        select.clicked.connect(self.select_retroarch)
        row = QHBoxLayout()
        row.addWidget(self.retroarch_edit, 1)
        row.addWidget(select)
        form.addRow("Instalação:", row)
        self.retroarch_cfg_edit = QLineEdit()
        self.retroarch_cfg_edit.setReadOnly(True)
        cfg_button = QPushButton("Selecionar retroarch.cfg")
        cfg_button.clicked.connect(self.select_retroarch_cfg)
        row_cfg = QHBoxLayout()
        row_cfg.addWidget(self.retroarch_cfg_edit, 1)
        row_cfg.addWidget(cfg_button)
        form.addRow("Configuração:", row_cfg)
        self.retroarch_status = QLabel()
        form.addRow("Status:", self.retroarch_status)
        layout.addWidget(group)

        dirs_group, dirs_form = self._path_group("Diretórios do RetroArch")
        for key, label in (
            ("cores", "Cores"),
            ("info", "Informações dos cores (.info)"),
            ("system", "System / BIOS"),
            ("assets", "Assets"),
            ("saves", "Saves"),
            ("states", "States"),
            ("shaders", "Shaders"),
            ("downloads", "Downloads"),
            ("screenshots", "Screenshots"),
        ):
            edit = QLineEdit()
            edit.setReadOnly(True)
            button = QPushButton("…")
            button.clicked.connect(lambda _=False, k=key: self.select_retro_subdir(k))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(button)
            dirs_form.addRow(f"{label}:", row)
            self.retro_edits[key] = edit
        layout.addWidget(dirs_group)

        actions = QHBoxLayout()
        load = QPushButton("📄 Ler retroarch.cfg")
        load.clicked.connect(self.load_retroarch_cfg)
        actions.addWidget(load)
        save = QPushButton("💾 Salvar caminhos no retroarch.cfg")
        save.clicked.connect(self.save_retroarch_cfg)
        actions.addWidget(save)
        detect = QPushButton("🔄 Redetectar")
        detect.clicked.connect(self.refresh)
        actions.addWidget(detect)
        layout.addLayout(actions)
        note = QLabel(
            "O diretório de instalação permanece na configuração central. Quando retroarch.cfg existe, "
            "os caminhos configurados nele são carregados e podem ser gravados novamente."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#888;font-size:10px;")
        layout.addWidget(note)
        layout.addStretch()
        return page

    def _tools_tab(self) -> QWidget:
        """Configure LaunchBox.exe and the local 7z.exe used by SERM."""
        page = QWidget()
        layout = QVBoxLayout(page)
        tools = self._load_json(self.TOOLS_FILE)
        group, form = self._path_group("Ferramentas auxiliares")
        self.launchbox_edit = QLineEdit(str(tools.get("launchbox") or ""))
        self.launchbox_edit.setReadOnly(True)
        select_lb = QPushButton("Selecionar LaunchBox.exe")
        select_lb.clicked.connect(self.select_launchbox)
        row = QHBoxLayout()
        row.addWidget(self.launchbox_edit, 1)
        row.addWidget(select_lb)
        form.addRow("LaunchBox:", row)
        self.launchbox_status = QLabel()
        form.addRow("Status:", self.launchbox_status)
        self.sevenzip_edit = QLineEdit(str(tools.get("sevenzip") or ""))
        self.sevenzip_edit.setReadOnly(True)
        select_7z = QPushButton("Selecionar 7z.exe")
        select_7z.clicked.connect(self.select_7zip)
        row7 = QHBoxLayout()
        row7.addWidget(self.sevenzip_edit, 1)
        row7.addWidget(select_7z)
        form.addRow("7-Zip:", row7)
        self.sevenzip_status = QLabel()
        form.addRow("Status:", self.sevenzip_status)
        layout.addWidget(group)
        refresh = QPushButton("🔄 Redetectar ferramentas")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        layout.addStretch()
        return page

    def select_emulator(self, key: str) -> None:
        """Select an emulator executable and save its parent directory."""
        label = self.EMULATOR_PATHS[key]
        path, _ = QFileDialog.getOpenFileName(self, f"Selecionar {label}.exe", str(Path.home()), "Executáveis (*.exe)")
        if not path:
            return
        data = self._load_json(self.PATHS_FILE)
        data[key] = str(Path(path).resolve().parent)
        self._save_json(self.PATHS_FILE, data)
        self.refresh()

    def select_retroarch(self) -> None:
        """Select and persist the RetroArch installation root."""
        current = self._load_json(self.PATHS_FILE).get("retroarch")
        selected = QFileDialog.getExistingDirectory(self, "Diretório do RetroArch", str(current or Path.home()))
        if not selected:
            return
        data = self._load_json(self.PATHS_FILE)
        data["retroarch"] = str(Path(selected).resolve())
        self._save_json(self.PATHS_FILE, data)
        self.refresh()

    def select_retroarch_cfg(self) -> None:
        """Select a retroarch.cfg and persist its explicit path."""
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar retroarch.cfg", str(Path.home()), "RetroArch config (retroarch.cfg)")
        if not path:
            return
        data = self._load_json(self.PATHS_FILE)
        data["retroarch_cfg"] = str(Path(path).resolve())
        self._save_json(self.PATHS_FILE, data)
        self.load_retroarch_cfg()

    def select_retro_subdir(self, key: str) -> None:
        """Select and persist one RetroArch subdirectory."""
        current = self.retro_edits[key].text()
        selected = QFileDialog.getExistingDirectory(self, "Selecionar diretório", current or str(Path.home()))
        if not selected:
            return
        data = self._load_json(self.PATHS_FILE)
        data[f"retroarch_{key}"] = str(Path(selected).resolve())
        self._save_json(self.PATHS_FILE, data)
        self.refresh()

    def select_launchbox(self) -> None:
        """Select and persist LaunchBox.exe."""
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar LaunchBox.exe", str(Path.home()), "LaunchBox (LaunchBox.exe);;Executáveis (*.exe)")
        if not path:
            return
        self.launchbox.set_executable(Path(path))
        self.refresh()

    def select_7zip(self) -> None:
        """Select and persist the command-line 7-Zip executable."""
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar 7z.exe", str(Path.home()), "7-Zip (7z.exe);;Executáveis (*.exe)")
        if not path:
            return
        data = self._load_json(self.TOOLS_FILE)
        data["sevenzip"] = str(Path(path).resolve())
        self._save_json(self.TOOLS_FILE, data)
        self.refresh()

    def load_retroarch_cfg(self) -> None:
        """Read supported directory keys from retroarch.cfg without rewriting unrelated settings."""
        cfg = self._retroarch_cfg_path()
        if not cfg or not cfg.is_file():
            self.retroarch_status.setText("● retroarch.cfg não encontrado")
            return
        data = self._load_json(self.PATHS_FILE)
        text = cfg.read_text(encoding="utf-8", errors="replace")
        loaded = 0
        for key, cfg_key in self.RETROARCH_KEYS.items():
            match = re.search(rf'^\s*{re.escape(cfg_key)}\s*=\s*"([^"]*)"', text, re.MULTILINE)
            if not match:
                continue
            value = match.group(1).strip()
            if value:
                path = Path(value).expanduser()
                if not path.is_absolute():
                    path = (cfg.parent / path).resolve()
                self.retro_edits[key].setText(str(path))
                data[f"retroarch_{key}"] = str(path)
                loaded += 1
        self._save_json(self.PATHS_FILE, data)
        self.retroarch_cfg_edit.setText(str(cfg))
        self.retroarch_status.setText(f"● Configuração carregada ({loaded} diretório(s))")

    def save_retroarch_cfg(self) -> None:
        """Write supported directory values to retroarch.cfg, preserving unrelated lines."""
        cfg = self._retroarch_cfg_path()
        if not cfg:
            QMessageBox = __import__("PySide6.QtWidgets", fromlist=["QMessageBox"]).QMessageBox
            QMessageBox.information(self, "RetroArch", "Selecione ou configure um retroarch.cfg primeiro.")
            return
        text = cfg.read_text(encoding="utf-8", errors="replace") if cfg.is_file() else ""
        for key, cfg_key in self.RETROARCH_KEYS.items():
            value = self.retro_edits[key].text().strip()
            if not value:
                continue
            replacement = f'{cfg_key} = "{value.replace(chr(34), chr(39))}"'
            pattern = rf'^\s*{re.escape(cfg_key)}\s*=.*$'
            if re.search(pattern, text, re.MULTILINE):
                text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
            else:
                text += ("\n" if text and not text.endswith("\n") else "") + replacement + "\n"
        cfg.parent.mkdir(parents=True, exist_ok=True)
        cfg.write_text(text, encoding="utf-8")
        self.retroarch_cfg_edit.setText(str(cfg))
        self.retroarch_status.setText("● Caminhos salvos no retroarch.cfg")

    def _retroarch_cfg_path(self) -> Path | None:
        """Resolve the explicit or conventional RetroArch configuration path."""
        data = self._load_json(self.PATHS_FILE)
        explicit = data.get("retroarch_cfg")
        if explicit:
            return Path(str(explicit)).expanduser()
        root = data.get("retroarch")
        if root:
            candidate = Path(str(root)).expanduser() / "retroarch.cfg"
            if candidate.is_file():
                return candidate
        return None

    def refresh(self) -> None:
        """Refresh all configured paths and executable status indicators."""
        paths = self._load_json(self.PATHS_FILE)
        for key, edit in getattr(self, "emulator_edits", {}).items():
            edit.setText(str(paths.get(key) or ""))
        retroarch = paths.get("retroarch")
        retro_root = Path(str(retroarch)).expanduser() if retroarch else None
        executable, root, cores = RetroArchManager(retro_root).discover()
        if hasattr(self, "retroarch_edit"):
            self.retroarch_edit.setText(str(root or retro_root or ""))
            self.retroarch_status.setText("● RetroArch encontrado" if executable else "● RetroArch não encontrado")
            cfg = self._retroarch_cfg_path()
            self.retroarch_cfg_edit.setText(str(cfg or ""))
        for key, edit in getattr(self, "retro_edits", {}).items():
            value = paths.get(f"retroarch_{key}")
            if not value:
                value = str(cores) if key == "cores" and cores else ""
            edit.setText(str(value or ""))
        tools = self._load_json(self.TOOLS_FILE)
        launchbox = self.launchbox.discover()
        launchbox_path = Path(launchbox) if launchbox else None
        if hasattr(self, "launchbox_edit"):
            self.launchbox_edit.setText(str(launchbox_path or tools.get("launchbox") or ""))
            self.launchbox_status.setText("● Encontrado" if launchbox_path and launchbox_path.is_file() else "● Não encontrado")
        configured_7zip = str(tools.get("sevenzip") or "")
        sevenzip = Path(configured_7zip) if configured_7zip and Path(configured_7zip).is_file() else EmulatorManager.find_7zip()
        if hasattr(self, "sevenzip_edit"):
            self.sevenzip_edit.setText(str(sevenzip or ""))
            self.sevenzip_status.setText("● Encontrado" if sevenzip and sevenzip.is_file() else "● Não encontrado")


__all__ = ["DirectoriesPage"]
