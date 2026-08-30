"""Seletores de shaders BGFX do MAME V2.

A interface descobre os recursos diretamente no diretório BGFX configurado,
sem manter uma lista fixa que fique obsoleta quando o usuário atualizar o MAME.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root


class MameShadersPage(QWidget):
    """Editor visual dos chains e backends BGFX do MAME."""

    PATHS_FILE = data_root() / "emulator_paths.json"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.chain = QComboBox()
        self.backend = QComboBox()
        self.info = QLabel()
        self.info.setWordWrap(True)
        self._build_ui()
        self.refresh()

    @staticmethod
    def _paths() -> dict[str, Any]:
        """Carrega os caminhos definidos na guia Diretórios."""
        try:
            value = json.loads(MameShadersPage.PATHS_FILE.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _mame_root(self) -> Path | None:
        """Resolve a raiz MAME a partir do executável ou configuração registrada."""
        paths = self._paths()
        candidates = [paths.get("mame_root"), paths.get("mame_executable"), paths.get("mame_config")]
        for raw in candidates:
            if not raw:
                continue
            path = Path(str(raw)).expanduser()
            if path.suffix.lower() == ".exe":
                path = path.parent
            elif path.suffix:
                path = path.parent
            if (path / "bgfx").is_dir():
                return path
        return None

    def _build_ui(self) -> None:
        """Monta seletores de chain, backend e atualização do catálogo BGFX."""
        root = QVBoxLayout(self)
        group = QGroupBox("MAME BGFX")
        form = QFormLayout(group)
        form.addRow("Chain / preset", self.chain)
        form.addRow("Backend do shader", self.backend)
        root.addWidget(group)
        root.addWidget(self.info)

        actions = QHBoxLayout()
        refresh = QPushButton("Atualizar shaders")
        refresh.clicked.connect(self.refresh)
        actions.addStretch(1)
        actions.addWidget(refresh)
        root.addLayout(actions)
        root.addStretch(1)

    def refresh(self) -> None:
        """Redescobre chains JSON e diretórios de shaders existentes."""
        current_chain = self.chain.currentData()
        current_backend = self.backend.currentData()
        self.chain.clear()
        self.backend.clear()

        root = self._mame_root()
        if root is None:
            self.info.setText("Raiz MAME não localizada. Configure o executável/diretório na guia Diretórios.")
            return

        chains_dir = root / "bgfx" / "chains"
        shaders_dir = root / "bgfx" / "shaders"
        chains = sorted(
            p for p in chains_dir.glob("*.json") if p.is_file()
        ) if chains_dir.is_dir() else []
        backends = sorted(
            p.name for p in shaders_dir.iterdir() if p.is_dir()
        ) if shaders_dir.is_dir() else []

        for path in chains:
            self.chain.addItem(path.stem, str(path))
        for name in backends:
            self.backend.addItem(name, name)

        if current_chain:
            index = self.chain.findData(current_chain)
            if index >= 0:
                self.chain.setCurrentIndex(index)
        if current_backend:
            index = self.backend.findData(current_backend)
            if index >= 0:
                self.backend.setCurrentIndex(index)

        self.info.setText(
            f"BGFX encontrado em: {root / 'bgfx'}\n"
            f"Chains disponíveis: {len(chains)} | Backends disponíveis: {len(backends)}\n"
            "LICENSE, README e desktop.ini são ignorados automaticamente. "
            "O seletor usa os arquivos realmente instalados no MAME."
        )


__all__ = ["MameShadersPage"]
