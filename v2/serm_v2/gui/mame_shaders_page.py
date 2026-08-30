"""Configuração BGFX do MAME V2.

A página trata ``bgfx_screen_chains`` como uma configuração de mapeamento
janela/tela do MAME, e não como um caminho para um JSON. O valor global é
persistido no mame.ini; arquivos CFG específicos continuam sendo uma camada
separada para os ajustes salvos pelo próprio MAME.
"""
from __future__ import annotations

import json
import subprocess
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
)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from ..runtime.paths import data_root
from .directories_guide_page import ConfigFileEditor


class MameShadersPage(QWidget):
    """Editor global de chains BGFX, respeitando o driver do MAME."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    VIDEO_KEY = "video"
    CHAIN_KEY = "bgfx_screen_chains"
    BACKEND_KEY = "bgfx_backend"

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
        try:
            value = json.loads(MameShadersPage.PATHS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _mame_root(self) -> Path | None:
        """Resolve a raiz da instalação MAME pelos caminhos persistidos."""
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
        """Localiza o mame.ini real do MAME."""
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

    def _mame_executable(self) -> Path | None:
        """Resolve o executável MAME a partir dos caminhos persistidos ou da raiz."""
        paths = self._paths()
        raw = paths.get("mame_executable")
        if raw:
            path = Path(str(raw)).expanduser()
            if path.is_file():
                return path
        root = self._mame_root()
        if root:
            candidate = root / "mame.exe"
            if candidate.is_file():
                return candidate
        return None

    def _editor(self) -> ConfigFileEditor | None:
        """Abre o mame.ini pelo editor que preserva comentários e estrutura."""
        path = self._mame_config()
        if path is None:
            return None
        try:
            return ConfigFileEditor(path)
        except OSError:
            return None

    def _build_ui(self) -> None:
        """Monta os seletores de driver, backend e chain BGFX."""
        root = QVBoxLayout(self)
        group = QGroupBox("MAME BGFX — configuração global")
        form = QFormLayout(group)

        self.video_driver.addItems(self.VIDEO_DRIVERS)
        self.video_driver.setEnabled(False)
        self.backend.addItems(self.BGFX_BACKENDS)
        form.addRow("Driver de vídeo atual", self.video_driver)
        form.addRow("Backend BGFX", self.backend)
        form.addRow("Chain / mapa global", self.chain)
        root.addWidget(group)
        root.addWidget(self.status)
        root.addWidget(self.info)

        actions = QHBoxLayout()
        reload_button = QPushButton("Recarregar")
        reload_button.clicked.connect(self.refresh)
        verify_button = QPushButton("Verificar MAME")
        verify_button.clicked.connect(self.verify_effective_config)
        self._apply_button = QPushButton("Aplicar global")
        self._apply_button.setProperty("role", "primary")
        self._apply_button.clicked.connect(self.apply_global)
        actions.addStretch(1)
        actions.addWidget(reload_button)
        actions.addWidget(verify_button)
        actions.addWidget(self._apply_button)
        root.addLayout(actions)
        root.addStretch(1)

    @staticmethod
    def _config_value(editor: ConfigFileEditor, key: str) -> str:
        """Retorna o primeiro valor encontrado para uma chave do INI."""
        values = editor.values(key)
        return values[0].strip() if values else ""

    @staticmethod
    def _chain_name(value: str) -> str:
        """Converte caminho/JSON legado para um identificador de chain do MAME."""
        value = value.strip().strip('"').replace("\\", "/")
        if "/" in value:
            value = value.rsplit("/", 1)[-1]
        if value.lower().endswith(".json"):
            value = value[:-5]
        return value.strip()

    @classmethod
    def _normalize_chain_map(cls, value: str) -> str:
        """Normaliza todos os chains de uma expressão BGFX, preservando , e :."""
        value = value.strip()
        if not value:
            return ""
        parts: list[str] = []
        token = ""
        for char in value:
            if char in ",:":
                parts.append(cls._chain_name(token))
                parts.append(char)
                token = ""
            else:
                token += char
        parts.append(cls._chain_name(token))
        return "".join(parts)

    def _set_bgfx_enabled(self, enabled: bool) -> None:
        """Habilita os controles BGFX somente quando video=bgfx."""
        has_chain = bool(self.chain.currentData())
        self.chain.setEnabled(enabled and has_chain)
        self.backend.setEnabled(enabled)
        if self._apply_button is not None:
            self._apply_button.setEnabled(enabled and has_chain)

    def refresh(self) -> None:
        """Lê mame.ini e atualiza os controles com a configuração efetiva salva."""
        editor = self._editor()
        root = self._mame_root()
        self.chain.clear()
        self.backend.clear()
        self.backend.addItems(self.BGFX_BACKENDS)

        if editor is None:
            self.video_driver.setCurrentText("auto")
            self._set_bgfx_enabled(False)
            self.status.setText("mame.ini não localizado.")
            self.info.setText(f"Raiz MAME: {root or 'não localizada'}")
            return

        driver = self._config_value(editor, self.VIDEO_KEY).lower() or "auto"
        if self.video_driver.findText(driver) < 0:
            self.video_driver.addItem(driver)
        self.video_driver.setCurrentText(driver)

        configured_map = self._normalize_chain_map(self._config_value(editor, self.CHAIN_KEY))
        current_backend = self._config_value(editor, self.BACKEND_KEY).lower() or "auto"
        backend_index = self.backend.findText(current_backend)
        if backend_index < 0:
            self.backend.addItem(current_backend)
            backend_index = self.backend.findText(current_backend)
        self.backend.setCurrentIndex(backend_index)

        chains_dir = root / "bgfx" / "chains" if root else None
        chains = sorted(
            p for p in chains_dir.glob("*.json") if p.is_file()
        ) if chains_dir and chains_dir.is_dir() else []

        # Presets de uma tela e mapas documentados para múltiplas telas/janelas.
        self.chain.addItem("default", "default")
        for path in chains:
            if self.chain.findData(path.stem) < 0:
                self.chain.addItem(path.stem, path.stem)

        # Se o valor global contém , ou :, ele é um mapa. Mantemos a expressão
        # completa selecionável para não destruir uma configuração multicâmera.
        if configured_map and self.chain.findData(configured_map) < 0:
            self.chain.addItem(f"Mapa atual: {configured_map}", configured_map)

        index = self.chain.findData(configured_map)
        if index >= 0:
            self.chain.setCurrentIndex(index)
        elif configured_map:
            # Para um único chain, seleciona o preset correspondente.
            single = self._chain_name(configured_map)
            index = self.chain.findData(single)
            if index >= 0:
                self.chain.setCurrentIndex(index)

        is_bgfx = driver == "bgfx"
        self._set_bgfx_enabled(is_bgfx)
        if is_bgfx:
            self.status.setText(
                f"BGFX ATIVO | backend={current_backend} | bgfx_screen_chains={configured_map or 'não definido'}"
            )
        else:
            self.status.setText(
                f"Driver atual: {driver}. BGFX bloqueado; selecione video=bgfx nas configurações do MAME."
            )

        self.info.setText(
            f"mame.ini: {self._mame_config()}\n"
            f"BGFX: {root / 'bgfx' if root else 'não localizado'}\n"
            f"Chains encontrados: {len(chains)}\n"
            "Sintaxe MAME: vírgula = telas na mesma janela; dois-pontos = janelas físicas."
        )

    def apply_global(self) -> None:
        """Grava somente bgfx_screen_chains no mame.ini e preserva o backend atual."""
        editor = self._editor()
        if editor is None:
            QMessageBox.warning(self, "MAME BGFX", "mame.ini não localizado.")
            return
        driver = self._config_value(editor, self.VIDEO_KEY).lower()
        if driver != "bgfx":
            QMessageBox.warning(self, "MAME BGFX", "video não está configurado como bgfx.")
            return
        chain_map = self._normalize_chain_map(str(self.chain.currentData() or ""))
        if not chain_map:
            QMessageBox.warning(self, "MAME BGFX", "Nenhum chain BGFX válido foi selecionado.")
            return
        try:
            editor.set_value(self.CHAIN_KEY, chain_map)
            backup = editor.save()
        except (OSError, KeyError) as exc:
            QMessageBox.critical(self, "MAME BGFX", f"Não foi possível aplicar:\n{exc}")
            return
        self.refresh()
        QMessageBox.information(
            self,
            "MAME BGFX",
            f"Configuração global aplicada:\n\n{self.CHAIN_KEY} = {chain_map}\n\n"
            f"Backend preservado: {self._config_value(editor, self.BACKEND_KEY) or 'auto'}\n\nBackup:\n{backup}",
        )

    def verify_effective_config(self) -> None:
        """Consulta o próprio MAME com -showconfig para validar a configuração salva."""
        executable = self._mame_executable()
        if executable is None:
            QMessageBox.warning(self, "MAME BGFX", "mame.exe não localizado.")
            return
        try:
            completed = subprocess.run(
                [str(executable), "-showconfig"],
                cwd=str(executable.parent),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            QMessageBox.critical(self, "MAME BGFX", f"Falha ao consultar o MAME:\n{exc}")
            return

        output = completed.stdout + "\n" + completed.stderr
        wanted = ("video", "bgfx_backend", "bgfx_screen_chains")
        lines = [
            line.strip()
            for line in output.splitlines()
            if any(line.strip().startswith(key) for key in wanted)
        ]
        if not lines:
            lines = ["O MAME não retornou as opções BGFX esperadas em -showconfig."]
        QMessageBox.information(
            self,
            "MAME BGFX — configuração efetiva",
            "\n".join(lines),
        )


__all__ = ["MameShadersPage"]
