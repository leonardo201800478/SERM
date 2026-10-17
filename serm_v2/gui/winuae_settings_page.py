"""Grouped editor for the WinUAE global options in its [WinUAE] section."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root
from .winuae_config import WinUAEConfigEditor


@dataclass(frozen=True, slots=True)
class WinUAEOption:
    key: str
    label: str
    kind: str = "bool"
    minimum: int = -2_147_483_648
    maximum: int = 2_147_483_647


class WinUAESettingsPage(QWidget):
    PATHS_FILE = data_root() / "emulator_paths.json"
    GROUPS = {
        "Geral e compatibilidade": (
            WinUAEOption("ConfigurationCache", "Usar cache de configurações"),
            WinUAEOption("RelativePaths", "Usar caminhos relativos"),
            WinUAEOption("RecursiveROMScan", "Busca recursiva de ROMs"),
            WinUAEOption("QuickStartCompatibility", "Compatibilidade do Quickstart"),
            WinUAEOption("QuickStartConfiguration", "Configuração Quickstart", "integer"),
            WinUAEOption("QuickStartHostConfig", "Perfil do computador hospedeiro", "text"),
            WinUAEOption("QuickStartModel", "Modelo Quickstart", "integer"),
            WinUAEOption("SaveImageOriginalPath", "Manter caminho original da imagem"),
        ),
        "Interface": (
            WinUAEOption("GUIFullscreen", "Abrir interface em tela cheia"),
            WinUAEOption("GUIResize", "Permitir redimensionar a interface"),
            WinUAEOption("GUISizeX", "Largura da interface", "integer", 1, 32768),
            WinUAEOption("GUISizeY", "Altura da interface", "integer", 1, 32768),
            WinUAEOption("GUIPosX", "Posição horizontal da interface", "integer"),
            WinUAEOption("GUIPosY", "Posição vertical da interface", "integer"),
            WinUAEOption("MainPosX", "Posição horizontal da janela principal", "integer"),
            WinUAEOption("MainPosY", "Posição vertical da janela principal", "integer"),
        ),
        "Artes e apresentação": (
            WinUAEOption("ArtCache", "Usar cache de artes"),
            WinUAEOption("ArtImageCount", "Quantidade de imagens de arte", "integer", 0, 10000),
            WinUAEOption("ArtImageWidth", "Largura das imagens de arte", "integer", 0, 32768),
            WinUAEOption(
                "ArtImageWidthFS", "Largura das imagens em tela cheia", "integer", 0, 32768
            ),
        ),
        "Busca de configurações": (
            WinUAEOption(
                "ConfigFileHardware_Auto", "Detectar configurações de hardware automaticamente"
            ),
            WinUAEOption("ConfigFileHardwareSearch", "Filtro de busca de hardware", "text"),
            WinUAEOption("ConfigFileSearch", "Filtro de busca de configurações", "text"),
        ),
        "Drivers": (
            WinUAEOption(
                "SoundDriverMask", "Máscara de drivers de áudio", "integer", 0, 2_147_483_647
            ),
        ),
    }

    GROUP_SECTIONS = {
        "Geral e compatibilidade": "emulators",
        "Interface": "emulators",
        "Artes e apresentação": "video",
        "Busca de configurações": "emulators",
        "Drivers": "drivers",
    }

    @classmethod
    def supports_section(cls, section: str) -> bool:
        return section in cls.GROUP_SECTIONS.values()

    def __init__(self, parent: QWidget | None = None, *, section: str = "emulators") -> None:
        super().__init__(parent)
        self.section = section
        self.options = tuple(
            option
            for group_name, group_options in self.GROUPS.items()
            if self.GROUP_SECTIONS.get(group_name) == section
            for option in group_options
        )
        self.controls: dict[str, QCheckBox | QSpinBox | QLineEdit] = {}
        root = QVBoxLayout(self)
        title = QLabel(f"Configurações do WinUAE · {section}")
        title.setProperty("role", "title")
        root.addWidget(title)
        self.group_tabs = QTabWidget()
        for group_name, options in self.GROUPS.items():
            if self.GROUP_SECTIONS.get(group_name) != self.section:
                continue
            page = QWidget()
            form = QFormLayout(page)
            form.setContentsMargins(14, 14, 14, 14)
            for option in options:
                control = self._make_control(option)
                self.controls[option.key] = control
                form.addRow(option.label, control)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.group_tabs.addTab(scroll, group_name)
        root.addWidget(self.group_tabs, 1)
        info = QLabel(
            "As opções gerais são lidas e gravadas somente na seção [WinUAE]. "
            "Diretórios são configurados em 01-Diretórios. Opções que não aparecem "
            "neste winuae.ini, como preferências específicas por jogo, não são criadas aqui."
        )
        info.setWordWrap(True)
        root.addWidget(info)
        self.status = QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        buttons = QHBoxLayout()
        save = QPushButton("Salvar configurações")
        save.clicked.connect(self.save)
        reload_button = QPushButton("Recarregar")
        reload_button.clicked.connect(self.refresh)
        buttons.addWidget(reload_button)
        buttons.addWidget(save)
        root.addLayout(buttons)
        self.refresh()

    @staticmethod
    def _make_control(option: WinUAEOption) -> QCheckBox | QSpinBox | QLineEdit:
        if option.kind == "bool":
            control = QCheckBox("Ativado")
        elif option.kind == "integer":
            control = QSpinBox()
            control.setRange(option.minimum, option.maximum)
        else:
            control = QLineEdit()
        control.setEnabled(False)
        return control

    def _editor(self) -> WinUAEConfigEditor | None:
        try:
            paths = json.loads(self.PATHS_FILE.read_text(encoding="utf-8"))
            paths = paths if isinstance(paths, dict) else {}
        except (OSError, ValueError, TypeError):
            paths = {}
        raw = paths.get("winuae_ini")
        root = Path(str(paths.get("winuae", ""))) if paths.get("winuae") else None
        candidates = ([Path(str(raw))] if raw else []) + ([root / "winuae.ini"] if root else [])
        path = next((candidate for candidate in candidates if candidate.is_file()), None)
        try:
            return WinUAEConfigEditor(path) if path else None
        except (OSError, UnicodeError):
            return None

    def refresh(self) -> None:
        editor = self._editor()
        self.status.setText(
            f"Arquivo: {editor.path}" if editor else "Arquivo: não configurado / não encontrado"
        )
        for option in self.options:
            control = self.controls[option.key]
            values = editor.values(option.key) if editor else []
            control.setEnabled(bool(values))
            if not values:
                continue
            raw = values[0]
            if option.kind == "bool" and isinstance(control, QCheckBox):
                control.setChecked(raw.strip().casefold() in {"1", "yes", "true", "on"})
            elif option.kind == "integer" and isinstance(control, QSpinBox):
                try:
                    control.setValue(int(raw))
                except ValueError:
                    control.setValue(0)
            elif isinstance(control, QLineEdit):
                control.setText(raw)

    @staticmethod
    def _bool_text(value: bool, original: str) -> str:
        normalized = original.strip().casefold()
        if normalized in {"true", "false"}:
            return "true" if value else "false"
        if normalized in {"yes", "no"}:
            return "yes" if value else "no"
        return "1" if value else "0"

    def save(self) -> None:
        editor = self._editor()
        if editor is None:
            QMessageBox.warning(self, "WinUAE", "Configure winuae.ini em 01-Diretórios.")
            return
        changed = 0
        try:
            for option in self.options:
                existing = editor.values(option.key)
                control = self.controls[option.key]
                if not existing or not control.isEnabled():
                    continue
                old = existing[0]
                if option.kind == "bool" and isinstance(control, QCheckBox):
                    value = self._bool_text(control.isChecked(), old)
                elif option.kind == "integer" and isinstance(control, QSpinBox):
                    value = str(control.value())
                elif isinstance(control, QLineEdit):
                    value = control.text().strip()
                else:
                    continue
                if value != old:
                    editor.set_value(option.key, value)
                    changed += 1
            if not changed:
                QMessageBox.information(self, "WinUAE", "Nenhuma alteração pendente.")
                return
            backup = editor.save()
        except (OSError, KeyError, ValueError) as exc:
            QMessageBox.critical(self, "WinUAE", f"Falha ao salvar.\n\n{exc}")
            return
        self.refresh()
        QMessageBox.information(
            self, "WinUAE", f"{changed} opção(ões) alteradas.\nBackup:\n{backup}"
        )
