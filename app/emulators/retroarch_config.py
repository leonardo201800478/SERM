"""Adapter para configuração nativa do RetroArch.

O RetroArch utiliza ``retroarch.cfg`` com linhas ``chave = valor``. O adapter
preserva comentários, includes e chaves desconhecidas e altera somente as
opções administradas pelo ARCADE MANAGER.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class RetroArchConfig:
    """Leitor/escritor seguro do ``retroarch.cfg``."""

    MANAGED_KEYS = {
        "video_driver",
        "video_fullscreen",
        "video_windowed_fullscreen",
        "video_fullscreen_x",
        "video_fullscreen_y",
        "video_refresh_rate",
        "video_vsync",
        "video_threaded",
        "video_allow_rotate",
        "video_rotation",
        "video_hdr_enable",
        "video_hdr_max_nits",
        "audio_enable",
        "audio_driver",
        "audio_out_rate",
        "audio_sync",
        "audio_latency",
        "audio_rate_control",
        "input_driver",
        "input_joypad_driver",
        "input_autodetect_enable",
        "input_axis_threshold",
        "input_analog_deadzone",
        "input_analog_sensitivity",
        "input_remap_binds_enable",
        "video_filter",
        "video_shader",
        "video_shader_enable",
        "video_shader_dir",
        "libretro_directory",
        "system_directory",
        "savefile_directory",
        "savestate_directory",
        "content_directory",
    }

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lines: list[str] = []
        self._newline = "\n"
        self.load()

    def load(self) -> None:
        """Carrega o arquivo mantendo sua representação textual."""
        if not self.path.is_file():
            self._lines = []
            return
        text = self.path.read_text(encoding="utf-8-sig")
        self._newline = "\r\n" if "\r\n" in text else "\n"
        self._lines = text.splitlines()

    @staticmethod
    def _parse_line(line: str) -> tuple[str, str] | None:
        """Extrai chave/valor de uma linha válida de configuração."""
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")) or "=" not in stripped:
            return None
        key, value = stripped.split("=", 1)
        return key.strip(), value.strip().strip('"')

    def get(self, key: str, default: str = "") -> str:
        """Obtém uma configuração pelo nome da chave."""
        for line in self._lines:
            parsed = self._parse_line(line)
            if parsed and parsed[0] == key:
                return parsed[1]
        return default

    def set(self, key: str, value: Any) -> None:
        """Altera uma chave existente ou acrescenta a chave ao final."""
        rendered = self._render_value(value)
        replacement = f'{key} = {rendered}'
        for index, line in enumerate(self._lines):
            parsed = self._parse_line(line)
            if parsed and parsed[0] == key:
                prefix = line[: len(line) - len(line.lstrip())]
                self._lines[index] = prefix + replacement
                return
        self._lines.append(replacement)

    @staticmethod
    def _render_value(value: Any) -> str:
        """Converte valores Python para o formato aceito pelo RetroArch."""
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return '""'
        if isinstance(value, (int, float)):
            return str(value)
        text = str(value)
        if not text:
            return '""'
        if any(char.isspace() for char in text) or "\\" in text or ":" in text:
            return f'"{text.replace(chr(34), chr(92) + chr(34))}"'
        return text

    def get_managed(self) -> dict[str, str]:
        """Retorna as opções administradas que estão presentes no arquivo."""
        return {key: self.get(key) for key in self.MANAGED_KEYS if self.get(key) != ""}

    def set_many(self, values: dict[str, Any]) -> None:
        """Atualiza várias opções conhecidas em uma única operação."""
        for key, value in values.items():
            if key in self.MANAGED_KEYS:
                self.set(key, value)

    def save(self, create_backup: bool = True) -> None:
        """Cria backup e grava o arquivo de forma atômica."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if create_backup and self.path.is_file():
            backup = self.path.with_suffix(self.path.suffix + ".bak")
            backup.write_bytes(self.path.read_bytes())
        text = self._newline.join(self._lines) + (self._newline if self._lines else "")
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8", newline="")
        os.replace(temporary, self.path)
