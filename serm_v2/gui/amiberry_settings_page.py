"""Grouped Amiberry settings backed by keys present in amiberry.conf."""

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
from .directories_guide_page import ConfigFileEditor


@dataclass(frozen=True, slots=True)
class AmiberryOption:
    key: str
    label: str
    kind: str = "bool"
    minimum: int = -2_147_483_648
    maximum: int = 2_147_483_647


class AmiberrySettingsPage(QWidget):
    PATHS_FILE = data_root() / "emulator_paths.json"
    GROUPS = {
        "Geral": (
            AmiberryOption("Quickstart", "Iniciar pelo Quickstart"),
            AmiberryOption(
                "read_config_descriptions", "Ler descrições dos arquivos de configuração"
            ),
            AmiberryOption("write_logfile", "Gravar arquivo de log"),
            AmiberryOption("default_open_gui_key", "Tecla para abrir a interface", "text"),
            AmiberryOption("default_quit_key", "Tecla para sair", "text"),
            AmiberryOption("default_ar_key", "Tecla para alternar proporção", "text"),
            AmiberryOption("default_retroarch_quit", "Permitir saída pelo RetroArch"),
            AmiberryOption("default_retroarch_menu", "Permitir abrir o menu do RetroArch"),
            AmiberryOption("default_retroarch_reset", "Permitir reiniciar pelo RetroArch"),
            AmiberryOption("default_retroarch_vkbd", "Permitir teclado virtual do RetroArch"),
            AmiberryOption("update_check", "Verificar atualizações", "integer", 0, 10),
            AmiberryOption("update_channel", "Canal de atualização", "integer", 0, 100),
        ),
        "Vídeo": (
            AmiberryOption("default_horizontal_centering", "Centralização horizontal"),
            AmiberryOption("default_vertical_centering", "Centralização vertical"),
            AmiberryOption("default_scaling_method", "Método de escala", "integer"),
            AmiberryOption("default_gfx_autoresolution", "Resolução automática", "integer"),
            AmiberryOption("default_frameskip", "Pular quadros"),
            AmiberryOption("default_correct_aspect_ratio", "Corrigir proporção"),
            AmiberryOption("default_auto_crop", "Recorte automático"),
            AmiberryOption("default_width", "Largura padrão", "integer", 1, 32768),
            AmiberryOption("default_height", "Altura padrão", "integer", 1, 32768),
            AmiberryOption("default_fullscreen_mode", "Modo de tela cheia", "integer"),
            AmiberryOption("shader", "Shader do modo Amiga", "text"),
            AmiberryOption("shader_rtg", "Shader do modo RTG", "text"),
            AmiberryOption("use_bezel", "Usar bezel"),
            AmiberryOption("use_custom_bezel", "Usar bezel personalizado"),
            AmiberryOption("custom_bezel", "Arquivo / identificador do bezel", "text"),
        ),
        "Áudio": (
            AmiberryOption(
                "default_sound_frequency", "Frequência de áudio (Hz)", "integer", 1, 384000
            ),
            AmiberryOption("default_sound_buffer", "Buffer de áudio", "integer", 0, 1000000),
            AmiberryOption("default_soundcard", "Dispositivo de áudio", "integer", 0, 1000),
            AmiberryOption("default_stereo_separation", "Separação estéreo", "integer", 0, 100),
        ),
        "Controles": (
            AmiberryOption("gui_joystick_control", "Controlar a interface com joystick"),
            AmiberryOption(
                "input_default_mouse_speed", "Velocidade padrão do mouse", "integer", 0, 10000
            ),
            AmiberryOption(
                "input_keyboard_as_joystick_stop_keypresses", "Parar joystick ao pressionar teclado"
            ),
            AmiberryOption(
                "default_joystick_deadzone", "Zona morta do joystick", "integer", 0, 100
            ),
            AmiberryOption("default_controller1", "Controle 1", "text"),
            AmiberryOption("default_controller2", "Controle 2", "text"),
            AmiberryOption("default_controller3", "Controle 3", "text"),
            AmiberryOption("default_controller4", "Controle 4", "text"),
            AmiberryOption("default_mouse1", "Dispositivo do mouse 1", "text"),
            AmiberryOption("default_mouse2", "Dispositivo do mouse 2", "text"),
            AmiberryOption("default_onscreen_joystick", "Joystick na tela"),
            AmiberryOption("default_vkbd_enabled", "Ativar teclado virtual"),
            AmiberryOption("default_vkbd_language", "Idioma do teclado virtual", "text"),
            AmiberryOption(
                "default_vkbd_transparency", "Transparência do teclado virtual", "integer", 0, 100
            ),
            AmiberryOption("default_vkbd_toggle", "Tecla do teclado virtual", "text"),
        ),
        "WHDLoad": (
            AmiberryOption("default_whd_buttonwait", "Aguardar botão ao concluir WHDLoad"),
            AmiberryOption("default_whd_showsplash", "Mostrar tela inicial WHDLoad"),
            AmiberryOption(
                "default_whd_configdelay", "Atraso de configuração WHDLoad", "integer", 0, 600
            ),
            AmiberryOption("default_whd_writecache", "Permitir cache de escrita"),
            AmiberryOption("default_whd_quit_on_exit", "Encerrar após sair do jogo"),
            AmiberryOption("use_jst_instead_of_whd", "Usar JST em vez de WHDLoad"),
        ),
        "Desempenho e avançado": (
            AmiberryOption("perf_log", "Registrar métricas de desempenho"),
            AmiberryOption("slow_host_warning", "Avisar sobre desempenho do computador"),
            AmiberryOption("use_adpf", "Ativar ajuste dinâmico de desempenho"),
            AmiberryOption("default_disable_cycle_exact", "Desativar ciclo exato por padrão"),
            AmiberryOption("default_line_mode", "Modo de linhas", "integer"),
            AmiberryOption(
                "default_quickstart_compatibility", "Compatibilidade do Quickstart", "integer"
            ),
            AmiberryOption("rctrl_as_ramiga", "Usar Ctrl direito como Amiga direito"),
            AmiberryOption("disable_shutdown_button", "Desativar botão de desligar"),
            AmiberryOption("allow_display_settings_from_json", "Permitir ajustes de tela via JSON"),
        ),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controls: dict[str, QCheckBox | QSpinBox | QLineEdit] = {}
        root = QVBoxLayout(self)
        title = QLabel("Configurações do Amiberry")
        title.setProperty("role", "title")
        root.addWidget(title)
        self.group_tabs = QTabWidget()
        for group_name, options in self.GROUPS.items():
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
            "As opções são agrupadas por área e só ficam ativas se a chave existir no amiberry.conf. "
            "Os caminhos são configurados em 01-Diretórios. Aplicar cria backup .bak."
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
    def _make_control(option: AmiberryOption) -> QCheckBox | QSpinBox | QLineEdit:
        if option.kind == "bool":
            control = QCheckBox("Ativado")
        elif option.kind == "integer":
            control = QSpinBox()
            control.setRange(option.minimum, option.maximum)
        else:
            control = QLineEdit()
        control.setEnabled(False)
        return control

    @staticmethod
    def _bool_text(value: bool, original: str) -> str:
        normalized = original.strip().casefold()
        if normalized in {"yes", "no"}:
            return "yes" if value else "no"
        if normalized in {"true", "false"}:
            return "true" if value else "false"
        return "1" if value else "0"

    def _editor(self) -> ConfigFileEditor | None:
        try:
            paths = json.loads(self.PATHS_FILE.read_text(encoding="utf-8"))
            paths = paths if isinstance(paths, dict) else {}
        except (OSError, ValueError, TypeError):
            paths = {}
        raw = paths.get("amiberry_conf")
        root = Path(str(paths.get("amiberry", ""))) if paths.get("amiberry") else None
        candidates = ([Path(str(raw))] if raw else []) + (
            [root / "Settings" / "amiberry.conf", root / "amiberry.conf"] if root else []
        )
        path = next((candidate for candidate in candidates if candidate.is_file()), None)
        try:
            return ConfigFileEditor(path) if path else None
        except (OSError, UnicodeError):
            return None

    def refresh(self) -> None:
        editor = self._editor()
        self.status.setText(
            f"Arquivo: {editor.path}" if editor else "Arquivo: não configurado / não encontrado"
        )
        for group in self.GROUPS.values():
            for option in group:
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

    def save(self) -> None:
        editor = self._editor()
        if editor is None:
            QMessageBox.warning(self, "Amiberry", "Configure amiberry.conf em 01-Diretórios.")
            return
        changed = 0
        try:
            for group in self.GROUPS.values():
                for option in group:
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
                QMessageBox.information(self, "Amiberry", "Nenhuma alteração pendente.")
                return
            backup = editor.save()
        except (OSError, KeyError, ValueError) as exc:
            QMessageBox.critical(self, "Amiberry", f"Falha ao salvar.\n\n{exc}")
            return
        self.refresh()
        QMessageBox.information(
            self, "Amiberry", f"{changed} opção(ões) alteradas.\nBackup:\n{backup}"
        )
