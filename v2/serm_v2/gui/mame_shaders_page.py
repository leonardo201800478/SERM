"""Configuração global de chains BGFX do MAME V2.

A GUI não trata um arquivo JSON como configuração por si só. Um chain só é
selecionável quando o driver de vídeo efetivo do MAME é ``bgfx``. A aplicação
global é feita pela chave nativa ``bgfx_screen_chains`` do mame.ini, preservando
backup e formatação através de ConfigFileEditor.
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
    """Editor global dos chains BGFX instalados no MAME."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    VIDEO_KEY = "video"
    CHAIN_KEY = "bgfx_screen_chains"
    BACKEND_KEY = "bgfx_backend"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.video_driver = QComboBox()
        self.chain = QComboBox()
        self.backend = QComboBox()
        self.status = QLabel()
        self.info = QLabel()
        self.status.setWordWrap(True)
        self.info.setWordWrap(True)
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
        self.video_driver.addItems(["auto", "accel", "soft", "opengl", "bgfx"])
        form.addRow("Driver de vídeo", self.video_driver)
        form.addRow("Chain BGFX", self.chain)
        form.addRow("Backend BGFX", self.backend)
        root.addWidget(group)
        root.addWidget(self.status)
        root.addWidget(self.info)

        actions = QHBoxLayout()
        reload_button = QPushButton("Recarregar")
        reload_button.clicked.connect(self.refresh)
        apply_button = QPushButton("Aplicar globalmente")
        apply_button.setProperty("role", "primary")
        apply_button.clicked.connect(self.apply_global)
        actions.addStretch(1)
        actions.addWidget(reload_button)
        actions.addWidget(apply_button)
        root.addLayout(actions)
        root.addStretch(1)
        self.video_driver.currentTextChanged.connect(self._video_changed)

    def _video_changed(self, value: str) -> None:
        """Limita a seleção de chain ao driver BGFX e informa a consequência."""
        is_bgfx = value.lower() == "bgfx"
        self.chain.setEnabled(is_bgfx)
        self.backend.setEnabled(is_bgfx)
        if not is_bgfx:
            self.status.setText(
                f"Driver selecionado: {value}. Chains BGFX estão desabilitados porque "
                "bgfx_screen_chains só é efetivo com video bgfx."
            )
        else:
            self.status.setText("Driver BGFX ativo: o chain poderá ser aplicado globalmente no mame.ini.")

    @staticmethod
    def _config_value(editor: ConfigFileEditor, key: str) -> str:
        """Retorna o primeiro valor existente para uma chave de configuração."""
        values = editor.values(key)
        return values[0].strip() if values else ""

    def refresh(self) -> None:
        """Lê o driver e o chain atuais e redescobre recursos BGFX instalados."""
        editor = self._editor()
        root = self._mame_root()
        self.chain.clear()
        self.backend.clear()

        if editor is None:
            self.video_driver.setCurrentText("auto")
            self.video_driver.setEnabled(False)
            self.chain.setEnabled(False)
            self.backend.setEnabled(False)
            self.status.setText("mame.ini não localizado. Configure-o primeiro na guia Diretórios.")
            return

        self.video_driver.setEnabled(True)
        driver = self._config_value(editor, self.VIDEO_KEY).lower() or "auto"
        if self.video_driver.findText(driver) < 0:
            self.video_driver.addItem(driver)
        self.video_driver.setCurrentText(driver)

        current_chain = self._config_value(editor, self.CHAIN_KEY)
        current_backend = self._config_value(editor, self.BACKEND_KEY)

        chains_dir = root / "bgfx" / "chains" if root else None
        shaders_dir = root / "bgfx" / "shaders" if root else None
        chains = sorted(p for p in chains_dir.glob("*.json") if p.is_file()) if chains_dir and chains_dir.is_dir() else []
        backends = sorted(p.name for p in shaders_dir.iterdir() if p.is_dir()) if shaders_dir and shaders_dir.is_dir() else []

        for path in chains:
            self.chain.addItem(path.stem, str(path))
        if current_chain and self.chain.findText(current_chain) < 0:
            self.chain.addItem(f"{current_chain} (configurado)", current_chain)
        if self.chain.count() == 0:
            self.chain.addItem("Nenhum chain encontrado", "")
        if current_chain:
            index = self.chain.findData(current_chain)
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
        elif self.backend.count():
            self.backend.setCurrentIndex(0)

        self._video_changed(driver)
        self.info.setText(
            f"BGFX: {root / 'bgfx' if root else 'não localizado'}\n"
            f"Chains instalados: {len(chains)} | Backends detectados: {len(backends)}\n"
            "O chain é aplicado por bgfx_screen_chains; o arquivo .json não é executado diretamente."
        )

    def apply_global(self) -> None:
        """Aplica o chain global no mame.ini somente quando o driver é BGFX."""
        editor = self._editor()
        if editor is None:
            QMessageBox.warning(self, "MAME BGFX", "mame.ini não localizado. Configure o arquivo na guia Diretórios.")
            return
        driver = self.video_driver.currentText().strip().lower()
        if driver != "bgfx":
            QMessageBox.warning(
                self,
                "MAME BGFX",
                "O chain BGFX não pode ser aplicado enquanto o driver de vídeo não for 'bgfx'. "
                "Selecione BGFX primeiro.",
            )
            return
        chain = str(self.chain.currentData() or self.chain.currentText()).strip()
        if not chain or chain.startswith("Nenhum chain"):
            QMessageBox.warning(self, "MAME BGFX", "Nenhum chain BGFX válido foi selecionado.")
            return
        try:
            editor.set_value(self.VIDEO_KEY, "bgfx")
            editor.set_value(self.CHAIN_KEY, chain)
            backup = editor.save()
        except (OSError, KeyError) as exc:
            QMessageBox.critical(self, "MAME BGFX", f"Não foi possível aplicar a configuração:\n{exc}")
            return
        self.refresh()
        QMessageBox.information(
            self,
            "MAME BGFX",
            f"Chain global aplicado: {chain}\n\nBackup criado em:\n{backup}",
        )


__all__ = ["MameShadersPage"]
