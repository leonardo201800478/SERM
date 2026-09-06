"""Editor seguro de configurações dos emuladores do SERM V2.

A tela é deliberadamente baseada nos arquivos reais: uma opção só fica editável
quando a chave existe no arquivo selecionado. Isso evita que o SERM invente
chaves ou altere a semântica de uma configuração desconhecida.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root
from .directories_guide_page import ConfigFileEditor


@dataclass(frozen=True, slots=True)
class SettingSpec:
    """Metadados de uma opção suportada pela interface."""

    key: str
    label: str
    kind: str
    category: str
    values: tuple[tuple[str, str], ...] = ()
    minimum: int = 0
    maximum: int = 100
    description: str = ""


class EmulatorSettingsPage(QWidget):
    """Configura MAME, FBNeo, Flycast, Supermodel e RetroArch em três níveis."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    CONFIG_KEYS = {
        "mame": "mame_config",
        "fbneo": "fbneo_config",
        "flycast": "flycast_config",
        "supermodel": "supermodel_config",
        "retroarch": "retroarch_cfg",
    }

    SPECS: dict[str, tuple[SettingSpec, ...]] = {
        "mame": (
            SettingSpec(
                "video",
                "Driver de vídeo",
                "combo",
                "Vídeo",
                (
                    ("bgfx", "BGFX"),
                    ("d3d", "Direct3D 9"),
                    ("opengl", "OpenGL"),
                    ("gdi", "GDI"),
                    ("soft", "Software"),
                    ("none", "Sem vídeo"),
                ),
                description="Backends documentados pelo MAME 0.289.",
            ),
            SettingSpec(
                "bgfx_backend",
                "Backend BGFX",
                "combo",
                "Vídeo",
                (
                    ("auto", "Automático"),
                    ("d3d9", "Direct3D 9"),
                    ("d3d11", "Direct3D 11"),
                    ("d3d12", "Direct3D 12"),
                    ("opengl", "OpenGL"),
                    ("vulkan", "Vulkan"),
                ),
            ),
            SettingSpec("filter", "Filtragem bilinear", "bool", "Vídeo"),
            SettingSpec("prescale", "Prescale", "slider", "Vídeo", minimum=1, maximum=5),
            SettingSpec("waitvsync", "VSync", "bool", "Vídeo"),
            SettingSpec(
                "samplerate",
                "Taxa de amostragem",
                "combo",
                "Áudio",
                (
                    ("22050", "22.05 kHz"),
                    ("32000", "32 kHz"),
                    ("44100", "44.1 kHz"),
                    ("48000", "48 kHz"),
                    ("96000", "96 kHz"),
                ),
            ),
            SettingSpec("samples", "Samples", "bool", "Áudio"),
            SettingSpec("volume", "Volume inicial (dB)", "slider", "Áudio", minimum=-32, maximum=0),
            SettingSpec("sound", "Backend de som", "text", "Áudio"),
            SettingSpec("joystick", "Joystick", "bool", "Controles"),
            SettingSpec("mouse", "Mouse", "bool", "Controles"),
            SettingSpec("lightgun", "Lightgun", "bool", "Controles"),
            SettingSpec("multikeyboard", "Múltiplos teclados", "bool", "Controles"),
            SettingSpec("multimouse", "Múltiplos mouses", "bool", "Controles"),
            SettingSpec(
                "joystickprovider",
                "Driver de joystick",
                "combo",
                "Controles",
                (("auto", "Automático"), ("dinput", "DirectInput"), ("sdl", "SDL")),
            ),
            SettingSpec("language", "Diretório de idiomas", "text", "Sistema"),
            SettingSpec(
                "priority", "Prioridade do processo", "slider", "Desempenho", minimum=0, maximum=7
            ),
            SettingSpec("triplebuffer", "Triple buffering", "bool", "Desempenho"),
            SettingSpec("syncrefresh", "Sincronizar refresh", "bool", "Desempenho"),
            SettingSpec("unevenstretch", "Escala não inteira", "bool", "Vídeo"),
            SettingSpec("switchres", "Trocar resolução em fullscreen", "bool", "Vídeo"),
            SettingSpec("artwork_crop", "Cortar artwork", "bool", "Vídeo"),
            SettingSpec("gl_glsl", "GLSL", "bool", "Avançado"),
            SettingSpec(
                "gl_glsl_filter",
                "Filtro GLSL",
                "combo",
                "Avançado",
                (("0", "Plain"), ("1", "Bilinear"), ("2", "Bicubic")),
            ),
        ),
        "fbneo": (
            SettingSpec("nVidSelect", "Blitter de vídeo", "slider", "Vídeo", minimum=0, maximum=6),
            SettingSpec("bVidBilinear", "Filtragem bilinear", "bool", "Vídeo"),
            SettingSpec("bVidScanlines", "Scanlines", "bool", "Vídeo"),
            SettingSpec("bVidScanDelay", "Fósforo lento", "bool", "Vídeo"),
            SettingSpec("nVidDX9HardFX", "HardFX", "slider", "Vídeo", minimum=0, maximum=20),
            SettingSpec("bVidHardwareVertex", "Hardware vertex", "bool", "Vídeo"),
            SettingSpec("bVidMotionBlur", "Motion blur", "bool", "Vídeo"),
            SettingSpec("bForce60Hz", "Forçar 60 Hz", "bool", "Vídeo"),
            SettingSpec("bAlwaysDrawFrames", "Sempre desenhar frames", "bool", "Desempenho"),
            SettingSpec("bRunAhead", "Run-ahead", "bool", "Desempenho"),
            SettingSpec("nAudSelect", "Plugin de áudio", "slider", "Áudio", minimum=0, maximum=8),
            SettingSpec("nAudVolume", "Volume", "slider", "Áudio", minimum=0, maximum=10000),
            SettingSpec(
                "nAudSegCount", "Buffer de áudio", "slider", "Áudio", minimum=2, maximum=20
            ),
            SettingSpec(
                "nAudSampleRate[0]",
                "Sample rate DirectSound",
                "combo",
                "Áudio",
                (
                    ("22050", "22.05 kHz"),
                    ("44100", "44.1 kHz"),
                    ("48000", "48 kHz"),
                    ("96000", "96 kHz"),
                ),
            ),
            SettingSpec(
                "nAudSampleRate[1]",
                "Sample rate XAudio2",
                "combo",
                "Áudio",
                (
                    ("22050", "22.05 kHz"),
                    ("44100", "44.1 kHz"),
                    ("48000", "48 kHz"),
                    ("96000", "96 kHz"),
                ),
            ),
            SettingSpec(
                "nInterpolation", "Interpolação PCM", "slider", "Áudio", minimum=0, maximum=3
            ),
            SettingSpec(
                "nFMInterpolation", "Interpolação FM", "slider", "Áudio", minimum=0, maximum=3
            ),
            SettingSpec("bAutoPause", "Pausar ao perder foco", "bool", "Controles"),
            SettingSpec(
                "bAlwaysProcessKeyboardInput", "Processar teclado sem foco", "bool", "Controles"
            ),
            SettingSpec("bSaveInputs", "Salvar controles por jogo", "bool", "Controles"),
            SettingSpec("nSocd[0]", "SOCD Player 1", "slider", "Controles", minimum=0, maximum=5),
            SettingSpec("nSocd[1]", "SOCD Player 2", "slider", "Controles", minimum=0, maximum=5),
            SettingSpec(
                "nIpsSelectedLanguage", "Idioma do IPS", "slider", "Sistema", minimum=0, maximum=20
            ),
            SettingSpec("bEnableHighResTimer", "High resolution timer", "bool", "Desempenho"),
            SettingSpec("bRewindEnabled", "Rewind", "bool", "Desempenho"),
            SettingSpec(
                "nRewindMemory",
                "Memória do rewind (MB)",
                "slider",
                "Desempenho",
                minimum=64,
                maximum=4096,
            ),
        ),
        "flycast": (
            SettingSpec(
                "Dreamcast.Cable",
                "Saída de vídeo",
                "combo",
                "Vídeo",
                (("0", "VGA"), ("1", "RGB"), ("2", "VGA Box"), ("3", "TV Composite")),
            ),
            SettingSpec(
                "Dreamcast.Region",
                "Região",
                "combo",
                "Sistema",
                (("0", "Japão"), ("1", "USA"), ("2", "Europa"), ("3", "Automática")),
            ),
            SettingSpec(
                "Dreamcast.Broadcast", "Broadcast", "slider", "Vídeo", minimum=0, maximum=4
            ),
            SettingSpec(
                "Dreamcast.Language",
                "Idioma",
                "combo",
                "Sistema",
                (
                    ("0", "Japonês"),
                    ("1", "Inglês"),
                    ("2", "Alemão"),
                    ("3", "Francês"),
                    ("4", "Espanhol"),
                    ("5", "Italiano"),
                    ("6", "Automático"),
                ),
            ),
            SettingSpec("Dynarec.Enabled", "Dynamic recompiler", "bool", "Desempenho"),
            SettingSpec("Dynarec.idleskip", "Idle skip", "bool", "Desempenho"),
            SettingSpec("Dynarec.unstable-opt", "Otimizações instáveis", "bool", "Desempenho"),
            SettingSpec("Dynarec.safe-mode", "Safe mode", "bool", "Desempenho"),
            SettingSpec("aica.DSPEnabled", "DSP", "bool", "Áudio"),
            SettingSpec("aica.LimitFPS", "Limitar FPS", "bool", "Áudio"),
            SettingSpec("aica.NoSound", "Sem som", "bool", "Áudio"),
            SettingSpec(
                "aica.BufferSize", "Buffer de áudio", "slider", "Áudio", minimum=512, maximum=8192
            ),
            SettingSpec(
                "backend",
                "Backend de áudio",
                "combo",
                "Áudio",
                (("auto", "Automático"), ("wasapi", "WASAPI"), ("sdl2", "SDL2"), ("null", "Nulo")),
            ),
            SettingSpec("rend.UseMipmaps", "Mipmaps", "bool", "Vídeo"),
            SettingSpec("rend.WideScreen", "Widescreen", "bool", "Vídeo"),
            SettingSpec("rend.ShowFPS", "Mostrar FPS", "bool", "Vídeo"),
            SettingSpec(
                "rend.TextureUpscale",
                "Upscale de texturas",
                "slider",
                "Vídeo",
                minimum=1,
                maximum=8,
            ),
            SettingSpec(
                "rend.MaxFilteredTextureSize",
                "Tamanho máximo filtrado",
                "slider",
                "Vídeo",
                minimum=64,
                maximum=4096,
            ),
            SettingSpec(
                "rend.ScreenScaling", "Escala da tela", "slider", "Vídeo", minimum=1, maximum=800
            ),
            SettingSpec(
                "rend.ScreenStretching", "Alongamento", "slider", "Vídeo", minimum=1, maximum=200
            ),
            SettingSpec("rend.Fog", "Fog", "bool", "Vídeo"),
            SettingSpec("rend.Rotate90", "Rotacionar 90°", "bool", "Vídeo"),
            SettingSpec("rend.WidescreenGameHacks", "Widescreen game hacks", "bool", "Avançado"),
            SettingSpec("pvr.rend", "Renderer PVR", "slider", "Avançado", minimum=0, maximum=8),
            SettingSpec(
                "pvr.MaxThreads", "Threads do PVR", "slider", "Desempenho", minimum=1, maximum=16
            ),
            SettingSpec(
                "input.MouseSensitivity",
                "Sensibilidade do mouse",
                "slider",
                "Controles",
                minimum=1,
                maximum=200,
            ),
            SettingSpec("input.JammaSetup", "JAMMA", "slider", "Controles", minimum=0, maximum=20),
        ),
        "supermodel": (
            SettingSpec("New3DEngine", "Novo motor 3D", "bool", "Vídeo"),
            SettingSpec("WideScreen", "Widescreen", "bool", "Vídeo"),
            SettingSpec("FullScreen", "Fullscreen", "bool", "Vídeo"),
            SettingSpec("VSync", "VSync", "bool", "Vídeo"),
            SettingSpec("ShowStats", "Mostrar estatísticas", "bool", "Vídeo"),
            SettingSpec("Stretch", "Stretch", "bool", "Vídeo"),
            SettingSpec("XResolution", "Resolução X", "slider", "Vídeo", minimum=320, maximum=7680),
            SettingSpec("YResolution", "Resolução Y", "slider", "Vídeo", minimum=240, maximum=4320),
            SettingSpec("SoundVolume", "Volume de som", "slider", "Áudio", minimum=0, maximum=200),
            SettingSpec(
                "MusicVolume", "Volume de música", "slider", "Áudio", minimum=0, maximum=200
            ),
            SettingSpec("Balance", "Balanço", "slider", "Áudio", minimum=-100, maximum=100),
            SettingSpec(
                "InputSystem",
                "Sistema de input",
                "combo",
                "Controles",
                (
                    ("dinput", "DirectInput"),
                    ("xinput", "XInput"),
                    ("rawinput", "Raw Input"),
                    ("sdl", "SDL"),
                ),
            ),
            SettingSpec("InputStart1", "Start Player 1", "text", "Controles"),
            SettingSpec("InputCoin1", "Coin Player 1", "text", "Controles"),
            SettingSpec("InputJoyUp", "Joystick cima", "text", "Controles"),
            SettingSpec("InputJoyDown", "Joystick baixo", "text", "Controles"),
            SettingSpec("InputJoyLeft", "Joystick esquerda", "text", "Controles"),
            SettingSpec("InputJoyRight", "Joystick direita", "text", "Controles"),
            SettingSpec("Network", "Network board", "bool", "Avançado"),
            SettingSpec("SimulateNet", "Simular rede", "bool", "Avançado"),
        ),
        "retroarch": (
            SettingSpec(
                "video_driver",
                "Driver de vídeo",
                "combo",
                "Vídeo",
                (
                    ("gl", "OpenGL"),
                    ("d3d11", "Direct3D 11"),
                    ("d3d12", "Direct3D 12"),
                    ("vulkan", "Vulkan"),
                    ("sdl2", "SDL2"),
                ),
            ),
            SettingSpec("video_fullscreen", "Fullscreen", "bool", "Vídeo"),
            SettingSpec("video_windowed_fullscreen", "Fullscreen em janela", "bool", "Vídeo"),
            SettingSpec("video_vsync", "VSync", "bool", "Vídeo"),
            SettingSpec("video_smooth", "Filtragem suave", "bool", "Vídeo"),
            SettingSpec("video_scale_integer", "Escala inteira", "bool", "Vídeo"),
            SettingSpec("video_allow_rotate", "Permitir rotação do core", "bool", "Vídeo"),
            SettingSpec(
                "video_fullscreen_x", "Resolução X", "slider", "Vídeo", minimum=0, maximum=7680
            ),
            SettingSpec(
                "video_fullscreen_y", "Resolução Y", "slider", "Vídeo", minimum=0, maximum=4320
            ),
            SettingSpec("video_monitor_index", "Monitor", "slider", "Vídeo", minimum=0, maximum=8),
            SettingSpec("audio_enable", "Áudio", "bool", "Áudio"),
            SettingSpec(
                "audio_driver",
                "Driver de áudio",
                "combo",
                "Áudio",
                (("wasapi", "WASAPI"), ("xaudio", "XAudio"), ("sdl", "SDL"), ("null", "Nulo")),
            ),
            SettingSpec(
                "audio_out_rate",
                "Sample rate",
                "combo",
                "Áudio",
                (
                    ("32000", "32 kHz"),
                    ("44100", "44.1 kHz"),
                    ("48000", "48 kHz"),
                    ("96000", "96 kHz"),
                ),
            ),
            SettingSpec("audio_sync", "Sincronizar áudio", "bool", "Áudio"),
            SettingSpec(
                "audio_latency", "Latência (ms)", "slider", "Áudio", minimum=1, maximum=256
            ),
            SettingSpec("audio_rate_control", "Rate control", "bool", "Áudio"),
            SettingSpec("audio_volume", "Volume (dB)", "slider", "Áudio", minimum=-40, maximum=12),
            SettingSpec(
                "input_driver",
                "Driver de input",
                "combo",
                "Controles",
                (("dinput", "DirectInput"), ("sdl", "SDL"), ("raw", "Raw"), ("xinput", "XInput")),
            ),
            SettingSpec(
                "input_joypad_driver",
                "Driver de gamepad",
                "combo",
                "Controles",
                (("dinput", "DirectInput"), ("sdl", "SDL"), ("xinput", "XInput")),
            ),
            SettingSpec("input_autodetect_enable", "Autodetectar controles", "bool", "Controles"),
            SettingSpec(
                "input_axis_threshold",
                "Threshold dos eixos",
                "slider",
                "Controles",
                minimum=0,
                maximum=100,
            ),
            SettingSpec(
                "menu_driver",
                "Interface do RetroArch",
                "combo",
                "Interface",
                (("rgui", "RGUI"), ("xmb", "XMB"), ("ozone", "Ozone"), ("glui", "GLUI")),
            ),
            SettingSpec("language", "Idioma", "text", "Sistema"),
            SettingSpec("rewind_enable", "Rewind", "bool", "Desempenho"),
            SettingSpec("fps_show", "Mostrar FPS", "bool", "Interface"),
            SettingSpec("threaded_video", "Vídeo em thread", "bool", "Desempenho"),
        ),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controls: dict[tuple[str, str], QWidget] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Cria nível 2 por emulador e nível 3 por categoria."""
        root = QVBoxLayout(self)
        title = QLabel("Configurações dos Emuladores")
        title.setProperty("role", "title")
        root.addWidget(title)
        info = QLabel(
            "Somente opções documentadas e presentes no arquivo real ficam editáveis. Salvar cria backup e altera apenas as chaves suportadas."
        )
        info.setWordWrap(True)
        root.addWidget(info)
        self.emulators = QTabWidget()
        for emulator in self.SPECS:
            self._build_emulator(emulator)
        root.addWidget(self.emulators, 1)

    def _build_emulator(self, emulator: str) -> None:
        """Cria a guia de segundo nível e suas categorias de terceiro nível."""
        page = QWidget()
        outer = QVBoxLayout(page)
        tabs = QTabWidget()
        categories = sorted(
            {s.category for s in self.SPECS[emulator]}, key=lambda x: (x == "Avançado", x)
        )
        for category in categories:
            cat_page = QWidget()
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(cat_page)
            form = QFormLayout(cat_page)
            form.setContentsMargins(14, 14, 14, 14)
            form.setHorizontalSpacing(18)
            for spec in (s for s in self.SPECS[emulator] if s.category == category):
                control = self._make_control(spec)
                self.controls[(emulator, spec.key)] = control
                form.addRow(self._label(spec), control)
            tabs.addTab(scroll, category)
        outer.addWidget(tabs, 1)
        buttons = QHBoxLayout()
        status = QLabel("Arquivo: não carregado")
        status.setObjectName(f"settings_status_{emulator}")
        save = QPushButton("💾 Salvar configurações")
        save.setProperty("role", "primary")
        save.clicked.connect(lambda: self.save(emulator))
        reload_button = QPushButton("↻ Recarregar")
        reload_button.clicked.connect(self.refresh)
        buttons.addWidget(status, 1)
        buttons.addWidget(reload_button)
        buttons.addWidget(save)
        outer.addLayout(buttons)
        self.emulators.addTab(page, emulator.upper() if emulator != "retroarch" else "RetroArch")

    def _label(self, spec: SettingSpec) -> QLabel:
        """Cria rótulo com tooltip documental."""
        label = QLabel(spec.label)
        label.setToolTip(spec.description or f"Chave: {spec.key}")
        return label

    def _make_control(self, spec: SettingSpec) -> QWidget:
        """Escolhe automaticamente checkbox, combo, slider ou texto."""
        if spec.kind == "bool":
            return QCheckBox("Ativado")
        if spec.kind == "combo":
            combo = QComboBox()
            for value, label in spec.values:
                combo.addItem(label, value)
            return combo
        if spec.kind == "slider":
            widget = QWidget()
            box = QHBoxLayout(widget)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(spec.minimum, spec.maximum)
            spin = QSpinBox()
            spin.setRange(spec.minimum, spec.maximum)
            slider.valueChanged.connect(spin.setValue)
            spin.valueChanged.connect(slider.setValue)
            box.addWidget(slider, 1)
            box.addWidget(spin)
            setattr(widget, "_serm_slider", slider)
            setattr(widget, "_serm_spin", spin)
            return widget
        return QLineEdit()

    @staticmethod
    def _load_paths() -> dict[str, Any]:
        """Carrega somente o mapa de caminhos mantido pelo SERM."""
        try:
            value = json.loads(EmulatorSettingsPage.PATHS_FILE.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _editor(self, emulator: str) -> ConfigFileEditor | None:
        """Abre o arquivo configurado para um emulador."""
        raw = self._load_paths().get(self.CONFIG_KEYS[emulator])
        if not raw:
            return None
        path = Path(str(raw)).expanduser()
        if not path.is_file():
            return None
        try:
            return ConfigFileEditor(path)
        except OSError:
            return None

    @staticmethod
    def _parse_bool(value: str) -> bool:
        """Converte formatos booleanos comuns."""
        return value.strip().casefold() in {"1", "true", "yes", "on"}

    @staticmethod
    def _bool_value(value: bool, original: str) -> str:
        """Mantém o formato booleano original quando possível."""
        if original.strip().casefold() in {"yes", "no"}:
            return "yes" if value else "no"
        if original.strip().casefold() in {"true", "false"}:
            return "true" if value else "false"
        return "1" if value else "0"

    def _set_control(self, control: QWidget, spec: SettingSpec, raw: str) -> None:
        """Preenche um widget com o valor efetivo do arquivo."""
        raw = raw.strip().strip('"')
        if spec.kind == "bool":
            control.setChecked(self._parse_bool(raw))  # type: ignore[attr-defined]
        elif spec.kind == "combo":
            index = control.findData(raw)  # type: ignore[attr-defined]
            control.setCurrentIndex(index if index >= 0 else -1)  # type: ignore[attr-defined]
            if index < 0:
                control.setToolTip(f"Valor atual não documentado nesta lista: {raw}")
        elif spec.kind == "slider":
            try:
                number = int(float(raw.replace(",", ".")))
            except ValueError:
                number = spec.minimum
            number = max(spec.minimum, min(spec.maximum, number))
            slider = getattr(control, "_serm_slider", None)
            spin = getattr(control, "_serm_spin", None)
            if isinstance(slider, QSlider) and isinstance(spin, QSpinBox):
                slider.setValue(number)
                spin.setValue(number)
        else:
            control.setText(raw)  # type: ignore[attr-defined]

    def _control_value(self, control: QWidget, spec: SettingSpec, original: str) -> str:
        """Obtém o valor do widget no formato aceito pelo arquivo."""
        if spec.kind == "bool":
            return self._bool_value(control.isChecked(), original)  # type: ignore[attr-defined]
        if spec.kind == "combo":
            return str(control.currentData())  # type: ignore[attr-defined]
        if spec.kind == "slider":
            spin = getattr(control, "_serm_spin", None)
            return str(spin.value()) if isinstance(spin, QSpinBox) else "0"
        return control.text().strip()  # type: ignore[attr-defined]

    def refresh(self) -> None:
        """Lê os arquivos e atualiza todos os controles sem gravar nada."""
        for emulator in self.SPECS:
            editor = self._editor(emulator)
            status = self.findChild(QLabel, f"settings_status_{emulator}")
            if editor is None:
                if status:
                    status.setText("Arquivo: não configurado / não encontrado")
                for spec in self.SPECS[emulator]:
                    self.controls[(emulator, spec.key)].setEnabled(False)
                continue
            if status:
                status.setText(f"Arquivo: {editor.path}")
            for spec in self.SPECS[emulator]:
                control = self.controls[(emulator, spec.key)]
                values = editor.values(spec.key)
                control.setEnabled(bool(values))
                if values:
                    self._set_control(control, spec, values[0])

    def save(self, emulator: str) -> None:
        """Grava somente chaves existentes, com backup atômico."""
        editor = self._editor(emulator)
        if editor is None:
            QMessageBox.warning(
                self,
                "Configuração",
                "Arquivo não encontrado. Configure-o primeiro na guia Diretórios.",
            )
            return
        changed = 0
        try:
            for spec in self.SPECS[emulator]:
                values = editor.values(spec.key)
                if not values:
                    continue
                value = self._control_value(self.controls[(emulator, spec.key)], spec, values[0])
                if value != values[0].strip().strip('"'):
                    editor.set_value(spec.key, value)
                    changed += 1
            if not changed:
                QMessageBox.information(self, "Configuração", "Nenhuma alteração pendente.")
                return
            backup = editor.save()
        except Exception as exc:
            QMessageBox.critical(
                self, "Falha ao salvar", f"Nenhuma alteração foi concluída com segurança.\n\n{exc}"
            )
            return
        self.refresh()
        QMessageBox.information(
            self, "Configuração salva", f"{changed} opção(ões) alterada(s).\nBackup:\n{backup}"
        )


__all__ = ["EmulatorSettingsPage", "SettingSpec"]
