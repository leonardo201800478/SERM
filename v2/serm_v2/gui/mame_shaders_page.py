"""Configuração BGFX do MAME V2.

A página primeiro inspeciona o ``inipath`` efetivo do MAME para identificar
arquivos INI que podem interferir na configuração global. Presets continuam
sendo preservados; arquivos efetivamente carregados são classificados e
conflitos são apresentados antes da aplicação de configurações.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root
from .directories_guide_page import ConfigFileEditor


class MameShadersPage(QWidget):
    """Editor BGFX com diagnóstico da composição de INIs do MAME."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    CHAIN_KEY = "bgfx_screen_chains"
    VIDEO_KEY = "video"
    BACKEND_KEY = "bgfx_backend"
    INIPATH_KEY = "inipath"

    BGFX_BACKENDS = ("auto", "d3d9", "d3d11", "d3d12", "opengl", "gles", "metal", "vulkan")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.video = QComboBox()
        self.backend = QComboBox()
        self.chain = QComboBox()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.scan = QLabel()
        self.scan.setWordWrap(True)
        self._build_ui()
        self.refresh()

    @staticmethod
    def _paths() -> dict[str, Any]:
        """Carrega os caminhos persistidos pelo SERM."""
        try:
            value = json.loads(MameShadersPage.PATHS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _root(self) -> Path | None:
        """Resolve a raiz da instalação MAME."""
        paths = self._paths()
        for key in ("mame_root", "mame_executable", "mame_config", "mame_ini"):
            raw = paths.get(key)
            if not raw:
                continue
            p = Path(str(raw)).expanduser()
            if p.is_file() or p.suffix.lower() in {".exe", ".ini"}:
                p = p.parent
            if p.name.lower() == "mame.ini":
                p = p.parent
            if (p / "mame.exe").is_file() or (p / "bgfx").is_dir():
                return p
        return None

    def _ini(self) -> Path | None:
        """Localiza o mame.ini."""
        paths = self._paths()
        for key in ("mame_config", "mame_ini"):
            raw = paths.get(key)
            if raw and Path(str(raw)).is_file():
                return Path(str(raw)).expanduser()
        root = self._root()
        if root:
            for name in ("mame.ini", "MAME.ini"):
                p = root / name
                if p.is_file():
                    return p
        return None

    @staticmethod
    def _value(editor: ConfigFileEditor | None, key: str) -> str:
        """Obtém o primeiro valor de uma chave INI."""
        if editor is None:
            return ""
        values = editor.values(key)
        return values[0].strip() if values else ""

    @staticmethod
    def _chain_name(value: str) -> str:
        """Normaliza um nome/caminho de chain para o identificador MAME."""
        value = value.strip().strip('"').replace("\\", "/")
        value = value.rsplit("/", 1)[-1]
        return value[:-5] if value.lower().endswith(".json") else value

    def _inipath(self, editor: ConfigFileEditor) -> list[Path]:
        """Resolve o inipath do mame.ini na ordem declarada, sem confundir presets com a raiz."""
        root = self._root()
        if root is None:
            return []
        raw = self._value(editor, self.INIPATH_KEY) or ".;ini;ini/presets"
        result: list[Path] = []
        for item in raw.split(";"):
            item = item.strip().strip('"')
            if not item:
                continue
            p = Path(item)
            if not p.is_absolute():
                p = root / p
            p = p.resolve()
            if p.is_dir() and p not in result:
                result.append(p)
        return result

    @staticmethod
    def _ini_keys(path: Path) -> dict[str, str]:
        """Extrai chaves simples de um INI para diagnóstico de conflitos."""
        result: dict[str, str] = {}
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return result
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            result[key.strip().lower()] = value.strip()
        return result

    def _scan_ini_environment(self, editor: ConfigFileEditor) -> tuple[list[Path], list[tuple[str, Path, str]]]:
        """Varre o inipath e retorna INIs encontrados e conflitos relevantes."""
        directories = self._inipath(editor)
        files: list[Path] = []
        conflicts: list[tuple[str, Path, str]] = []
        tracked: dict[str, tuple[Path, str]] = {}
        for directory in directories:
            for path in sorted(directory.glob("*.ini")):
                if path.resolve() == editor.path.resolve():
                    continue
                files.append(path)
                for key, value in self._ini_keys(path).items():
                    if key in {self.VIDEO_KEY, self.BACKEND_KEY, self.CHAIN_KEY, "filter", "prescale", "waitvsync", "syncrefresh", "switchres", "resolution", "aspect", "view"}:
                        if key in tracked and tracked[key][1] != value:
                            conflicts.append((key, path, value))
                        tracked[key] = (path, value)
        return files, conflicts

    def _build_ui(self) -> None:
        """Constrói a interface dos controles BGFX."""
        root = QVBoxLayout(self)
        group = QGroupBox("MAME BGFX — configuração global")
        form = QFormLayout(group)
        form.addRow("Driver de vídeo", self.video)
        form.addRow("Backend BGFX", self.backend)
        form.addRow("Chain global", self.chain)
        root.addWidget(group)
        root.addWidget(self.status)
        root.addWidget(self.scan)
        refresh = QPushButton("Recarregar / verificar INIs")
        refresh.clicked.connect(self.refresh)
        root.addWidget(refresh)
        root.addStretch(1)

    def refresh(self) -> None:
        """Lê a configuração e faz a varredura preventiva do inipath."""
        self.video.clear()
        self.backend.clear()
        self.chain.clear()
        self.video.addItems(("auto", "bgfx", "d3d", "opengl", "soft"))
        self.backend.addItems(self.BGFX_BACKENDS)
        ini_path = self._ini()
        editor = ConfigFileEditor(ini_path) if ini_path is not None else None
        if editor is None:
            self.status.setText("mame.ini não localizado.")
            self.scan.setText("Não foi possível analisar o inipath.")
            return
        driver = self._value(editor, self.VIDEO_KEY).lower() or "auto"
        backend = self._value(editor, self.BACKEND_KEY).lower() or "auto"
        configured = self._chain_name(self._value(editor, self.CHAIN_KEY))
        self.video.setCurrentText(driver)
        self.backend.setCurrentText(backend)
        root = self._root()
        chains_dir = root / "bgfx" / "chains" if root else None
        if chains_dir and chains_dir.is_dir():
            for p in sorted(chains_dir.glob("*.json")):
                self.chain.addItem(p.stem, p.stem)
        if configured and self.chain.findData(configured) < 0:
            self.chain.addItem(f"Atual: {configured}", configured)
        if configured:
            self.chain.setCurrentIndex(max(0, self.chain.findData(configured)))
        files, conflicts = self._scan_ini_environment(editor)
        if conflicts:
            details = "\n".join(f"{key}: {path.name} → {value}" for key, path, value in conflicts[:10])
            self.scan.setText(f"⚠ {len(conflicts)} conflito(s) detectado(s) no inipath:\n{details}")
        else:
            self.scan.setText(f"✓ INI environment normalizado para análise: {len(files)} arquivo(s) encontrado(s) no inipath.")
        self.status.setText(f"Driver={driver} | Backend={backend} | Chain global={configured or 'não definido'} | mame.ini={editor.path}")


__all__ = ["MameShadersPage"]
