"""Canonical Layer-1 schema for the global RetroArch configuration.

The schema contains only options administered by the application. Core options,
content-specific overrides and shader presets remain outside this global schema.
"""
from __future__ import annotations

from .config_schema import Setting, _s

RETROARCH_SCHEMA: dict[str, tuple[Setting, ...]] = {
    "general": (
        _s("video_driver", "Driver de vídeo", "Backend de vídeo do RetroArch.", "choice", "auto", (("auto", "Automático"), ("gl", "OpenGL"), ("glcore", "OpenGL Core"), ("vulkan", "Vulkan"), ("d3d11", "Direct3D 11"), ("d3d12", "Direct3D 12"), ("d3d10", "Direct3D 10"), ("d3d9", "Direct3D 9"), ("sdl2", "SDL2"), ("sdl3", "SDL3"), ("gdi", "GDI")), "video-backend"),
        _s("audio_driver", "Driver de áudio", "Backend de áudio do RetroArch.", "string", "auto", feature="audio"),
        _s("input_driver", "Driver de input", "Backend de entrada do RetroArch.", "string", "auto", feature="input"),
    ),
    "video": (
        _s("video_fullscreen", "Tela cheia", "Executa o RetroArch em tela cheia.", "bool", False, feature="fullscreen"),
        _s("video_windowed_fullscreen", "Fullscreen sem borda", "Usa fullscreen em janela sem bordas.", "bool", True, feature="fullscreen"),
        _s("video_vsync", "VSync", "Sincroniza a apresentação dos frames.", "bool", True, feature="vsync"),
        _s("video_threaded", "Vídeo em thread", "Processa a apresentação de vídeo em uma thread separada.", "bool", False, feature="threading"),
        _s("video_fullscreen_x", "Resolução X", "Largura explícita da tela cheia; zero permite autodetecção.", "int", 0),
        _s("video_fullscreen_y", "Resolução Y", "Altura explícita da tela cheia; zero permite autodetecção.", "int", 0),
        _s("video_refresh_rate", "Refresh rate", "Taxa de atualização alvo.", "float", 59.94, feature="refresh-rate"),
        _s("video_hdr_enable", "HDR", "Ativa HDR no pipeline de vídeo quando suportado.", "bool", False, feature="hdr"),
        _s("video_hdr_max_nits", "HDR máximo (nits)", "Luminância máxima usada pelo pipeline HDR.", "int", 1000, feature="hdr"),
    ),
    "audio": (
        _s("audio_enable", "Áudio", "Ativa a saída de áudio.", "bool", True, feature="audio"),
        _s("audio_out_rate", "Sample rate", "Taxa de amostragem da saída de áudio.", "int", 48000, feature="audio"),
        _s("audio_latency", "Latência (ms)", "Latência alvo da saída de áudio.", "int", 64, feature="audio-latency"),
        _s("audio_sync", "Sincronização de áudio", "Mantém o áudio sincronizado com a execução.", "bool", True, feature="audio-sync"),
        _s("audio_rate_control", "Controle de taxa", "Permite ajuste de taxa para manter a sincronização.", "bool", True, feature="audio-rate-control"),
    ),
    "input": (
        _s("input_joypad_driver", "Joypad driver", "Backend de gamepad usado pelo RetroArch.", "string", "auto", feature="joypad"),
        _s("input_autodetect_enable", "Autodetecção", "Ativa autodetecção de dispositivos e perfis.", "bool", True, feature="input-autodetect"),
        _s("input_axis_threshold", "Axis threshold", "Limite de ativação dos eixos analógicos.", "float", 0.5),
        _s("input_analog_deadzone", "Analog deadzone", "Zona morta dos eixos analógicos.", "float", 0.0),
        _s("input_analog_sensitivity", "Analog sensitivity", "Sensibilidade dos eixos analógicos.", "float", 1.0),
        _s("input_remap_binds_enable", "Remapping", "Habilita remapeamento de binds.", "bool", True, feature="remapping"),
    ),
    "shaders": (
        _s("video_shader_enable", "Shader habilitado", "Ativa o shader configurado no frontend.", "bool", False, feature="shader"),
        _s("video_shader", "Preset", "Caminho do preset de shader usado pelo RetroArch.", "path", "", feature="shader"),
        _s("video_shader_dir", "Diretório", "Diretório base para shaders.", "path", "shaders", feature="shader"),
    ),
}
