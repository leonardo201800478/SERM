"""Leitura dos diretórios nativos definidos pelo retroarch.cfg."""
from __future__ import annotations

import re
from pathlib import Path


class RetroArchConfigService:
    """Interpreta somente a configuração de diretórios do RetroArch."""

    DIRECTORY_SUFFIX = "_directory"
    DIRECTORY_KEYS = {
        "content_directory",
        "core_assets_directory",
        "core_info_directory",
        "cursor_directory",
        "database_directory",
        "file_browser_directory",
        "libretro_directory",
        "playlist_directory",
        "recording_output_directory",
        "rgui_browser_directory",
        "rgui_config_directory",
        "savefile_directory",
        "savestate_directory",
        "screenshot_directory",
        "system_directory",
        "thumbnails_directory",
        "video_filter_dir",
        "video_shader_dir",
        "video_shader_directory",
    }

    @classmethod
    def read_directories(cls, config_path: Path, install_dir: Path) -> dict[str, str]:
        """Lê todos os diretórios explícitos do retroarch.cfg.

        Valores ``:\\`` são relativos à instalação do RetroArch. Caminhos
        absolutos permanecem absolutos. Valores especiais como ``default``
        são preservados literalmente, pois possuem semântica própria no RA.
        """
        config_path = Path(config_path).expanduser().resolve()
        install_dir = Path(install_dir).expanduser().resolve()
        if not config_path.is_file():
            raise FileNotFoundError(f"retroarch.cfg não encontrado: {config_path}")

        result: dict[str, str] = {}
        for raw_line in config_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            match = re.match(r"^([A-Za-z0-9_.-]+)\s*=\s*(.*)$", line)
            if not match:
                continue
            key, raw_value = match.groups()
            if key not in cls.DIRECTORY_KEYS and not key.endswith(cls.DIRECTORY_SUFFIX):
                continue
            value = raw_value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            if not value:
                continue
            result[key] = str(cls.resolve_value(value, install_dir))
        return result

    @staticmethod
    def resolve_value(value: str, install_dir: Path) -> Path | str:
        """Resolve um valor nativo do RetroArch sem destruir valores especiais."""
        normalized = value.replace("/", "\\")
        if normalized.casefold() in {"default", "null", "none"}:
            return value
        if normalized.startswith(":\\"):
            return (install_dir / normalized[2:]).resolve()
        path = Path(value).expanduser()
        if path.is_absolute():
            return path.resolve()
        return (install_dir / path).resolve()

    @staticmethod
    def config_path(install_dir: Path) -> Path:
        """Retorna o caminho padrão do retroarch.cfg."""
        return Path(install_dir).expanduser().resolve() / "retroarch.cfg"


__all__ = ["RetroArchConfigService"]
