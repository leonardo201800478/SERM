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
from .altirra_settings_page import AltirraSettingsPage
from .amiberry_settings_page import AmiberrySettingsPage
from .ares_controls_page import AresControlsPage
from .directories_guide_page import ConfigFileEditor, DirectoryGuidePage
from .winuae_settings_page import WinUAESettingsPage

VIDEO_CATEGORY = "Vídeo"
AUDIO_CATEGORY = "Áudio"
DRIVER_CATEGORY = "Drivers"
AUTO_OPTION_LABEL = "Automático"
ADVANCED_CATEGORY = "Avançado"
SAMPLE_RATE_22050_LABEL = "22.05 kHz"
SAMPLE_RATE_44100_LABEL = "44.1 kHz"
SAMPLE_RATE_48000_LABEL = "48 kHz"
SAMPLE_RATE_96000_LABEL = "96 kHz"


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
    value_scale: float = 1.0
    value_offset: float = 0.0


class SliderControl(QWidget):
    """Container that keeps its paired slider widgets explicitly typed."""

    slider: QSlider
    spin: QSpinBox


class EmulatorSettingsPage(QWidget):
    """Configura MAME, FBNeo, Flycast, Supermodel e RetroArch em três níveis."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    CONFIG_KEYS = {
        "mame": "mame_config",
        "fbneo": "fbneo_config",
        "flycast": "flycast_config",
        "supermodel": "supermodel_config",
        "retroarch": "retroarch_cfg",
        "azahar": "azahar_config",
        "ares": "ares_config",
    }

    SPECS: dict[str, tuple[SettingSpec, ...]] = {
        "mame": (
            SettingSpec(
                "video",
                "Driver de vídeo",
                "combo",
                DRIVER_CATEGORY,
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
                DRIVER_CATEGORY,
                (
                    ("auto", AUTO_OPTION_LABEL),
                    ("d3d9", "Direct3D 9"),
                    ("d3d11", "Direct3D 11"),
                    ("d3d12", "Direct3D 12"),
                    ("opengl", "OpenGL"),
                    ("vulkan", "Vulkan"),
                ),
            ),
            SettingSpec("filter", "Filtragem bilinear", "bool", VIDEO_CATEGORY),
            SettingSpec("prescale", "Prescale", "slider", VIDEO_CATEGORY, minimum=1, maximum=5),
            SettingSpec("waitvsync", "VSync", "bool", VIDEO_CATEGORY),
            SettingSpec(
                "samplerate",
                "Taxa de amostragem",
                "combo",
                AUDIO_CATEGORY,
                (
                    ("22050", SAMPLE_RATE_22050_LABEL),
                    ("32000", "32 kHz"),
                    ("44100", SAMPLE_RATE_44100_LABEL),
                    ("48000", SAMPLE_RATE_48000_LABEL),
                    ("96000", SAMPLE_RATE_96000_LABEL),
                ),
            ),
            SettingSpec("samples", "Samples", "bool", AUDIO_CATEGORY),
            SettingSpec(
                "volume", "Volume inicial (dB)", "slider", AUDIO_CATEGORY, minimum=-32, maximum=0
            ),
            SettingSpec("sound", "Backend de som", "text", DRIVER_CATEGORY),
            SettingSpec("joystick", "Joystick", "bool", "Controles"),
            SettingSpec("mouse", "Mouse", "bool", "Controles"),
            SettingSpec("lightgun", "Lightgun", "bool", "Controles"),
            SettingSpec("multikeyboard", "Múltiplos teclados", "bool", "Controles"),
            SettingSpec("multimouse", "Múltiplos mouses", "bool", "Controles"),
            SettingSpec(
                "joystickprovider",
                "Driver de joystick",
                "combo",
                DRIVER_CATEGORY,
                (("auto", AUTO_OPTION_LABEL), ("dinput", "DirectInput"), ("sdl", "SDL")),
            ),
            SettingSpec("language", "Diretório de idiomas", "text", "Sistema"),
            SettingSpec(
                "priority", "Prioridade do processo", "slider", "Desempenho", minimum=0, maximum=7
            ),
            SettingSpec("triplebuffer", "Triple buffering", "bool", VIDEO_CATEGORY),
            SettingSpec("syncrefresh", "Sincronizar refresh", "bool", VIDEO_CATEGORY),
            SettingSpec("unevenstretch", "Escala não inteira", "bool", VIDEO_CATEGORY),
            SettingSpec("switchres", "Trocar resolução em fullscreen", "bool", VIDEO_CATEGORY),
            SettingSpec("artwork_crop", "Cortar artwork", "bool", VIDEO_CATEGORY),
            SettingSpec("gl_glsl", "GLSL", "bool", VIDEO_CATEGORY),
            SettingSpec(
                "gl_glsl_filter",
                "Filtro GLSL",
                "combo",
                VIDEO_CATEGORY,
                (("0", "Plain"), ("1", "Bilinear"), ("2", "Bicubic")),
            ),
        ),
        "fbneo": (
            SettingSpec(
                "nVidSelect", "Blitter de vídeo", "slider", DRIVER_CATEGORY, minimum=0, maximum=6
            ),
            SettingSpec("bVidBilinear", "Filtragem bilinear", "bool", VIDEO_CATEGORY),
            SettingSpec("bVidScanlines", "Scanlines", "bool", VIDEO_CATEGORY),
            SettingSpec("bVidScanDelay", "Fósforo lento", "bool", VIDEO_CATEGORY),
            SettingSpec("nVidDX9HardFX", "HardFX", "slider", VIDEO_CATEGORY, minimum=0, maximum=20),
            SettingSpec("bVidHardwareVertex", "Hardware vertex", "bool", VIDEO_CATEGORY),
            SettingSpec("bVidMotionBlur", "Motion blur", "bool", VIDEO_CATEGORY),
            SettingSpec("bForce60Hz", "Forçar 60 Hz", "bool", VIDEO_CATEGORY),
            SettingSpec("bAlwaysDrawFrames", "Sempre desenhar frames", "bool", "Desempenho"),
            SettingSpec("bRunAhead", "Run-ahead", "bool", "Desempenho"),
            SettingSpec(
                "nAudSelect", "Plugin de áudio", "slider", DRIVER_CATEGORY, minimum=0, maximum=8
            ),
            SettingSpec("nAudVolume", "Volume", "slider", AUDIO_CATEGORY, minimum=0, maximum=10000),
            SettingSpec(
                "nAudSegCount", "Buffer de áudio", "slider", AUDIO_CATEGORY, minimum=2, maximum=20
            ),
            SettingSpec(
                "nAudSampleRate[0]",
                "Sample rate DirectSound",
                "combo",
                AUDIO_CATEGORY,
                (
                    ("22050", SAMPLE_RATE_22050_LABEL),
                    ("44100", SAMPLE_RATE_44100_LABEL),
                    ("48000", SAMPLE_RATE_48000_LABEL),
                    ("96000", SAMPLE_RATE_96000_LABEL),
                ),
            ),
            SettingSpec(
                "nAudSampleRate[1]",
                "Sample rate XAudio2",
                "combo",
                AUDIO_CATEGORY,
                (
                    ("22050", SAMPLE_RATE_22050_LABEL),
                    ("44100", SAMPLE_RATE_44100_LABEL),
                    ("48000", SAMPLE_RATE_48000_LABEL),
                    ("96000", SAMPLE_RATE_96000_LABEL),
                ),
            ),
            SettingSpec(
                "nInterpolation", "Interpolação PCM", "slider", AUDIO_CATEGORY, minimum=0, maximum=3
            ),
            SettingSpec(
                "nFMInterpolation",
                "Interpolação FM",
                "slider",
                AUDIO_CATEGORY,
                minimum=0,
                maximum=3,
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
                VIDEO_CATEGORY,
                (("0", "VGA"), ("1", "RGB"), ("2", "VGA Box"), ("3", "TV Composite")),
            ),
            SettingSpec(
                "Dreamcast.Region",
                "Região",
                "combo",
                "Sistema",
                (("0", "Japão"), ("1", "USA"), ("2", "Europa"), ("3", AUTO_OPTION_LABEL)),
            ),
            SettingSpec(
                "Dreamcast.Broadcast", "Broadcast", "slider", VIDEO_CATEGORY, minimum=0, maximum=4
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
                    ("6", AUTO_OPTION_LABEL),
                ),
            ),
            SettingSpec("Dynarec.Enabled", "Dynamic recompiler", "bool", "Desempenho"),
            SettingSpec("Dynarec.idleskip", "Idle skip", "bool", "Desempenho"),
            SettingSpec("Dynarec.unstable-opt", "Otimizações instáveis", "bool", "Desempenho"),
            SettingSpec("Dynarec.safe-mode", "Safe mode", "bool", "Desempenho"),
            SettingSpec("aica.DSPEnabled", "DSP", "bool", AUDIO_CATEGORY),
            SettingSpec("aica.LimitFPS", "Limitar FPS", "bool", AUDIO_CATEGORY),
            SettingSpec("aica.NoSound", "Sem som", "bool", AUDIO_CATEGORY),
            SettingSpec(
                "aica.BufferSize",
                "Buffer de áudio",
                "slider",
                AUDIO_CATEGORY,
                minimum=512,
                maximum=8192,
            ),
            SettingSpec(
                "backend",
                "Backend de áudio",
                "combo",
                DRIVER_CATEGORY,
                (
                    ("auto", AUTO_OPTION_LABEL),
                    ("wasapi", "WASAPI"),
                    ("sdl2", "SDL2"),
                    ("null", "Nulo"),
                ),
            ),
            SettingSpec("rend.UseMipmaps", "Mipmaps", "bool", VIDEO_CATEGORY),
            SettingSpec("rend.WideScreen", "Widescreen", "bool", VIDEO_CATEGORY),
            SettingSpec("rend.ShowFPS", "Mostrar FPS", "bool", VIDEO_CATEGORY),
            SettingSpec(
                "rend.TextureUpscale",
                "Upscale de texturas",
                "slider",
                VIDEO_CATEGORY,
                minimum=1,
                maximum=8,
            ),
            SettingSpec(
                "rend.MaxFilteredTextureSize",
                "Tamanho máximo filtrado",
                "slider",
                VIDEO_CATEGORY,
                minimum=64,
                maximum=4096,
            ),
            SettingSpec(
                "rend.ScreenScaling",
                "Escala da tela",
                "slider",
                VIDEO_CATEGORY,
                minimum=1,
                maximum=800,
            ),
            SettingSpec(
                "rend.ScreenStretching",
                "Alongamento",
                "slider",
                VIDEO_CATEGORY,
                minimum=1,
                maximum=200,
            ),
            SettingSpec("rend.Fog", "Fog", "bool", VIDEO_CATEGORY),
            SettingSpec("rend.Rotate90", "Rotacionar 90°", "bool", VIDEO_CATEGORY),
            SettingSpec(
                "rend.WidescreenGameHacks", "Widescreen game hacks", "bool", VIDEO_CATEGORY
            ),
            SettingSpec(
                "pvr.rend", "Renderer PVR", "slider", DRIVER_CATEGORY, minimum=0, maximum=8
            ),
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
            SettingSpec("New3DEngine", "Novo motor 3D", "bool", VIDEO_CATEGORY),
            SettingSpec("WideScreen", "Widescreen", "bool", VIDEO_CATEGORY),
            SettingSpec("FullScreen", "Fullscreen", "bool", VIDEO_CATEGORY),
            SettingSpec("VSync", "VSync", "bool", VIDEO_CATEGORY),
            SettingSpec("ShowStats", "Mostrar estatísticas", "bool", VIDEO_CATEGORY),
            SettingSpec("Stretch", "Stretch", "bool", VIDEO_CATEGORY),
            SettingSpec(
                "XResolution", "Resolução X", "slider", VIDEO_CATEGORY, minimum=320, maximum=7680
            ),
            SettingSpec(
                "YResolution", "Resolução Y", "slider", VIDEO_CATEGORY, minimum=240, maximum=4320
            ),
            SettingSpec(
                "SoundVolume", "Volume de som", "slider", AUDIO_CATEGORY, minimum=0, maximum=200
            ),
            SettingSpec(
                "MusicVolume", "Volume de música", "slider", AUDIO_CATEGORY, minimum=0, maximum=200
            ),
            SettingSpec("Balance", "Balanço", "slider", "Áudio", minimum=-100, maximum=100),
            SettingSpec(
                "InputSystem",
                "Sistema de input",
                "combo",
                DRIVER_CATEGORY,
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
            SettingSpec("Network", "Network board", "bool", ADVANCED_CATEGORY),
            SettingSpec("SimulateNet", "Simular rede", "bool", ADVANCED_CATEGORY),
        ),
        "retroarch": (
            SettingSpec(
                "video_driver",
                "Driver de vídeo",
                "combo",
                DRIVER_CATEGORY,
                (
                    ("gl", "OpenGL"),
                    ("d3d11", "Direct3D 11"),
                    ("d3d12", "Direct3D 12"),
                    ("vulkan", "Vulkan"),
                    ("sdl2", "SDL2"),
                ),
            ),
            SettingSpec("video_fullscreen", "Fullscreen", "bool", VIDEO_CATEGORY),
            SettingSpec(
                "video_windowed_fullscreen", "Fullscreen em janela", "bool", VIDEO_CATEGORY
            ),
            SettingSpec("video_vsync", "VSync", "bool", VIDEO_CATEGORY),
            SettingSpec("video_smooth", "Filtragem suave", "bool", VIDEO_CATEGORY),
            SettingSpec("video_scale_integer", "Escala inteira", "bool", VIDEO_CATEGORY),
            SettingSpec("video_allow_rotate", "Permitir rotação do core", "bool", VIDEO_CATEGORY),
            SettingSpec(
                "video_fullscreen_x",
                "Resolução X",
                "slider",
                VIDEO_CATEGORY,
                minimum=0,
                maximum=7680,
            ),
            SettingSpec(
                "video_fullscreen_y",
                "Resolução Y",
                "slider",
                VIDEO_CATEGORY,
                minimum=0,
                maximum=4320,
            ),
            SettingSpec(
                "video_monitor_index", "Monitor", "slider", VIDEO_CATEGORY, minimum=0, maximum=8
            ),
            SettingSpec("audio_enable", AUDIO_CATEGORY, "bool", AUDIO_CATEGORY),
            SettingSpec(
                "audio_driver",
                "Driver de áudio",
                "combo",
                DRIVER_CATEGORY,
                (("wasapi", "WASAPI"), ("xaudio", "XAudio"), ("sdl", "SDL"), ("null", "Nulo")),
            ),
            SettingSpec(
                "audio_out_rate",
                "Sample rate",
                "combo",
                AUDIO_CATEGORY,
                (
                    ("32000", "32 kHz"),
                    ("44100", SAMPLE_RATE_44100_LABEL),
                    ("48000", SAMPLE_RATE_48000_LABEL),
                    ("96000", SAMPLE_RATE_96000_LABEL),
                ),
            ),
            SettingSpec("audio_sync", "Sincronizar áudio", "bool", AUDIO_CATEGORY),
            SettingSpec(
                "audio_latency", "Latência (ms)", "slider", AUDIO_CATEGORY, minimum=1, maximum=256
            ),
            SettingSpec("audio_rate_control", "Rate control", "bool", AUDIO_CATEGORY),
            SettingSpec(
                "audio_volume", "Volume (dB)", "slider", AUDIO_CATEGORY, minimum=-40, maximum=12
            ),
            SettingSpec(
                "input_driver",
                "Driver de input",
                "combo",
                DRIVER_CATEGORY,
                (("dinput", "DirectInput"), ("sdl", "SDL"), ("raw", "Raw"), ("xinput", "XInput")),
            ),
            SettingSpec(
                "input_joypad_driver",
                "Driver de gamepad",
                "combo",
                DRIVER_CATEGORY,
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
        "azahar": (
            SettingSpec("fullscreen", "Tela cheia", "bool", VIDEO_CATEGORY),
            SettingSpec(
                "muteWhenInBackground", "Silenciar em segundo plano", "bool", AUDIO_CATEGORY
            ),
            SettingSpec("use_cpu_jit", "Usar JIT da CPU", "bool", "Desempenho"),
            SettingSpec(
                "graphics_api",
                "API gráfica",
                "combo",
                DRIVER_CATEGORY,
                (("0", "Software"), ("1", "OpenGL"), ("2", "Vulkan")),
            ),
            SettingSpec("use_hw_shader", "Usar shaders de hardware", "bool", VIDEO_CATEGORY),
            SettingSpec("use_vsync_new", "VSync", "bool", VIDEO_CATEGORY),
            SettingSpec(
                "resolution_factor",
                "Escala da resolução",
                "combo",
                VIDEO_CATEGORY,
                (
                    ("0", "Automática"),
                    ("1", "Nativa (1×)"),
                    *((str(scale), f"{scale}×") for scale in range(2, 19)),
                ),
            ),
            SettingSpec(
                "texture_filter",
                "Filtro de textura",
                "combo",
                VIDEO_CATEGORY,
                (
                    ("0", "Sem filtro"),
                    ("1", "Anime4K"),
                    ("2", "Bicúbico"),
                    ("3", "ScaleForce"),
                    ("4", "xBRZ"),
                    ("5", "MMPX"),
                ),
            ),
            SettingSpec(
                "texture_sampling",
                "Amostragem de textura",
                "combo",
                VIDEO_CATEGORY,
                (("0", "Controlada pelo jogo"), ("1", "Vizinho mais próximo"), ("2", "Linear")),
            ),
            SettingSpec("use_integer_scaling", "Escala inteira", "bool", VIDEO_CATEGORY),
            SettingSpec("volume", "Volume", "text", AUDIO_CATEGORY),
            SettingSpec(
                "region_value",
                "Região",
                "combo",
                "Sistema",
                (
                    ("-1", "Automática"),
                    ("0", "Japão"),
                    ("1", "EUA"),
                    ("2", "Europa"),
                    ("3", "Austrália"),
                    ("4", "China"),
                    ("5", "Coreia"),
                    ("6", "Taiwan"),
                ),
            ),
            SettingSpec(
                "layout_option",
                "Layout das telas",
                "combo",
                VIDEO_CATEGORY,
                (
                    ("0", "Original"),
                    ("1", "Tela única"),
                    ("2", "Tela ampliada"),
                    ("3", "Lado a lado"),
                    ("4", "Janelas separadas"),
                    ("5", "Híbrido"),
                    ("6", "Personalizado"),
                ),
            ),
            SettingSpec(
                "aspect_ratio",
                "Proporção da imagem",
                "combo",
                VIDEO_CATEGORY,
                (
                    ("0", "Padrão"),
                    ("1", "16:9"),
                    ("2", "4:3"),
                    ("3", "21:9"),
                    ("4", "16:10"),
                    ("5", "Esticar"),
                ),
            ),
            SettingSpec(
                "audio_emulation",
                "Emulação de áudio",
                "combo",
                AUDIO_CATEGORY,
                (("0", "HLE"), ("1", "LLE"), ("2", "LLE multithread")),
            ),
            SettingSpec("use_virtual_sd", "Usar cartão SD virtual", "bool", "Sistema"),
        ),
        "ares": (
            SettingSpec("Boot.Fast", "Inicialização rápida", "bool", "Sistema"),
            SettingSpec("Boot.Prefer", "Região preferencial", "text", "Sistema"),
            SettingSpec("General.Rewind", "Rewind", "bool", "Desempenho"),
            SettingSpec("General.RunAhead", "Run-ahead", "bool", "Desempenho"),
            SettingSpec(
                "General.AutoSaveMemory", "Salvar memória automaticamente", "bool", "Sistema"
            ),
            SettingSpec("General.NoFilePrompt", "Não solicitar mídia adicional", "bool", "Sistema"),
            SettingSpec(
                "Developer.HomebrewMode", "Modo de desenvolvimento homebrew", "bool", "Avançado"
            ),
            SettingSpec("Developer.ForceInterpreter", "Forçar interpretador", "bool", "Avançado"),
            SettingSpec(
                "Nintendo64.ExpansionPak", "Expansion Pak do Nintendo 64", "bool", "Nintendo 64"
            ),
            SettingSpec(
                "Nintendo64.ControllerPakBankString",
                "Tamanho do Controller Pak",
                "combo",
                "Nintendo 64",
                (
                    ("32KiB (Default)", "32 KiB (padrão)"),
                    ("128KiB (Datel 1Meg)", "128 KiB (Datel 1Meg)"),
                    ("512KiB (Datel 4Meg)", "512 KiB (Datel 4Meg)"),
                    ("1984KiB (Maximum)", "1984 KiB (máximo)"),
                ),
            ),
            SettingSpec("GameBoyAdvance.Player", "Game Boy Player", "bool", "Game Boy Advance"),
            SettingSpec("MegaDrive.TMSS", "TMSS Boot ROM", "bool", "Mega Drive"),
            SettingSpec(
                "Rewind.Length",
                "Duração do rewind",
                "combo",
                "Desempenho",
                tuple((str(value), f"{value} estados") for value in (10, 20, 40, 80, 160, 320)),
            ),
            SettingSpec(
                "Rewind.Frequency",
                "Frequência do rewind",
                "combo",
                "Desempenho",
                tuple(
                    (str(value), f"A cada {value} quadros") for value in (20, 40, 60, 80, 100, 120)
                ),
            ),
            SettingSpec("Audio.Frequency", "Frequência de saída", "readonly", AUDIO_CATEGORY),
            SettingSpec("Audio.Latency", "Latência", "readonly", AUDIO_CATEGORY),
            SettingSpec("Audio.Mute", "Silenciar áudio", "bool", AUDIO_CATEGORY),
            SettingSpec(
                "Audio.Volume",
                "Volume",
                "slider",
                AUDIO_CATEGORY,
                minimum=0,
                maximum=200,
                value_scale=100.0,
            ),
            SettingSpec(
                "Audio.Balance",
                "Balance",
                "slider",
                AUDIO_CATEGORY,
                minimum=0,
                maximum=100,
                value_scale=50.0,
                value_offset=50.0,
            ),
            SettingSpec(
                "Video.Driver",
                "Driver de vídeo (reinicie o ares para aplicar)",
                "combo",
                DRIVER_CATEGORY,
                (
                    ("OpenGL 3.2", "OpenGL 3.2"),
                    ("OpenGL 4.6", "OpenGL 4.6"),
                    ("Direct3D 9.0", "Direct3D 9.0"),
                    ("None", "Nenhum"),
                ),
            ),
            SettingSpec(
                "Audio.Driver",
                "Driver de áudio",
                "combo",
                DRIVER_CATEGORY,
                (
                    ("WASAPI", "WASAPI"),
                    ("XAudio 2.9", "XAudio 2.9"),
                    ("SDL", "SDL"),
                    ("DirectSound 7.0", "DirectSound 7.0"),
                    ("waveOut", "waveOut"),
                    ("None", "Nenhum"),
                ),
            ),
            SettingSpec(
                "Input.Driver",
                "Driver de controles",
                "combo",
                DRIVER_CATEGORY,
                (("Windows", "Windows"), ("SDL", "SDL"), ("None", "Nenhum")),
            ),
            SettingSpec(
                "Input.Defocus",
                "Comportamento ao perder foco",
                "combo",
                "Controles",
                (("Pause", "Pausar"), ("Block", "Bloquear entrada"), ("Allow", "Continuar")),
            ),
            SettingSpec(
                "Input.DigitalToAnalog",
                "Digital para analógico",
                "combo",
                "Controles",
                (
                    ("Immediate", "Imediato"),
                    ("GradualReturn", "Gradual, retorna ao centro"),
                    ("GradualHold", "Gradual, mantém posição"),
                ),
            ),
            SettingSpec(
                "Input.DigitalToAnalogTime",
                "Tempo de deslocamento (ms)",
                "slider",
                "Controles",
                minimum=100,
                maximum=1000,
            ),
        ),
    }

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        section: str = "emulators",
        only_emulator: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.section = section
        self.only_emulator = only_emulator
        self.controls: dict[tuple[str, str], QWidget] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Cria nível 2 por emulador e nível 3 por categoria."""
        root = QVBoxLayout(self)
        titles = {
            "emulators": "Configurações gerais dos Emuladores",
            "video": "Configurações de vídeo dos Emuladores",
            "drivers": "Drivers de vídeo, áudio e controles dos Emuladores",
            "audio": "Configurações de som dos Emuladores",
            "controls": "Configurações de controles dos Emuladores",
        }
        title_text = titles.get(self.section, "Configurações dos Emuladores")
        if self.only_emulator:
            title_text = f"{title_text} · {self.only_emulator.upper()}"
        title = QLabel(title_text)
        title.setProperty("role", "title")
        root.addWidget(title)
        info = QLabel(
            "Somente opções documentadas e presentes no arquivo real ficam editáveis. Salvar cria backup e altera apenas as chaves suportadas."
        )
        info.setWordWrap(True)
        root.addWidget(info)
        self.category_tabs = QTabWidget()
        self.emulator_tabs: dict[str, QTabWidget] = {}
        self.pending_status: dict[str, tuple[QLabel, QLabel, str]] = {}
        self.altirra_page: AltirraSettingsPage | None = None
        self.amiberry_page: AmiberrySettingsPage | None = None
        self.winuae_page: WinUAESettingsPage | None = None
        self.ares_controls_page: AresControlsPage | None = None
        if self.only_emulator:
            self._build_emulator(self.only_emulator, self.category_tabs)
            self.category_tabs.tabBar().hide()
            root.addWidget(self.category_tabs, 1)
            return
        labels = {key: label for key, label, _config in DirectoryGuidePage.EMULATORS}
        config_keys = {
            key: config_key or f"{key}_config"
            for key, _label, config_key in DirectoryGuidePage.EMULATORS
        }
        for category, members in DirectoryGuidePage.CATEGORIES:
            category_page = QWidget()
            category_layout = QVBoxLayout(category_page)
            category_layout.setContentsMargins(0, 0, 0, 0)
            tabs = QTabWidget()
            self.emulator_tabs[category] = tabs
            for emulator in members:
                if emulator in self.SPECS:
                    self._build_emulator(emulator, tabs)
                elif emulator == "altirra":
                    if AltirraSettingsPage.supports_section(self.section):
                        self.altirra_page = AltirraSettingsPage(self, section=self.section)
                        tabs.addTab(self.altirra_page, labels[emulator].split(" · ", 1)[0])
                elif emulator == "amiberry":
                    if AmiberrySettingsPage.supports_section(self.section):
                        self.amiberry_page = AmiberrySettingsPage(self, section=self.section)
                        tabs.addTab(self.amiberry_page, "Amiberry")
                elif emulator == "winuae":
                    if WinUAESettingsPage.supports_section(self.section):
                        self.winuae_page = WinUAESettingsPage(self, section=self.section)
                        tabs.addTab(self.winuae_page, "WinUAE")
                elif self.section == "emulators":
                    self._build_pending_emulator(
                        emulator, labels[emulator], config_keys[emulator], tabs
                    )
            if tabs.count() == 0:
                continue
            category_layout.addWidget(tabs)
            self.category_tabs.addTab(category_page, category)
        root.addWidget(self.category_tabs, 1)

    def _build_pending_emulator(
        self, emulator: str, label: str, config_key: str, tabs: QTabWidget
    ) -> None:
        """Give every directory registry emulator a settings page from day one."""
        page = QWidget()
        layout = QVBoxLayout(page)
        heading = QLabel(label)
        heading.setProperty("role", "title")
        layout.addWidget(heading)
        information = QLabel(
            "A guia deste emulador está pronta para receber opções específicas. "
            "Selecione o arquivo em 01-Diretórios e envie-o para mapear as opções "
            "compatíveis com o formato nativo."
        )
        information.setWordWrap(True)
        layout.addWidget(information)
        executable_status = QLabel()
        config_status = QLabel()
        layout.addWidget(executable_status)
        layout.addWidget(config_status)
        self.pending_status[emulator] = (executable_status, config_status, config_key)
        layout.addStretch(1)
        tabs.addTab(page, label.split(" · ", 1)[0])

    def _build_emulator(self, emulator: str, tabs_container: QTabWidget) -> None:
        """Cria a guia de segundo nível e suas categorias de terceiro nível."""
        specs = self._specs_for(emulator)
        if not specs:
            return
        page = QWidget()
        outer = QVBoxLayout(page)
        tabs = QTabWidget()
        categories = sorted({s.category for s in specs}, key=lambda x: (x == ADVANCED_CATEGORY, x))
        for category in categories:
            cat_page = QWidget()
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(cat_page)
            form = QFormLayout(cat_page)
            form.setContentsMargins(14, 14, 14, 14)
            form.setHorizontalSpacing(18)
            for spec in (s for s in specs if s.category == category):
                control = self._make_control(spec)
                self.controls[(emulator, spec.key)] = control
                form.addRow(self._label(spec), control)
            tabs.addTab(scroll, category)
        if emulator == "ares" and self.section == "controls":
            self.ares_controls_page = AresControlsPage(tabs)
            tabs.addTab(self.ares_controls_page, "Gamepads virtuais")
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
        tabs_container.addTab(page, emulator.upper() if emulator != "retroarch" else "RetroArch")

    @staticmethod
    def _category_section(category: str) -> str | None:
        normalized = category.casefold().replace("í", "i").replace("á", "a")
        if normalized == "drivers":
            return "drivers"
        if "video" in normalized:
            return "video"
        if "audio" in normalized:
            return "audio"
        if "controle" in normalized or "input" in normalized or "hotkey" in normalized:
            return "controls"
        return None

    def _specs_for(self, emulator: str) -> tuple[SettingSpec, ...]:
        if self.only_emulator and emulator != self.only_emulator:
            return ()
        specs = self.SPECS.get(emulator, ())
        if self.section == "emulators":
            return tuple(spec for spec in specs if self._category_section(spec.category) is None)
        return tuple(
            spec for spec in specs if self._category_section(spec.category) == self.section
        )

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
            widget = SliderControl()
            box = QHBoxLayout(widget)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(spec.minimum, spec.maximum)
            spin = QSpinBox()
            spin.setRange(spec.minimum, spec.maximum)
            slider.valueChanged.connect(spin.setValue)
            spin.valueChanged.connect(slider.setValue)
            box.addWidget(slider, 1)
            box.addWidget(spin)
            widget.slider = slider
            widget.spin = spin
            return widget
        edit = QLineEdit()
        if spec.kind == "readonly":
            edit.setReadOnly(True)
            edit.setToolTip(
                "Opção dinâmica do backend; os valores possíveis dependem deste computador."
            )
        return edit

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
            if index < 0:
                control.addItem(f"Current value (preserved): {raw}", raw)  # type: ignore[attr-defined]
                index = control.count() - 1  # type: ignore[attr-defined]
            control.setCurrentIndex(index)  # type: ignore[attr-defined]
            if index < 0:
                control.setToolTip(f"Valor atual não documentado nesta lista: {raw}")
        elif spec.kind == "slider":
            try:
                raw_number = float(raw.replace(",", "."))
                number = round(raw_number * spec.value_scale + spec.value_offset)
            except ValueError:
                number = spec.minimum
            number = max(spec.minimum, min(spec.maximum, number))
            if isinstance(control, SliderControl):
                control.slider.setValue(number)
                control.spin.setValue(number)
        else:
            control.setText(raw)  # type: ignore[attr-defined]

    def _control_value(self, control: QWidget, spec: SettingSpec, original: str) -> str:
        """Obtém o valor do widget no formato aceito pelo arquivo."""
        if spec.kind == "bool":
            return self._bool_value(control.isChecked(), original)  # type: ignore[attr-defined]
        if spec.kind == "combo":
            return str(control.currentData())  # type: ignore[attr-defined]
        if spec.kind == "slider":
            if not isinstance(control, SliderControl):
                return "0"
            value = (control.spin.value() - spec.value_offset) / spec.value_scale
            return f"{value:.4f}".rstrip("0").rstrip(".")
        return control.text().strip()  # type: ignore[attr-defined]

    def _disable_emulator_controls(self, emulator: str) -> None:
        for spec in self._specs_for(emulator):
            self.controls[(emulator, spec.key)].setEnabled(False)

    def _refresh_emulator(self, emulator: str, editor) -> None:
        status = self.findChild(QLabel, f"settings_status_{emulator}")
        if status:
            status.setText(f"Arquivo: {editor.path}")
        for spec in self._specs_for(emulator):
            control = self.controls[(emulator, spec.key)]
            values = editor.values(spec.key)
            control.setEnabled(bool(values))
            if values:
                self._set_control(control, spec, values[0])

    def refresh(self) -> None:
        """Lê os arquivos e atualiza todos os controles sem gravar nada."""
        if self.ares_controls_page is not None:
            self.ares_controls_page.refresh()
        for emulator in self.SPECS:
            if not self._specs_for(emulator):
                continue
            editor = self._editor(emulator)
            if editor is None:
                status = self.findChild(QLabel, f"settings_status_{emulator}")
                if status:
                    status.setText("Arquivo: não configurado / não encontrado")
                self._disable_emulator_controls(emulator)
                continue
            self._refresh_emulator(emulator, editor)
        if self.altirra_page is not None:
            self.altirra_page.refresh()
        if self.amiberry_page is not None:
            self.amiberry_page.refresh()
        if self.winuae_page is not None:
            self.winuae_page.refresh()
        paths = self._load_paths()
        for emulator, (executable_label, config_label, config_key) in self.pending_status.items():
            executable_label.setText(
                f"Executável registrado: {paths.get(f'{emulator}_exe') or '—'}"
            )
            config_label.setText(f"Arquivo de configuração: {paths.get(config_key) or '—'}")

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
            for spec in self._specs_for(emulator):
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
