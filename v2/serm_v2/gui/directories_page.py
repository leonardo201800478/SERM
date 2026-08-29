"""Unified directories page for SERM V2."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget

from ..runtime.paths import integrations_root


class DirectoriesPage(QWidget):
    """Unify emulator, RetroArch and tool directories without legacy imports."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build directory sub-tabs using V2-local persistence."""
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._emulators_tab(), "Emuladores")
        tabs.addTab(self._retroarch_tab(), "RetroArch")
        tabs.addTab(self._tools_tab(), "LaunchBox / 7-Zip")
        layout.addWidget(tabs)

    @staticmethod
    def _path_row(label: str, current: str, save) -> QWidget:
        """Create a reusable path field with a folder picker."""
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.addWidget(QLabel(label))
        edit = QLineEdit(current)
        row.addWidget(edit, 1)
        button = QPushButton("Selecionar")

        def choose() -> None:
            from PySide6.QtWidgets import QFileDialog

            selected = QFileDialog.getExistingDirectory(widget, f"Selecionar {label}", edit.text() or str(__import__("pathlib").Path.home()))
            if selected:
                edit.setText(selected)
                save(selected)

        button.clicked.connect(choose)
        row.addWidget(button)
        return widget

    def _emulators_tab(self) -> QWidget:
        """Expose standalone emulator roots stored by the Home service."""
        from .emulator_home import EmulatorHomePage

        page = QWidget()
        layout = QVBoxLayout(page)
        manager = EmulatorHomePage(self).manager
        paths = manager.roots
        for key, label in manager.LABELS.items():
            edit_path = paths.get(key)
            layout.addWidget(QLabel(f"{label}: {edit_path or 'não configurado'}"))
        layout.addWidget(QLabel("Os executáveis também podem ser configurados diretamente na Home."))
        layout.addStretch()
        return page

    def _retroarch_tab(self) -> QWidget:
        """Expose RetroArch root and core directory without depending on V1."""
        import json
        from pathlib import Path

        page = QWidget()
        layout = QVBoxLayout(page)
        config_path = integrations_root() / "emulator_paths.json"
        try:
            data = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            data = {}
        root = str(data.get("retroarch") or "")
        layout.addWidget(self._path_row("Diretório:", root, lambda value: self._save_path(config_path, "retroarch", value)))
        layout.addWidget(QLabel("O retroarch.cfg e os diretórios internos continuam sendo tratados pelo componente RetroArch da Home."))
        layout.addStretch()
        return page

    def _tools_tab(self) -> QWidget:
        """Expose LaunchBox and 7-Zip paths through the V2 tools registry."""
        import json

        page = QWidget()
        layout = QVBoxLayout(page)
        config_path = integrations_root() / "tools.json"
        try:
            data = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            data = {}
        for key, label in (("launchbox", "LaunchBox.exe"), ("sevenzip", "7z.exe")):
            layout.addWidget(self._path_row(label, str(data.get(key) or ""), lambda value, k=key: self._save_path(config_path, k, value)))
        layout.addStretch()
        return page

    @staticmethod
    def _save_path(path, key: str, value: str) -> None:
        """Persist one auxiliary directory entry."""
        import json

        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            data = {}
        data[key] = value
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def refresh(self) -> None:
        """Refresh the page; sub-tabs read their own current configuration on construction."""
        return


__all__ = ["DirectoriesPage"]
