"""Unified directory configuration for SERM V2."""
from __future__ import annotations

import json
from pathlib import Path

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
    """Configure all external application directories used by SERM V2.

    The page deliberately shares the same V2 persistence used by Home. It never
    creates another Home widget just to inspect configuration, avoiding nested
    discovery/workers and keeping the two screens synchronized.
    """

    EMULATOR_PATHS = EmulatorManager.LABELS
    PATHS_FILE = data_root() / "emulator_paths.json"
    TOOLS_FILE = integrations_root() / "tools.json"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.launchbox = LaunchBoxIntegration()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Build the three directory-management groups."""
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._emulators_tab(), "Emuladores")
        tabs.addTab(self._retroarch_tab(), "RetroArch")
        tabs.addTab(self._tools_tab(), "LaunchBox / 7-Zip")
        layout.addWidget(tabs)

    @staticmethod
    def _load_json(path: Path) -> dict[str, object]:
        """Load a JSON mapping, returning an empty mapping on invalid data."""
        try:
            value = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, ValueError, TypeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _save_json(path: Path, data: dict[str, object]) -> None:
        """Persist one V2 JSON configuration mapping atomically enough for GUI use."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _path_group(title: str) -> tuple[QGroupBox, QFormLayout]:
        """Create a standard group used by the directory tabs."""
        group = QGroupBox(title)
        return group, QFormLayout(group)

    def _emulators_tab(self) -> QWidget:
        """Configure the four standalone emulator installation roots."""
        page = QWidget()
        layout = QVBoxLayout(page)
        paths = self._load_json(self.PATHS_FILE)
        self.emulator_edits: dict[str, QLineEdit] = {}

        group, form = self._path_group("Emuladores standalone")
        for key, label in self.EMULATOR_PATHS.items():
            edit = QLineEdit(str(paths.get(key) or ""))
            edit.setReadOnly(True)
            button = QPushButton("Selecionar")
            button.clicked.connect(lambda _=False, k=key: self.select_emulator(k))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(button)
            form.addRow(f"{label}:", row)
            self.emulator_edits[key] = edit
        layout.addWidget(group)

        self.emulator_hint = QLabel(
            "A Home usa exatamente estes diretórios para descoberta, instalação e atualização."
        )
        self.emulator_hint.setWordWrap(True)
        layout.addWidget(self.emulator_hint)

        refresh = QPushButton("🔄 Atualizar detecção")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        layout.addStretch()
        return page

    def _retroarch_tab(self) -> QWidget:
        """Configure RetroArch root and expose its cores directory."""
        page = QWidget()
        layout = QVBoxLayout(page)
        paths = self._load_json(self.PATHS_FILE)

        group, form = self._path_group("RetroArch")
        self.retroarch_edit = QLineEdit(str(paths.get("retroarch") or ""))
        self.retroarch_edit.setReadOnly(True)
        select = QPushButton("Selecionar diretório")
        select.clicked.connect(self.select_retroarch)
        row = QHBoxLayout()
        row.addWidget(self.retroarch_edit, 1)
        row.addWidget(select)
        form.addRow("Instalação:", row)

        self.retroarch_status = QLabel()
        form.addRow("Status:", self.retroarch_status)
        self.retroarch_cores = QLabel()
        self.retroarch_cores.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Cores:", self.retroarch_cores)
        layout.addWidget(group)

        info = QLabel(
            "O diretório informado aqui é compartilhado com a Home. "
            "Os cores são instalados em <RetroArch>\\cores."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        refresh = QPushButton("🔄 Redetectar RetroArch")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        layout.addStretch()
        return page

    def _tools_tab(self) -> QWidget:
        """Configure LaunchBox and the command-line 7-Zip executable."""
        page = QWidget()
        layout = QVBoxLayout(page)
        group, form = self._path_group("Ferramentas auxiliares")

        tools = self._load_json(self.TOOLS_FILE)
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
        """Select an emulator executable and persist its parent directory."""
        label = self.EMULATOR_PATHS[key]
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Selecionar {label}.exe",
            str(Path.home()),
            f"{label} (*.exe);;Executáveis (*.exe)",
        )
        if not path:
            return
        data = self._load_json(self.PATHS_FILE)
        data[key] = str(Path(path).resolve().parent)
        self._save_json(self.PATHS_FILE, data)
        self.refresh()

    def select_retroarch(self) -> None:
        """Select and persist the RetroArch installation root."""
        current = self._load_json(self.PATHS_FILE).get("retroarch")
        selected = QFileDialog.getExistingDirectory(
            self,
            "Diretório do RetroArch",
            str(current or Path.home()),
        )
        if not selected:
            return
        data = self._load_json(self.PATHS_FILE)
        data["retroarch"] = str(Path(selected).resolve())
        self._save_json(self.PATHS_FILE, data)
        self.refresh()

    def select_launchbox(self) -> None:
        """Select and persist LaunchBox.exe."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar LaunchBox.exe",
            str(Path.home()),
            "LaunchBox (LaunchBox.exe);;Executáveis (*.exe)",
        )
        if not path:
            return
        self.launchbox.set_executable(Path(path))
        self.refresh()

    def select_7zip(self) -> None:
        """Select and persist the 7-Zip command-line executable."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar 7z.exe",
            str(Path.home()),
            "7-Zip (7z.exe);;Executáveis (*.exe)",
        )
        if not path:
            return
        data = self._load_json(self.TOOLS_FILE)
        data["sevenzip"] = str(Path(path).resolve())
        self._save_json(self.TOOLS_FILE, data)
        self.refresh()

    def refresh(self) -> None:
        """Refresh all directory fields and executable status indicators."""
        paths = self._load_json(self.PATHS_FILE)
        for key, edit in getattr(self, "emulator_edits", {}).items():
            value = str(paths.get(key) or "")
            edit.setText(value)

        retroarch = paths.get("retroarch")
        retro_root = Path(str(retroarch)).expanduser() if retroarch else None
        executable, root, cores = RetroArchManager(retro_root).discover()
        if hasattr(self, "retroarch_edit"):
            self.retroarch_edit.setText(str(root or retro_root or ""))
            self.retroarch_status.setText("● Encontrado" if executable else "● Não encontrado")
            self.retroarch_cores.setText(str(cores or (retro_root / "cores" if retro_root else "")))

        tools = self._load_json(self.TOOLS_FILE)
        launchbox = self.launchbox.discover()
        launchbox_path = Path(launchbox) if launchbox else Path(str(tools.get("launchbox") or ""))
        if hasattr(self, "launchbox_edit"):
            self.launchbox_edit.setText(str(launchbox_path) if launchbox_path else "")
            self.launchbox_status.setText(
                "● Encontrado" if launchbox_path.is_file() else "● Não encontrado"
            )

        configured_7zip = str(tools.get("sevenzip") or "")
        sevenzip = Path(configured_7zip) if configured_7zip and Path(configured_7zip).is_file() else EmulatorManager.find_7zip()
        if hasattr(self, "sevenzip_edit"):
            self.sevenzip_edit.setText(str(sevenzip or ""))
            self.sevenzip_status.setText(
                "● Encontrado" if sevenzip and sevenzip.is_file() else "● Não encontrado"
            )


__all__ = ["DirectoriesPage"]
