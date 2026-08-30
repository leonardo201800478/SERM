"""Configuração global de chains BGFX do MAME V2.

A página lê a configuração efetiva do mame.ini, descobre os chains instalados
na pasta bgfx/chains e usa somente os valores oficiais aceitos pelo MAME para
bgfx_backend. O backend não é inferido a partir das pastas de shaders.
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
    """Editor do chain BGFX global, subordinado ao driver de vídeo do MAME."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    VIDEO_KEY = "video"
    CHAIN_KEY = "bgfx_screen_chains"
    BACKEND_KEY = "bgfx_backend"

    # Valores documentados pelo MAME 0.289.
    BGFX_BACKENDS = ("auto", "d3d9", "d3d11", "d3d12", "opengl", "gles", "metal", "vulkan")
    VIDEO_DRIVERS = ("auto", "bgfx", "d3d", "opengl", "soft")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.video_driver = QComboBox()
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
        """Carrega os caminhos persistidos pelo SERM."""
        path = MameShadersPage.PATHS_FILE
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _mame_root(self) -> Path | None:
        """Resolve a instalação MAME por qualquer caminho persistido pelo SERM."""
        paths = self._paths()
        candidates: list[Path] = []
        for key in ("mame_root", "mame_executable", "mame_config", "mame_ini"):
            raw = paths.get(key)
            if raw:
                candidates.append(Path(str(raw)).expanduser())
        for candidate in candidates:
            path = candidate
            if path.is_file() or path.suffix.lower() in {".exe", ".ini"}:
                path = path.parent
            if path.name.lower() == "mame.ini":
                path = path.parent
            if (path / "mame.exe").is_file() or (path / "bgfx").is_dir():
                return path
        return None

    def _mame_config(self) -> Path | None:
        """Localiza o mame.ini real, mesmo quando o JSON não possui mame_config."""
        paths = self._paths()
        for key in ("mame_config", "mame_ini"):
            raw = paths.get(key)
            if raw:
                path = Path(str(raw)).expanduser()
                if path.is_file():
                    return path
        root = self._mame_root()
        if root:
            for name in ("mame.ini", "MAME.ini"):
                path = root / name
                if path.is_file():
                    return path
        return None

    def _editor(self) -> ConfigFileEditor | None:
        """Abre o mame.ini através do editor que preserva sua estrutura."""
        path = self._mame_config()
        if path is None:
            return None
        try:
            return ConfigFileEditor(path)
        except OSError:
            return None

    def _build_ui(self) -> None:
        """Monta os seletores e ações da configuração BGFX."""
        root = QVBoxLayout(self)
        group = QGroupBox("MAME BGFX — Chain global")
        form = QFormLayout(group)
        self.video_driver.addItems(self.VIDEO_DRIVERS)
        self.video_driver.setEnabled(False)
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
        """Retorna o primeiro valor de uma chave do INI."""
        values = editor.values(key)
        return values[0].strip() if values else ""

    @staticmethod
    def _chain_name(value: str) -> str:
        """Normaliza caminho/JSON legado para o identificador aceito pelo MAME."""
        value = value.strip().strip('"').replace("\\", "/")
        if "/" in value:
            value = value.rsplit("/", 1)[-1]
        if value.lower().endswith(".json"):
            value = value[:-5]
        return value.strip()

    def _set_bgfx_enabled(self, enabled: bool) -> None:
        """Bloqueia todos os controles BGFX quando o driver não é BGFX."""
        self.chain.setEnabled(enabled and bool(self.chain.currentData()))
        self.backend.setEnabled(enabled)
        if self._apply_button is not None:
            self._apply_button.setEnabled(enabled and bool(self.chain.currentData()))

    def refresh(self) -> None:
        """Lê o mame.ini e descobre chains instalados."""
        editor = self._editor()
        root = self._mame_root()
        self.chain.clear()
        self.backend.clear()
        self.backend.addItems(self.BGFX_BACKENDS)

        if editor is None:
            self.video_driver.setCurrentText("auto")
            self._set_bgfx_enabled(False)
            self.status.setText(
                "mame.ini não localizado. A página procura mame_config, mame_ini, "
                "mame_executable e finalmente mame.ini na raiz do MAME."
            )
            self.info.setText(f"Caminho persistido do MAME: {root or 'não localizado'}")
            return

        driver = self._config_value(editor, self.VIDEO_KEY).strip().lower() or "auto"
        if self.video_driver.findText(driver) < 0:
            self.video_driver.addItem(driver)
        self.video_driver.setCurrentText(driver)

        configured_chain = self._chain_name(self._config_value(editor, self.CHAIN_KEY))
        current_backend = self._config_value(editor, self.BACKEND_KEY).strip().lower() or "auto"
        backend_index = self.backend.findText(current_backend)
        if backend_index < 0:
            self.backend.addItem(current_backend)
            backend_index = self.backend.findText(current_backend)
        self.backend.setCurrentIndex(backend_index)

        chains_dir = root / "bgfx" / "chains" if root else None
        chains = sorted(p for p in chains_dir.glob("*.json") if p.is_file()) if chains_dir and chains_dir.is_dir() else []

        for path in chains:
            self.chain.addItem(path.stem, path.stem)
        if configured_chain and self.chain.findData(configured_chain) < 0:
            self.chain.addItem(f"{configured_chain} (configurado)", configured_chain)
        if self.chain.count() == 0:
            self.chain.addItem("Nenhum chain encontrado", "")
        elif configured_chain:
            index = self.chain.findData(configured_chain)
            if index >= 0:
                self.chain.setCurrentIndex(index)

        is_bgfx = driver == "bgfx"
        self._set_bgfx_enabled(is_bgfx)
        if is_bgfx:
            self.status.setText(
                f"BGFX ATIVO | backend={current_backend} | chain={configured_chain or 'não definido'}"
            )
        else:
            self.status.setText(
                f"Driver atual: {driver}. Chains BGFX bloqueados. "
                "O MAME só usa bgfx_screen_chains quando video=bgfx."
            )

        self.info.setText(
            f"mame.ini: {self._mame_config()}\n"
            f"BGFX: {root / 'bgfx' if root else 'não localizado'}\n"
            f"Chains instalados: {len(chains)} | Backends oficiais: {len(self.BGFX_BACKENDS)}\n"
            "bgfx_backend é o backend do BGFX; ele não é inferido pelas pastas de shaders."
        )

    def apply_global(self) -> None:
        """Aplica somente o chain global; não altera driver nem backend."""
        editor = self._editor()
        if editor is None:
            QMessageBox.warning(self, "MAME BGFX", "mame.ini não localizado.")
            return
        driver = self._config_value(editor, self.VIDEO_KEY).strip().lower()
        if driver != "bgfx":
            QMessageBox.warning(self, "MAME BGFX", "video não está configurado como bgfx.")
            return
        chain = self._chain_name(str(self.chain.currentData() or ""))
        if not chain:
            QMessageBox.warning(self, "MAME BGFX", "Nenhum chain BGFX válido foi selecionado.")
            return
        try:
            editor.set_value(self.CHAIN_KEY, chain)
            backup = editor.save()
        except (OSError, KeyError) as exc:
            QMessageBox.critical(self, "MAME BGFX", f"Não foi possível aplicar:\n{exc}")
            return
        self.refresh()
        QMessageBox.information(
            self,
            "MAME BGFX",
            f"Chain global aplicado:\n\nbgfx_screen_chains = {chain}\n\nBackup:\n{backup}",
        )


__all__ = ["MameShadersPage"]
