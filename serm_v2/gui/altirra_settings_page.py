"""Altirra settings UI backed by its section-aware native configuration file."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root
from .altirra_config import AltirraConfigEditor


@dataclass(frozen=True, slots=True)
class AltirraOption:
    section: str
    key: str
    label: str
    category: str
    kind: str = "bool"
    minimum: int = 0
    maximum: int = 100


class AltirraSettingsPage(QWidget):
    """Expose a conservative set of existing settings from the active profile."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    ROOT = "User\\Software\\virtualdub.org\\Altirra"
    PROFILE_ROOT = f"{ROOT}\\Profiles"
    GLOBAL_SECTION = f"{PROFILE_ROOT}\\00000000"
    OPTIONS = (
        AltirraOption(GLOBAL_SECTION, "BASIC enabled", "BASIC ativado", "Inicialização"),
        AltirraOption(
            GLOBAL_SECTION, "Console: Keyboard present", "Teclado presente", "Inicialização"
        ),
        AltirraOption(
            GLOBAL_SECTION,
            "Cassette: Auto-boot enabled",
            "Inicialização automática de fita",
            "Inicialização",
        ),
        AltirraOption(
            GLOBAL_SECTION,
            "Cassette: Auto BASIC boot enabled",
            "Inicializar fita no BASIC",
            "Inicialização",
        ),
        AltirraOption(
            GLOBAL_SECTION,
            "Cassette: Auto-rewind enabled",
            "Rebobinar fita automaticamente",
            "Fita e disco",
        ),
        AltirraOption(
            GLOBAL_SECTION, "Cassette: SIO patch enabled", "SIO patch da fita", "Fita e disco"
        ),
        AltirraOption(
            GLOBAL_SECTION, "Disk: SIO patch enabled", "SIO patch do disco", "Fita e disco"
        ),
        AltirraOption(
            GLOBAL_SECTION,
            "Disk: Burst transfers enabled",
            "Transferência rápida de disco",
            "Fita e disco",
        ),
        AltirraOption(
            GLOBAL_SECTION, "Display: Full screen", "Iniciar em tela cheia", "Vídeo e interface"
        ),
        AltirraOption(GLOBAL_SECTION, "View: Show FPS", "Mostrar FPS", "Vídeo e interface"),
        AltirraOption(
            GLOBAL_SECTION, "View: Vertical sync", "Sincronização vertical", "Vídeo e interface"
        ),
        AltirraOption(
            GLOBAL_SECTION, "Display: Show indicators", "Mostrar indicadores", "Vídeo e interface"
        ),
        AltirraOption(GLOBAL_SECTION, "GTIA: Scanlines", "Scanlines", "Vídeo e interface"),
        AltirraOption("@active", "PAL mode", "Modo PAL", "Sistema ativo"),
        AltirraOption("@active", "SECAM mode", "Modo SECAM", "Sistema ativo"),
        AltirraOption("@active", "Mixed video mode", "Modo de vídeo misto", "Sistema ativo"),
        AltirraOption(GLOBAL_SECTION, "Pause when inactive", "Pausar quando inativo", "Desempenho"),
        AltirraOption(
            GLOBAL_SECTION,
            "Speed: Enable rewind recording",
            "Gravar dados para retroceder",
            "Desempenho",
        ),
        AltirraOption(GLOBAL_SECTION, "Audio: Mute", "Silenciar áudio", "Áudio"),
        AltirraOption(
            GLOBAL_SECTION, "Audio: Latency", "Latência de áudio (ms)", "Áudio", "int", 10, 500
        ),
        AltirraOption(
            GLOBAL_SECTION,
            "Speed: Frame rate modifier",
            "Velocidade em porcentagem",
            "Desempenho",
            "int",
            10,
            300,
        ),
        AltirraOption(
            GLOBAL_SECTION,
            "Scanline intensity",
            "Intensidade das scanlines",
            "Vídeo e interface",
            "int",
            0,
            100,
        ),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controls: dict[str, QWidget] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        info = QLabel(
            "Opções do perfil ativo que já existem no Altirra.ini. O arquivo mantém suas demais configurações; salvar cria uma cópia .bak."
        )
        info.setWordWrap(True)
        root.addWidget(info)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        categories: dict[str, QFormLayout] = {}
        for category in dict.fromkeys(option.category for option in self.OPTIONS):
            group = QGroupBox(category)
            form = QFormLayout(group)
            body_layout.addWidget(group)
            categories[category] = form
        for option in self.OPTIONS:
            if option.kind == "bool":
                control: QWidget = QCheckBox("Ativado")
            else:
                spin = QSpinBox()
                spin.setRange(option.minimum, option.maximum)
                control = spin
            control.setEnabled(False)
            self.controls[option.key] = control
            categories[option.category].addRow(option.label, control)
        body_layout.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        buttons = QHBoxLayout()
        self.status = QLabel("Arquivo: não configurado")
        self.status.setWordWrap(True)
        reload_button = QPushButton("Recarregar")
        reload_button.clicked.connect(self.refresh)
        save_button = QPushButton("Salvar Altirra")
        save_button.clicked.connect(self.save)
        buttons.addWidget(self.status, 1)
        buttons.addWidget(reload_button)
        buttons.addWidget(save_button)
        root.addLayout(buttons)

    @classmethod
    def _config_path(cls) -> Path | None:
        try:
            paths = json.loads(cls.PATHS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        raw = paths.get("altirra_config") if isinstance(paths, dict) else None
        path = Path(str(raw)).expanduser() if raw else None
        return path if path and path.is_file() else None

    def _editor(self) -> AltirraConfigEditor | None:
        path = self._config_path()
        if path is None:
            return None
        try:
            return AltirraConfigEditor(path)
        except (OSError, UnicodeError):
            return None

    def refresh(self) -> None:
        editor = self._editor()
        if editor is None:
            self.status.setText("Arquivo Altirra.ini não configurado ou indisponível")
            for control in self.controls.values():
                control.setEnabled(False)
            return
        profile_section = editor.active_profile_section()
        profile_name = profile_section.rsplit("\\", 1)[-1]
        self.status.setText(f"Arquivo: {editor.path}\nPerfil: {profile_name}")
        for option in self.OPTIONS:
            section = profile_section if option.section == "@active" else option.section
            values = editor.values(section, option.key)
            control = self.controls[option.key]
            control.setEnabled(bool(values))
            if not values:
                continue
            if option.kind == "bool":
                control.setChecked(values[0].casefold() in {"1", "true", "yes", "on"})  # type: ignore[attr-defined]
            else:
                try:
                    value = int(values[0], 0)
                except ValueError:
                    value = option.minimum
                control.setValue(max(option.minimum, min(option.maximum, value)))  # type: ignore[attr-defined]

    def save(self) -> None:
        editor = self._editor()
        if editor is None:
            QMessageBox.warning(
                self, "Altirra", "Selecione um Altirra.ini válido em 01-Diretórios."
            )
            return
        profile_section = editor.active_profile_section()
        changed = 0
        try:
            for option in self.OPTIONS:
                section = profile_section if option.section == "@active" else option.section
                current = editor.values(section, option.key)
                control = self.controls[option.key]
                if not current or not control.isEnabled():
                    continue
                if option.kind == "bool":
                    value = "1" if control.isChecked() else "0"  # type: ignore[attr-defined]
                else:
                    value = str(control.value())  # type: ignore[attr-defined]
                if value != current[0]:
                    editor.set_value(section, option.key, value)
                    changed += 1
            if changed:
                backup = editor.save()
            else:
                QMessageBox.information(self, "Altirra", "Nenhuma alteração pendente.")
                return
        except (OSError, KeyError, ValueError) as exc:
            QMessageBox.critical(
                self, "Altirra", f"Não foi possível salvar a configuração.\n\n{exc}"
            )
            return
        self.refresh()
        QMessageBox.information(
            self, "Altirra salvo", f"{changed} opção(ões) alterada(s).\nBackup:\n{backup}"
        )


__all__ = ["AltirraOption", "AltirraSettingsPage"]
