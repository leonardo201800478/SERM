"""Configuração BGFX do MAME V2.

A página trata ``bgfx_screen_chains`` como configuração global do MAME e
reconhece que arquivos CFG por sistema podem conter overrides BGFX. O editor
permite manter esses overrides ou removê-los seletivamente para que o global
passe a prevalecer.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
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
    """Editor global de chains BGFX, com diagnóstico de overrides CFG."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    VIDEO_KEY = "video"
    CHAIN_KEY = "bgfx_screen_chains"
    BACKEND_KEY = "bgfx_backend"
    CFG_DIRECTORY_KEY = "cfg_directory"

    BGFX_BACKENDS = ("auto", "d3d9", "d3d11", "d3d12", "opengl", "gles", "metal", "vulkan")
    VIDEO_DRIVERS = ("auto", "bgfx", "d3d", "opengl", "soft")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.video_driver = QComboBox()
        self.chain = QComboBox()
        self.backend = QComboBox()
        self.remove_overrides = QCheckBox("Remover overrides BGFX dos CFGs ao aplicar global")
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

    def _cfg_directory(self, editor: ConfigFileEditor | None = None) -> Path | None:
        """Resolve o diretório CFG usando cfg_directory e a raiz do MAME."""
        editor = editor or self._editor()
        root = self._mame_root()
        raw = self._config_value(editor, self.CFG_DIRECTORY_KEY) if editor else ""
        if raw:
            path = Path(raw.strip().strip('"'))
            if not path.is_absolute() and root:
                path = root / path
            return path
        if root:
            return root / "cfg"
        return None

    def _build_ui(self) -> None:
        """Monta os seletores e controles de configuração BGFX."""
        root = QVBoxLayout(self)
        global_group = QGroupBox("MAME BGFX — configuração global")
        form = QFormLayout(global_group)
        self.video_driver.addItems(self.VIDEO_DRIVERS)
        self.video_driver.setEnabled(False)
        self.backend.addItems(self.BGFX_BACKENDS)
        form.addRow("Driver de vídeo atual", self.video_driver)
        form.addRow("Backend BGFX", self.backend)
        form.addRow("Chain / mapa global", self.chain)
        form.addRow("Aplicação global", self.remove_overrides)
        root.addWidget(global_group)

        override_group = QGroupBox("Overrides BGFX por sistema")
        override_layout = QVBoxLayout(override_group)
        self.override_summary = QLabel()
        self.override_summary.setWordWrap(True)
        override_layout.addWidget(self.override_summary)
        root.addWidget(override_group)
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
    def _config_value(editor: ConfigFileEditor | None, key: str) -> str:
        """Retorna o primeiro valor encontrado para uma chave do INI."""
        if editor is None:
            return ""
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
        """Normaliza chains sem destruir a sintaxe de múltiplas telas/janelas."""
        value = value.strip()
        if not value:
            return ""
        out: list[str] = []
        token = ""
        for char in value:
            if char in ",:":
                out.append(cls._chain_name(token))
                out.append(char)
                token = ""
            else:
                token += char
        out.append(cls._chain_name(token))
        return "".join(out)

    def _set_bgfx_enabled(self, enabled: bool) -> None:
        """Habilita os controles BGFX somente quando video=bgfx."""
        has_chain = bool(self.chain.currentData())
        self.chain.setEnabled(enabled and has_chain)
        self.backend.setEnabled(enabled)
        self.remove_overrides.setEnabled(enabled)
        if self._apply_button is not None:
            self._apply_button.setEnabled(enabled and has_chain)

    @staticmethod
    def _cfg_override(path: Path) -> tuple[bool, list[str]]:
        """Detecta overrides BGFX e retorna os chains encontrados no CFG."""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False, []
        if "<bgfx>" not in text:
            return False, []
        chains = re.findall(r'<screen\b[^>]*\bchain=["\']([^"\']+)["\']', text, re.IGNORECASE)
        return True, chains

    def _scan_cfg_overrides(self) -> list[tuple[Path, list[str]]]:
        """Lista somente CFGs que possuem configuração BGFX específica."""
        directory = self._cfg_directory()
        if directory is None or not directory.is_dir():
            return []
        found: list[tuple[Path, list[str]]] = []
        for path in sorted(directory.glob("*.cfg")):
            has_bgfx, chains = self._cfg_override(path)
            if has_bgfx:
                found.append((path, chains))
        return found

    @staticmethod
    def _remove_bgfx_block(text: str) -> str:
        """Remove somente o bloco <bgfx> de CFG, preservando mixer e demais dados."""
        pattern = re.compile(r"\s*<bgfx>.*?</bgfx>\s*", re.IGNORECASE | re.DOTALL)
        return pattern.sub("\n", text, count=1)

    def refresh(self) -> None:
        """Lê mame.ini, descobre chains e diagnostica overrides CFG."""
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
            self.override_summary.setText("Overrides CFG: não foi possível verificar.")
            return

        driver = self._config_value(editor, self.VIDEO_KEY).lower() or "auto"
        if self.video_driver.findText(driver) < 0:
            self.video_driver.addItem(driver)
        self.video_driver.setCurrentText(driver)

        configured_map = self._normalize_chain_map(self._config_value(editor, self.CHAIN_KEY))
        current_backend = self._config_value(editor, self.BACKEND_KEY).lower() or "auto"
        if self.backend.findText(current_backend) < 0:
            self.backend.addItem(current_backend)
        self.backend.setCurrentText(current_backend)

        chains_dir = root / "bgfx" / "chains" if root else None
        chains = sorted(p for p in chains_dir.glob("*.json") if p.is_file()) if chains_dir and chains_dir.is_dir() else []
        self.chain.addItem("default", "default")
        for path in chains:
            if self.chain.findData(path.stem) < 0:
                self.chain.addItem(path.stem, path.stem)
        if configured_map and self.chain.findData(configured_map) < 0:
            self.chain.addItem(f"Mapa atual: {configured_map}", configured_map)
        index = self.chain.findData(configured_map)
        if index >= 0:
            self.chain.setCurrentIndex(index)
        elif configured_map and "," not in configured_map and ":" not in configured_map:
            index = self.chain.findData(self._chain_name(configured_map))
            if index >= 0:
                self.chain.setCurrentIndex(index)

        overrides = self._scan_cfg_overrides()
        if overrides:
            preview = [f"{p.stem}: {', '.join(c) or 'BGFX sem chain explícito'}" for p, c in overrides[:12]]
            extra = f"\n… e mais {len(overrides) - 12}." if len(overrides) > 12 else ""
            self.override_summary.setText(f"{len(overrides)} CFG(s) possuem override BGFX:\n" + "\n".join(preview) + extra)
        else:
            self.override_summary.setText("Nenhum CFG com override BGFX foi encontrado.")

        is_bgfx = driver == "bgfx"
        self._set_bgfx_enabled(is_bgfx)
        self.status.setText(
            f"BGFX ATIVO | backend={current_backend} | global={configured_map or 'não definido'}"
            if is_bgfx else
            f"Driver atual: {driver}. BGFX bloqueado; selecione video=bgfx nas configurações do MAME."
        )
        self.info.setText(
            f"mame.ini: {self._mame_config()}\n"
            f"BGFX: {root / 'bgfx' if root else 'não localizado'}\n"
            f"CFG: {self._cfg_directory(editor) or 'não localizado'}\n"
            f"Chains encontrados: {len(chains)}\n"
            "Vírgula = telas na mesma janela; dois-pontos = janelas físicas."
        )

    def apply_global(self) -> None:
        """Grava o chain global e opcionalmente remove somente overrides BGFX dos CFGs."""
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
            QMessageBox.critical(self, "MAME BGFX", f"Não foi possível aplicar ao mame.ini:\n{exc}")
            return

        removed = 0
        if self.remove_overrides.isChecked():
            for path, _chains in self._scan_cfg_overrides():
                try:
                    original = path.read_text(encoding="utf-8", errors="replace")
                    updated = self._remove_bgfx_block(original)
                    if updated != original:
                        backup_path = path.with_suffix(path.suffix + ".serm.bak")
                        if not backup_path.exists():
                            backup_path.write_text(original, encoding="utf-8")
                        path.write_text(updated, encoding="utf-8", newline="")
                        removed += 1
                except OSError:
                    continue

        self.refresh()
        QMessageBox.information(
            self,
            "MAME BGFX",
            f"Global aplicado:\n{self.CHAIN_KEY} = {chain_map}\n\n"
            f"Backend preservado: {self._config_value(editor, self.BACKEND_KEY) or 'auto'}\n"
            f"CFGs com override removidos: {removed}\n\nBackup do mame.ini:\n{backup}",
        )

    def verify_effective_config(self) -> None:
        """Consulta o próprio MAME com -showconfig e exibe a configuração global efetiva."""
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
        lines = [line.strip() for line in output.splitlines() if any(line.strip().startswith(key) for key in wanted)]
        if not lines:
            lines = ["O MAME não retornou as opções BGFX esperadas em -showconfig."]
        overrides = self._scan_cfg_overrides()
        QMessageBox.information(
            self,
            "MAME BGFX — configuração efetiva",
            "\n".join(lines) + f"\n\nCFGs com override BGFX detectados: {len(overrides)}",
        )


__all__ = ["MameShadersPage"]
