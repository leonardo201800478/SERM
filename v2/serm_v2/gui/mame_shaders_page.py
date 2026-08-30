"""Configuração global de chains BGFX do MAME V2.

O driver de vídeo é lido do ``mame.ini`` e não é alterado por esta página.
Chains e backends BGFX só ficam disponíveis quando ``video=bgfx``. O valor
persistido em ``bgfx_screen_chains`` é sempre o identificador do chain, sem
caminho absoluto e sem ``.json``.
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
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root
from .directories_guide_page import ConfigFileEditor


class MameShadersPage(QWidget):
    """Editor do chain BGFX global, subordinado ao driver do MAME."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    VIDEO_KEY = "video"
    CHAIN_KEY = "bgfx_screen_chains"
    BACKEND_KEY = "bgfx_backend"
    VIDEO_DRIVERS = ("auto", "bgfx", "opengl", "soft")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.video_driver = QComboBox()
        self.video_driver.setEnabled(False)
        self.chain = QComboBox()
        self.backend = QComboBox()
        self.status = QLabel()
        self.info = QLabel()
        self.status.setWordWrap(True)
        self.info.setWordWrap(True)
        self._apply_button: QPushButton | None = None
        self._build_ui()
        self.refresh()

    @staticmethod
    def _paths() -> dict[str, Any]:
        """Carrega os caminhos definidos pelo SERM."""
        path = MameShadersPage.PATHS_FILE
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _mame_config(self) -> Path | None:
        """Obtém o mame.ini configurado e verifica sua existência."""
        raw = self._paths().get("mame_config")
        if not raw:
            return None
        path = Path(str(raw)).expanduser()
        return path if path.is_file() else None

    def _mame_root(self) -> Path | None:
        """Resolve a raiz da instalação MAME a partir dos caminhos configurados."""
        paths = self._paths()
        for key in ("mame_root", "mame_executable", "mame_config"):
            raw = paths.get(key)
            if not raw:
                continue
            path = Path(str(raw)).expanduser()
            if path.suffix.lower() == ".exe" or path.suffix:
                path = path.parent
            if (path / "bgfx").is_dir():
                return path
        config = self._mame_config()
        if config and (config.parent / "bgfx").is_dir():
            return config.parent
        return None

    def _editor(self) -> ConfigFileEditor | None:
        """Abre o mame.ini real através do editor preservador de estrutura."""
        path = self._mame_config()
        if path is None:
            return None
        try:
            return ConfigFileEditor(path)
        except OSError:
            return None

    def _build_ui(self) -> None:
        """Monta os seletores e ações do chain global."""
        root = QVBoxLayout(self)
        group = QGroupBox("MAME BGFX — Chain global")
        form = QFormLayout(group)
        self.video_driver.addItems(self.VIDEO_DRIVERS)
        form.addRow("Driver de vídeo atual", self.video_driver)
        form.addRow("Chain BGFX", self.chain)
        form.addRow("Backend BGFX", self.backend)
        root.addWidget(group)
        root.addWidget(self.status)
        root.addWidget(self.info)

        actions = QHBoxLayout()
        reload_button = QPushButton("Recarregar")
        reload_button.clicked.connect(self.refresh)
        self._apply_button = QPushButton("Aplicar chain global")
        self._apply_button.setProperty("role", "primary")
        self._apply_button.clicked.connect(self.apply_global)
        actions.addStretch(1)
        actions.addWidget(reload_button)
        actions.addWidget(self._apply_button)
        root.addLayout(actions)
        root.addStretch(1)

    @staticmethod
    def _config_value(editor: ConfigFileEditor, key: str) -> str:
        """Retorna o primeiro valor existente para uma chave de configuração."""
        values = editor.values(key)
        return values[0].strip() if values else ""

    @staticmethod
    def _chain_name(value: str) -> str:
        """Normaliza valor para o identificador aceito em ``bgfx_screen_chains``."""
        normalized = value.strip().strip('"').replace("\\", "/")
        if "/" in normalized:
            normalized = normalized.rsplit("/", 1)[-1]
        if normalized.lower().endswith(".json"):
            normalized = normalized[:-5]
        return normalized.strip()

    def _set_bgfx_enabled(self, enabled: bool) -> None:
        """Habilita controles BGFX exclusivamente quando o driver atual é BGFX."""
        self.chain.setEnabled(enabled)
        self.backend.setEnabled(enabled)
        if self._apply_button is not None:
            self._apply_button.setEnabled(enabled and bool(self.chain.currentData()))

    def refresh(self) -> None:
        """Lê o mame.ini e redescobre chains/backends instalados."""
        editor = self._editor()
        root = self._mame_root()
        self.chain.clear()
        self.backend.clear()

        if editor is None:
            self.video_driver.setCurrentText("auto")
            self._set_bgfx_enabled(False)
            self.status.setText("mame.ini não localizado. Configure-o primeiro na guia Diretórios.")
            return

        driver = self._config_value(editor, self.VIDEO_KEY).lower() or "auto"
        if self.video_driver.findText(driver) < 0:
            self.video_driver.addItem(driver)
        self.video_driver.setCurrentText(driver)

        configured_chain = self._chain_name(self._config_value(editor, self.CHAIN_KEY))
        current_backend = self._config_value(editor, self.BACKEND_KEY)

        chains_dir = root / "bgfx" / "chains" if root else None
        shaders_dir = root / "bgfx" / "shaders" if root else None
        chains = sorted(
            p for p in chains_dir.glob("*.json") if p.is_file()
        ) if chains_dir and chains_dir.is_dir() else []
        backends = sorted(
            p.name for p in shaders_dir.iterdir() if p.is_dir()
        ) if shaders_dir and shaders_dir.is_dir() else []

        for path in chains:
            self.chain.addItem(path.stem, path.stem)
        if configured_chain and self.chain.findData(configured_chain) < 0:
            self.chain.addItem(f"{configured_chain} (configurado)", configured_chain)
        if self.chain.count() == 0:
            self.chain.addItem("Nenhum chain encontrado", "")
        if configured_chain:
            index = self.chain.findData(configured_chain)
            if index >= 0:
                self.chain.setCurrentIndex(index)

        for name in backends:
            self.backend.addItem(name, name)
        if current_backend and self.backend.findData(current_backend) < 0:
            self.backend.addItem(current_backend, current_backend)
        if current_backend:
            index = self.backend.findData(current_backend)
            if index >= 0:
                self.backend.setCurrentIndex(index)

        is_bgfx = driver == "bgfx"
        self._set_bgfx_enabled(is_bgfx)
        if is_bgfx:
            self.status.setText(
                "BGFX ativo. O chain selecionado será gravado no mame.ini "
                "somente como nome do preset, sem caminho e sem .json."
            )
        else:
            self.status.setText(
                f"Driver atual: {driver}. Chains BGFX estão bloqueados; "
                "selecione 'bgfx' na guia Configurações MAME para habilitá-los."
            )

        self.info.setText(
            f"BGFX: {root / 'bgfx' if root else 'não localizado'}\n"
            f"Chains instalados: {len(chains)} | Backends detectados: {len(backends)}\n"
            "Chain persistido: bgfx_screen_chains=<nome-do-chain>."
        )

    def apply_global(self) -> None:
        """Grava apenas o chain global no mame.ini quando BGFX está ativo."""
        editor = self._editor()
        if editor is None:
            QMessageBox.warning(self, "MAME BGFX", "mame.ini não localizado. Configure o arquivo na guia Diretórios.")
            return

        driver = self._config_value(editor, self.VIDEO_KEY).strip().lower()
        if driver != "bgfx":
            QMessageBox.warning(
                self,
                "MAME BGFX",
                "O driver atual do MAME não é 'bgfx'. Altere video para bgfx na guia Configurações MAME antes de aplicar um chain.",
            )
            return

        chain = self._chain_name(str(self.chain.currentData() or ""))
        if not chain:
            QMessageBox.warning(self, "MAME BGFX", "Nenhum chain BGFX válido foi selecionado.")
            return

        # O backend é apenas uma preferência do BGFX; esta página não o altera.
        try:
            editor.set_value(self.CHAIN_KEY, chain)
            backup = editor.save()
        except (OSError, KeyError) as exc:
            QMessageBox.critical(self, "MAME BGFX", f"Não foi possível aplicar a configuração:\n{exc}")
            return

        self.refresh()
        QMessageBox.information(
            self,
            "MAME BGFX",
            f"Chain global aplicado:\n\nbgfx_screen_chains = {chain}\n\nBackup criado em:\n{backup}",
        )


__all__ = ["MameShadersPage"]
