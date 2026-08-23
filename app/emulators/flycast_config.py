"""Adapter para a configuração nativa do Flycast.

O Flycast organiza as opções principais na seção ``[config]`` e usa valores
``yes/no`` para booleanos. O adapter preserva as demais seções e chaves do
arquivo, atualizando somente opções explicitamente suportadas pela GUI.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class FlycastConfigError(RuntimeError):
    """Erro de leitura ou gravação da configuração do Flycast."""


class FlycastConfig:
    """Lê e grava opções do Flycast sem destruir configurações desconhecidas."""

    SECTION = "config"

    VIDEO_KEYS = {
        "renderer": "pvr.rend",
        "resolution": "rend.Resolution",
        "vsync": "rend.vsync",
        "fullscreen": "window.fullscreen",
        "filtering": "rend.TextureFiltering",
        "anisotropic": "rend.AnisotropicFiltering",
        "texture_upscale": "rend.TextureUpscale",
        "texture_upscale2": "rend.TextureUpscale2",
        "widescreen": "rend.WideScreen",
        "super_wide": "rend.SuperWideScreen",
        "threaded": "rend.ThreadedRendering",
        "fog": "rend.Fog",
        "mipmaps": "rend.UseMipmaps",
        "framebuffer": "rend.EmulateFramebuffer",
    }

    AUDIO_KEYS = {
        "vmu_sound": "VmuSound",
        "auto_latency": "aica.AutoLatency",
        "buffer_size": "aica.BufferSize",
        "dsp": "aica.DSPEnabled",
        "volume": "aica.Volume",
    }

    INPUT_KEYS = {
        "mouse_sensitivity": "MouseSensitivity",
        "raw_input": "RawInput",
        "vibration": "VirtualGamepadVibration",
    }

    GENERAL_KEYS = {
        "language": "Dreamcast.Language",
        "region": "Dreamcast.Region",
        "cable": "Dreamcast.Cable",
        "broadcast": "Dreamcast.Broadcast",
        "ram_mod_32mb": "Dreamcast.RamMod32MB",
        "per_game_vmu": "PerGameVmu",
        "physical_vmu": "UsePhysicalVmuMemory",
        "dynarec": "Dynarec.Enabled",
        "sh4_clock": "Sh4Clock",
    }

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)

    def exists(self) -> bool:
        """Indica se o arquivo de configuração existe."""
        return self.config_path.is_file()

    def read_text(self) -> str:
        """Lê o arquivo preservando seu conteúdo textual."""
        if not self.exists():
            raise FlycastConfigError(f"Arquivo não encontrado: {self.config_path}")
        try:
            return self.config_path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise FlycastConfigError(f"Falha ao ler {self.config_path}: {exc}") from exc

    @classmethod
    def get_value(cls, text: str, key: str, section: str = SECTION) -> str | None:
        """Obtém uma chave dentro de uma seção INI específica."""
        active = False
        for raw in text.splitlines():
            line = raw.strip()
            if line.startswith("[") and line.endswith("]"):
                active = line[1:-1].strip().casefold() == section.casefold()
                continue
            if not active or not line or line.startswith(("#", ";")) or "=" not in line:
                continue
            current, value = line.split("=", 1)
            if current.strip().casefold() == key.casefold():
                return value.strip()
        return None

    def get(self, key: str, default: Any = None) -> Any:
        """Retorna uma configuração do Flycast ou ``default``."""
        value = self.get_value(self.read_text(), key)
        return default if value is None else value

    def get_many(self, keys: dict[str, str]) -> dict[str, Any]:
        """Lê um conjunto de chaves preservando os nomes canônicos da GUI."""
        text = self.read_text()
        return {name: self.get_value(text, key) for name, key in keys.items()}

    def set_many(self, values: dict[str, Any]) -> None:
        """Atualiza várias opções na seção ``[config]`` atomicamente."""
        if not values:
            return
        text = self.read_text() if self.exists() else "[config]\n"
        lines = text.splitlines(keepends=True)
        section_start: int | None = None
        section_end = len(lines)

        for index, raw in enumerate(lines):
            stripped = raw.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                name = stripped[1:-1].strip().casefold()
                if name == self.SECTION.casefold():
                    section_start = index
                elif section_start is not None:
                    section_end = index
                    break

        if section_start is None:
            if text and not text.endswith(("\n", "\r")):
                text += "\n"
            text += f"\n[{self.SECTION}]\n"
            lines = text.splitlines(keepends=True)
            section_start = len(lines) - 1
            section_end = len(lines)

        for key, value in values.items():
            serialized = self._serialize(value)
            replaced = False
            for index in range(section_start + 1, section_end):
                stripped = lines[index].strip()
                if not stripped or stripped.startswith(("#", ";")) or "=" not in stripped:
                    continue
                current, _ = stripped.split("=", 1)
                if current.strip().casefold() == key.casefold():
                    lines[index] = f"{key} = {serialized}\n"
                    replaced = True
                    break
            if not replaced:
                lines.insert(section_end, f"{key} = {serialized}\n")
                section_end += 1

        self._atomic_write("".join(lines))

    def update_named(self, mapping: dict[str, Any]) -> None:
        """Converte nomes da GUI para chaves nativas e grava a configuração."""
        key_map = {
            **self.VIDEO_KEYS,
            **self.AUDIO_KEYS,
            **self.INPUT_KEYS,
            **self.GENERAL_KEYS,
        }
        native = {key_map[name]: value for name, value in mapping.items() if name in key_map}
        self.set_many(native)

    def read_named(self) -> dict[str, Any]:
        """Lê todas as opções conhecidas agrupadas pelos nomes da GUI."""
        mapping = {
            **self.VIDEO_KEYS,
            **self.AUDIO_KEYS,
            **self.INPUT_KEYS,
            **self.GENERAL_KEYS,
        }
        return self.get_many(mapping)

    @staticmethod
    def _serialize(value: Any) -> str:
        """Converte valores Python para a representação nativa do Flycast."""
        if isinstance(value, bool):
            return "yes" if value else "no"
        if value is None:
            return ""
        return str(value)

    def _atomic_write(self, text: str) -> None:
        """Cria backup e substitui o arquivo atomicamente."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        backup = self.config_path.with_suffix(self.config_path.suffix + ".bak")
        temporary = self.config_path.with_suffix(self.config_path.suffix + ".tmp")
        try:
            if self.config_path.exists():
                backup.write_text(self.config_path.read_text(encoding="utf-8-sig"), encoding="utf-8")
            temporary.write_text(text, encoding="utf-8", newline="")
            os.replace(temporary, self.config_path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise FlycastConfigError(f"Falha ao gravar {self.config_path}: {exc}") from exc
