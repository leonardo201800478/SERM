"""Layer 1 configuration schemas for supported arcade emulators.

These schemas are deliberately limited to settings that belong to the
emulator itself. Runtime discovery of GPU backends, shader files and devices
is deferred to the dynamic capability layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ControlType = Literal["bool", "int", "float", "string", "choice", "path", "secret"]


@dataclass(frozen=True, slots=True)
class Setting:
    """Describes one editable emulator setting."""

    key: str
    label: str
    description: str
    control: ControlType
    default: Any
    choices: tuple[tuple[str, str], ...] = ()
    feature: str | None = None


def _s(key: str, label: str, description: str, control: ControlType, default: Any,
       choices: tuple[tuple[str, str], ...] = (), feature: str | None = None) -> Setting:
    """Build a canonical setting declaration."""
    return Setting(key, label, description, control, default, choices, feature)


SCHEMAS: dict[str, dict[str, tuple[Setting, ...]]] = {
    "mame": {
        "general": (
            _s("window", "Janela", "Executa o MAME em janela em vez de tela cheia.", "bool", False),
            _s("maximize", "Maximizar", "Maximiza a janela quando o modo janela está ativo.", "bool", False),
            _s("throttle", "Limitar velocidade", "Mantém a execução na velocidade nominal do sistema emulado.", "bool", True, feature="throttle"),
        ),
        "video": (
            _s("video", "Backend de vídeo", "Seleciona o sistema de renderização utilizado pelo MAME.", "choice", "bgfx", (("bgfx", "BGFX"), ("d3d", "Direct3D"), ("opengl", "OpenGL"), ("none", "Nenhum")), "video-backend"),
            _s("bgfx_backend", "Backend BGFX", "Backend gráfico utilizado quando BGFX está selecionado.", "choice", "auto", (("auto", "Automático"), ("d3d9", "Direct3D 9"), ("d3d11", "Direct3D 11"), ("d3d12", "Direct3D 12"), ("opengl", "OpenGL"), ("vulkan", "Vulkan")), "bgfx"),
            _s("fullscreen", "Tela cheia", "Executa o MAME em tela cheia.", "bool", True, feature="fullscreen"),
            _s("filter", "Filtragem", "Aplica filtragem ao vídeo quando suportada pelo backend.", "bool", True),
            _s("prescale", "Prescale", "Escala prévia a imagem antes do processamento do backend.", "int", 1),
            _s("keepaspect", "Manter proporção", "Preserva a proporção original da imagem.", "bool", True, feature="keep-aspect"),
            _s("unevenstretch", "Alongamento livre", "Permite escalonamento não inteiro para ocupar a tela.", "bool", True),
            _s("waitvsync", "VSync", "Sincroniza a apresentação dos frames com a atualização do monitor.", "bool", False, feature="vsync"),
            _s("syncrefresh", "Sincronizar refresh", "Sincroniza a execução com a taxa de atualização do sistema quando possível.", "bool", False, feature="sync-refresh"),
            _s("bgfx_screen_chains", "BGFX chain", "Seleciona o chain de pós-processamento BGFX.", "string", "default", feature="bgfx"),
            _s("hlsl_enable", "HLSL", "Ativa o pipeline HLSL de pós-processamento quando disponível.", "bool", False, feature="hlsl"),
            _s("gl_glsl", "GLSL", "Ativa o pipeline GLSL quando o backend OpenGL o suporta.", "bool", False, feature="glsl"),
        ),
        "audio": (
            _s("sound", "Som", "Ativa ou desativa a saída de áudio do MAME.", "bool", True, feature="sound"),
            _s("samplerate", "Taxa de amostragem", "Define a taxa de amostragem usada pela saída de áudio.", "int", 48000),
            _s("volume", "Volume", "Define o ganho global da saída de áudio.", "int", 0),
            _s("audio_latency", "Latência", "Controla o compromisso entre latência e tolerância a oscilações do áudio.", "int", 2, feature="audio-latency"),
            _s("samples", "Samples", "Permite o uso dos arquivos de samples requeridos pelas máquinas.", "bool", True, feature="samples"),
            _s("audio_backend", "Saída de áudio", "Seleciona o sistema de áudio quando suportado pela plataforma.", "choice", "auto", (("auto", "Automático"), ("none", "Nenhum"))),
        ),
        "input": (
            _s("keyboard", "Teclado", "Habilita entrada por teclado.", "bool", True, feature="keyboard"),
            _s("joystick", "Joystick", "Habilita entrada por controles/joysticks.", "bool", True, feature="joystick"),
            _s("mouse", "Mouse", "Habilita entrada por mouse.", "bool", True, feature="mouse"),
            _s("lightgun", "Lightgun", "Habilita dispositivos de lightgun quando disponíveis.", "bool", True, feature="lightgun"),
            _s("multikeyboard", "Múltiplos teclados", "Permite diferenciar múltiplos dispositivos de teclado.", "bool", False, feature="multikeyboard"),
            _s("multimouse", "Múltiplos mouses", "Permite diferenciar múltiplos dispositivos de mouse.", "bool", False, feature="multimouse"),
        ),
        "performance": (
            _s("frameskip", "Frameskip", "Define quantos frames podem ser ignorados para manter desempenho.", "int", 0, feature="frameskip"),
            _s("autoframeskip", "Frameskip automático", "Permite ao MAME ajustar o frameskip para manter a velocidade alvo.", "bool", False, feature="frameskip"),
            _s("speed", "Velocidade", "Define o multiplicador de velocidade da emulação.", "float", 1.0),
            _s("numprocessors", "Processadores", "Define a afinidade/quantidade de processadores usada quando suportada.", "string", "auto"),
        ),
        "paths": (
            _s("rompath", "ROM path", "Diretórios onde o MAME procura ROMs.", "path", ""),
            _s("samplepath", "Sample path", "Diretórios onde o MAME procura samples.", "path", ""),
            _s("cfg_directory", "CFG path", "Diretório dos arquivos de configuração das máquinas.", "path", ""),
            _s("nvram_directory", "NVRAM path", "Diretório dos dados persistentes NVRAM.", "path", ""),
            _s("state_directory", "State path", "Diretório dos save states.", "path", ""),
        ),
    },
    "flycast": {
        "general": (
            _s("region", "Região", "Região utilizada pela emulação.", "choice", "auto", (("auto", "Automático"), ("japan", "Japão"), ("usa", "EUA"), ("europe", "Europa"))),
            _s("language", "Idioma", "Idioma utilizado quando o sistema/software oferece essa seleção.", "choice", "english", (("english", "Inglês"), ("japanese", "Japonês"))),
        ),
        "video": (
            _s("renderer", "Renderer", "Seleciona o backend de renderização disponível no Flycast.", "choice", "auto", (("auto", "Automático"), ("opengl", "OpenGL"), ("vulkan", "Vulkan"))),
            _s("fullscreen", "Tela cheia", "Executa o Flycast em tela cheia.", "bool", True, feature="fullscreen"),
            _s("integer_scaling", "Escala inteira", "Usa fatores inteiros de escala quando possível.", "bool", False, feature="integer-scaling"),
            _s("filtering", "Filtragem", "Ativa filtragem da imagem.", "bool", True, feature="filtering"),
            _s("texture_filtering", "Filtragem de textura", "Controla a filtragem aplicada às texturas.", "choice", "auto", (("auto", "Automático"), ("nearest", "Nearest"), ("linear", "Linear")), "texture-filtering"),
            _s("texture_upscaling", "Upscaling de textura", "Controla a ampliação das texturas quando suportada.", "choice", "off", (("off", "Desligado"), ("2x", "2x"), ("4x", "4x")), "texture-upscaling"),
            _s("vsync", "VSync", "Sincroniza a apresentação dos frames com o monitor.", "bool", False, feature="vsync"),
            _s("widescreen", "Widescreen", "Aplica apresentação widescreen quando suportada pelo software.", "bool", False, feature="widescreen"),
        ),
        "audio": (
            _s("audio", "Áudio", "Ativa a saída de áudio.", "bool", True, feature="audio"),
            _s("audio_latency", "Latência", "Ajusta o compromisso entre latência e estabilidade do áudio.", "int", 1, feature="audio-latency"),
        ),
        "input": (
            _s("controller", "Controles", "Habilita suporte aos controles configurados.", "bool", True, feature="controller"),
            _s("lightgun", "Lightgun", "Habilita dispositivos de mira quando suportados.", "bool", True, feature="lightgun"),
            _s("wheel", "Volante", "Habilita entrada de volante para sistemas compatíveis.", "bool", True, feature="wheel"),
            _s("force_feedback", "Force Feedback", "Habilita retorno de força quando suportado.", "bool", True, feature="force-feedback"),
        ),
        "performance": (
            _s("dynarec", "Dynarec", "Usa recompilação dinâmica para acelerar a CPU emulada.", "bool", True, feature="dynarec"),
            _s("sh4_clock", "Clock SH4", "Ajusta o clock virtual do SH4; valores fora do padrão podem afetar compatibilidade.", "int", 200, feature="sh4-clock"),
            _s("threading", "Threading", "Controla recursos de execução paralela quando disponíveis.", "bool", True, feature="threading"),
        ),
        "achievements": (
            _s("retroachievements", "RetroAchievements", "Ativa integração com RetroAchievements.", "bool", False, feature="retroachievements"),
            _s("hardcore", "Hardcore", "Ativa o modo Hardcore quando suportado e autenticado.", "bool", False, feature="achievements-hardcore"),
            _s("username", "Usuário", "Nome da conta do RetroAchievements.", "string", ""),
            _s("token", "Token", "Credencial do RetroAchievements; deve ser armazenada de forma segura.", "secret", ""),
        ),
    },
    "supermodel": {
        "general": (_s("fullscreen", "Tela cheia", "Executa o Supermodel em tela cheia.", "bool", True),),
        "video": (
            _s("resolution", "Resolução", "Define a resolução de apresentação.", "string", "auto"),
            _s("vsync", "VSync", "Sincroniza a apresentação com a taxa de atualização do monitor.", "bool", False),
            _s("show_fps", "Mostrar FPS", "Exibe a taxa de frames durante a execução.", "bool", False, feature="show-fps"),
            _s("vertex_shader", "Vertex shader", "Seleciona o shader de vértices quando disponível.", "path", "", feature="vertex-shader"),
            _s("fragment_shader", "Fragment shader", "Seleciona o shader de fragmentos quando disponível.", "path", "", feature="fragment-shader"),
        ),
        "audio": (
            _s("sound", "Som", "Ativa a saída de áudio.", "bool", True, feature="audio"),
            _s("mpeg_audio", "Áudio MPEG", "Ativa o áudio MPEG quando usado pelo software.", "bool", True, feature="mpeg-audio"),
            _s("music_volume", "Volume da música", "Ajusta o volume da música.", "int", 100, feature="music-volume"),
            _s("sound_volume", "Volume dos efeitos", "Ajusta o volume dos efeitos sonoros.", "int", 100, feature="sound-volume"),
            _s("stereo_swap", "Inverter estéreo", "Troca os canais esquerdo e direito.", "bool", False, feature="stereo-swap"),
        ),
        "input": (
            _s("keyboard", "Teclado", "Habilita controles por teclado.", "bool", True, feature="keyboard"),
            _s("gamepad", "Gamepad", "Habilita controles por gamepad.", "bool", True, feature="gamepad"),
            _s("wheel", "Volante", "Habilita entrada de volante.", "bool", True, feature="wheel"),
            _s("pedal", "Pedais", "Habilita entrada de pedais.", "bool", True, feature="pedal"),
        ),
        "force_feedback": (
            _s("force_feedback", "Force Feedback", "Habilita retorno de força.", "bool", True, feature="force-feedback"),
        ),
        "paths": (
            _s("rompath", "ROM path", "Diretório onde o Supermodel procura os arquivos das máquinas.", "path", ""),
            _s("nvram", "NVRAM path", "Diretório para dados persistentes.", "path", ""),
        ),
    },
    "fbneo": {
        "general": (
            _s("region", "Região", "Região utilizada pelo core/software quando aplicável.", "choice", "auto", (("auto", "Automático"), ("japan", "Japão"), ("usa", "EUA"), ("europe", "Europa"))),
        ),
        "video": (
            _s("fullscreen", "Tela cheia", "Executa o FBNeo em tela cheia quando suportado.", "bool", True),
            _s("vsync", "VSync", "Sincroniza a apresentação dos frames.", "bool", False),
            _s("integer_scaling", "Escala inteira", "Mantém fatores inteiros de escala para a imagem.", "bool", False),
            _s("aspect_ratio", "Proporção", "Seleciona a proporção de apresentação.", "choice", "core", (("core", "Core"), ("4:3", "4:3"), ("16:9", "16:9"))),
            _s("filtering", "Filtragem", "Controla a filtragem de vídeo disponível no frontend/core.", "bool", True),
        ),
        "audio": (_s("audio", "Áudio", "Ativa a saída de áudio.", "bool", True),),
        "input": (
            _s("keyboard", "Teclado", "Habilita controles por teclado.", "bool", True),
            _s("gamepad", "Gamepad", "Habilita controles por gamepad.", "bool", True),
            _s("lightgun", "Lightgun", "Habilita entrada de lightgun quando disponível.", "bool", True),
            _s("wheel", "Volante", "Habilita entrada de volante quando disponível.", "bool", True),
        ),
        "performance": (
            _s("frameskip", "Frameskip", "Permite reduzir frames processados quando o desempenho for insuficiente.", "int", 0, feature="frameskip"),
            _s("save_state", "Save state", "Habilita o uso de estados salvos quando o frontend/core oferecer suporte.", "bool", True, feature="save-state"),
        ),
        "achievements": (_s("retroachievements", "RetroAchievements", "Ativa RetroAchievements quando o FBNeo estiver sendo usado através de um frontend compatível.", "bool", False, feature="retroachievements"),),
    },
}


def get_schema(emulator: str) -> dict[str, tuple[Setting, ...]]:
    """Return the canonical Layer-1 schema for an emulator.

    RetroArch keeps its larger schema in a dedicated module so that its
    frontend-specific contract does not inflate the generic emulator schema.
    The import is intentionally lazy to avoid a circular import because
    ``retroarch_schema`` reuses ``Setting`` and ``_s`` from this module.
    """
    key = emulator.strip().lower()
    if key == "retroarch":
        from .retroarch_schema import RETROARCH_SCHEMA

        return RETROARCH_SCHEMA
    try:
        return SCHEMAS[key]
    except KeyError as exc:
        raise ValueError(f"Emulador não suportado: {emulator}") from exc
