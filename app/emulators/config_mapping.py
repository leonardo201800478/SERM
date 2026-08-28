"""Map canonical schema keys to verified physical emulator keys.

Este módulo é deliberadamente pequeno: o schema define a interface canônica
e os adapters definem como ela é persistida. Só entram aqui equivalências de
semântica direta; transformações (por exemplo fullscreen <-> window no MAME)
continuam fora do mapping simples.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config_schema import get_schema


@dataclass(frozen=True, slots=True)
class ConfigMapping:
    """Representa uma tradução direta de chave canônica para chave física."""

    emulator: str
    canonical_key: str
    physical_key: str


_MAPPINGS: tuple[ConfigMapping, ...] = (
    # MAME: nomes canônicos precisam ser exatamente os do schema.
    ConfigMapping("mame", "window", "window"),
    ConfigMapping("mame", "waitvsync", "waitvsync"),
    ConfigMapping("mame", "syncrefresh", "syncrefresh"),
    ConfigMapping("mame", "keepaspect", "keepaspect"),
    ConfigMapping("mame", "frameskip", "frameskip"),
    ConfigMapping("mame", "throttle", "throttle"),
    ConfigMapping("mame", "samplerate", "samplerate"),
    ConfigMapping("mame", "audio_latency", "audio_latency"),
    ConfigMapping("mame", "joystick", "joystick"),
    ConfigMapping("mame", "mouse", "mouse"),
    ConfigMapping("mame", "lightgun", "lightgun"),
    # Flycast.
    ConfigMapping("flycast", "fullscreen", "fullscreen"),
    ConfigMapping("flycast", "vsync", "vsync"),
    ConfigMapping("flycast", "audio_latency", "audio_latency"),
    ConfigMapping("flycast", "retroachievements", "retroachievements"),
    # Supermodel.
    ConfigMapping("supermodel", "fullscreen", "FullScreen"),
    ConfigMapping("supermodel", "vsync", "VSync"),
    ConfigMapping("supermodel", "show_fps", "ShowFPS"),
    ConfigMapping("supermodel", "music_volume", "MusicVolume"),
    ConfigMapping("supermodel", "sound_volume", "SoundVolume"),
    ConfigMapping("supermodel", "stereo_swap", "StereoSwap"),
    # FBNeo é mantido principalmente no formato nativo; não inventar chaves.
    # RetroArch: somente retroarch.cfg; opções de core (.opt) não pertencem aqui.
    ConfigMapping("retroarch", "fullscreen", "video_fullscreen"),
    ConfigMapping("retroarch", "vsync", "video_vsync"),
    ConfigMapping("retroarch", "video_threaded", "video_threaded"),
    ConfigMapping("retroarch", "audio_enable", "audio_enable"),
    ConfigMapping("retroarch", "audio_out_rate", "audio_out_rate"),
    ConfigMapping("retroarch", "audio_latency", "audio_latency"),
    ConfigMapping("retroarch", "input_joypad_driver", "input_joypad_driver"),
    ConfigMapping("retroarch", "input_autodetect_enable", "input_autodetect_enable"),
    ConfigMapping("retroarch", "video_shader", "video_shader"),
    ConfigMapping("retroarch", "video_shader_enable", "video_shader_enable"),
)

_INDEX = {(item.emulator, item.canonical_key): item for item in _MAPPINGS}


def get_mapping(emulator: str, canonical_key: str) -> ConfigMapping | None:
    """Retorna o mapping físico ou ``None`` se não houver equivalência direta."""
    return _INDEX.get((emulator.strip().lower(), canonical_key.strip()))


def physical_key(emulator: str, canonical_key: str) -> str | None:
    """Retorna a chave física para uma configuração canônica."""
    mapping = get_mapping(emulator, canonical_key)
    return mapping.physical_key if mapping else None


def validate_mappings() -> tuple[str, ...]:
    """Detecta mappings cujo canonical_key não existe no schema atual.

    O retorno vazio é a condição esperada. A função é usada por testes e evita
    que uma refatoração do schema deixe traduções silenciosamente órfãs.
    """
    errors: list[str] = []
    for mapping in _MAPPINGS:
        schema = get_schema(mapping.emulator)
        known = {setting.key for domain in schema.values() for setting in domain}
        if mapping.canonical_key not in known:
            errors.append(f"{mapping.emulator}:{mapping.canonical_key}")
    return tuple(errors)
