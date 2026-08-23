import json
import os
from pathlib import Path

from app.emulators.supermodel_config import SupermodelConfig


class AppConfig:
    """Configuração persistente do ARCADE MANAGER."""

    CONFIG_DIR = Path.home() / ".mame-set-builder"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    DB_DIR = PROJECT_ROOT / "data" / "database"
    DB_PATH = DB_DIR / "mame_set_builder.db"
    SCAN_DIR = DB_DIR / "scan"

    EMULATOR_PATH_DEFAULTS = {
        "flycast": {"roms": "roms", "bios": "data", "vmu": "data", "saves": "data", "states": "data", "textures": "data", "boxart": "data", "cheats": "cheats"},
        "supermodel": {"roms": "ROMs", "config": "Config", "nvram": "NVRAM", "saves": "Saves", "assets": "Assets"},
        "fbneo": {"roms": "roms", "neocd": "neocdiso", "previews": "support/previews", "titles": "support/titles", "cheats": "support/cheats", "hiscore": "support/hiscores", "samples": "support/samples", "hdd": "support/hdd", "ips": "support/ips", "romdata": "support/romdata", "icons": "support/icons", "neocd_covers": "support/neocdz", "neocd_previews": "support/neocdzpreviews", "blend": "support/blend", "select": "support/select", "versus": "support/versus", "howto": "support/howto", "scores": "support/scores", "bosses": "support/bosses", "gameover": "support/gameover", "flyers": "support/flyers", "marquees": "support/marquees", "controls": "support/cpanel", "cabinets": "support/cabinets", "pcbs": "support/pcbs", "history": "support/history", "commands": "support/commands", "eeprom": "config/games"},
        "retroarch": {"config": "config", "cores": "cores", "system": "system", "assets": "assets", "shaders": "shaders", "saves": "saves", "states": "states", "downloads": "downloads"},
    }

    RETROARCH_DIRECTORY_KEYS = (
        "assets_directory", "cache_directory", "cheat_database_path",
        "content_database_path", "content_directory", "core_assets_directory",
        "dynamic_wallpapers_directory", "input_remapping_directory",
        "libretro_directory", "libretro_info_path", "osk_overlay_directory",
        "overlay_directory", "playlist_directory", "recording_config_directory",
        "recording_output_directory", "rgui_browser_directory", "rgui_config_directory",
        "savefile_directory", "savestate_directory", "screenshot_directory",
        "system_directory", "thumbnails_directory", "video_font_path",
        "video_shader_directory",
    )

    def __init__(self):
        self.mame_path: Path | None = None
        self.flycast_path: Path | None = None
        self.supermodel_path: Path | None = None
        self.fbneo_path: Path | None = None
        self.retroarch_path: Path | None = None
        self.mame_dir: Path | None = None
        self.flycast_dir: Path | None = None
        self.supermodel_dir: Path | None = None
        self.fbneo_dir: Path | None = None
        self.retroarch_dir: Path | None = None
        self.mame_version: str | None = None
        self.flycast_version: str | None = None
        self.supermodel_version: str | None = None
        self.fbneo_version: str | None = None
        self.retroarch_version: str | None = None
        self.emulator_paths = {emulator: {name: None for name in paths} for emulator, paths in self.EMULATOR_PATH_DEFAULTS.items()}
        self.flycast_rom_paths: list[Path] = []
        self.retroarch_native_paths: dict[str, Path | str] = {}
        self.retroarch_config_file: Path | None = None
        self.retroarch_core_config_dir: Path | None = None
        self.retroarch_core_remap_dir: Path | None = None
        self.retroarch_core_shader_dir: Path | None = None
        self.chdman_path: Path | None = None
        self.ini_path: Path | None = None
        self.catver_path: Path | None = None
        self.db_path: Path = self.DB_PATH
        self.source_dirs: list[Path] = []
        self.destination_dir: Path | None = None
        self.output_layout: str = "single"
        self.cache_dir: Path | None = None
        self.cache_limit_mb: int = 1024
        self.scan_workers: int = max(1, min(os.cpu_count() or 2, 16))
        self._ensure_directories()
        self.load()

    def _ensure_directories(self):
        """Garante os diretórios persistentes do aplicativo."""
        self.DB_DIR.mkdir(parents=True, exist_ok=True)
        self.SCAN_DIR.mkdir(parents=True, exist_ok=True)

    def load(self):
        """Carrega configurações persistidas."""
        if not self.CONFIG_FILE.exists():
            return
        try:
            data = json.loads(self.CONFIG_FILE.read_text(encoding="utf-8"))
            for attr in ("mame_path", "flycast_path", "supermodel_path", "fbneo_path", "retroarch_path"):
                value = data.get(attr)
                setattr(self, attr, Path(value) if value else None)
            for attr, path_attr in (("mame_dir", "mame_path"), ("flycast_dir", "flycast_path"), ("supermodel_dir", "supermodel_path"), ("fbneo_dir", "fbneo_path"), ("retroarch_dir", "retroarch_path")):
                setattr(self, attr, self._load_dir(data, attr, getattr(self, path_attr)))
            for emulator in ("mame", "flycast", "supermodel", "fbneo", "retroarch"):
                self.__dict__[f"{emulator}_version"] = data.get(f"{emulator}_version") or None

            persisted_paths = data.get("emulator_paths", {})
            for emulator, defaults in self.EMULATOR_PATH_DEFAULTS.items():
                stored = persisted_paths.get(emulator, {})
                for name in defaults:
                    value = stored.get(name)
                    self.emulator_paths[emulator][name] = Path(value) if value else None

            native_paths = data.get("retroarch_native_paths", {})
            if isinstance(native_paths, dict):
                self.retroarch_native_paths = {
                    str(k): (Path(v) if isinstance(v, str) and v else v)
                    for k, v in native_paths.items()
                }
            cfg = data.get("retroarch_config_file")
            self.retroarch_config_file = Path(cfg) if cfg else None
            self._derive_retroarch_core_layout()

            stored_flycast_roms = data.get("flycast_rom_paths")
            if isinstance(stored_flycast_roms, list):
                self.flycast_rom_paths = [Path(value) for value in stored_flycast_roms if value][:4]
            elif isinstance(stored_flycast_roms, str):
                self.flycast_rom_paths = [Path(value.strip()) for value in stored_flycast_roms.split(";") if value.strip()][:4]
            else:
                legacy_rom = self.emulator_paths["flycast"].get("roms")
                self.flycast_rom_paths = [legacy_rom] if legacy_rom else []

            if self.mame_dir:
                canonical_mame = self.mame_dir.expanduser() / "mame.exe"
                self.mame_path = canonical_mame if canonical_mame.is_file() else None

            self.chdman_path = Path(data["chdman_path"]) if data.get("chdman_path") else None
            self.ini_path = Path(data["ini_path"]) if data.get("ini_path") else None
            self.catver_path = Path(data["catver_path"]) if data.get("catver_path") else None
            self.source_dirs = [Path(p) for p in data.get("source_dirs", [])[:3] if p]
            self.destination_dir = Path(data["destination_dir"]) if data.get("destination_dir") else None
            self.output_layout = data.get("output_layout", "single") if data.get("output_layout") in {"single", "split"} else "single"
            self.cache_dir = Path(data["cache_dir"]) if data.get("cache_dir") else None
            self.cache_limit_mb = max(64, int(data.get("cache_limit_mb", 1024)))
            self.scan_workers = max(1, min(int(data.get("scan_workers", self.scan_workers)), 32))
            self._sync_supermodel_from_native()
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    @staticmethod
    def _load_dir(data: dict, key: str, executable: Path | None) -> Path | None:
        """Lê um diretório persistido, usando a pasta do executável como fallback."""
        value = data.get(key)
        if value:
            return Path(value)
        return executable.parent if executable and executable.suffix.casefold() == ".exe" else None

    @staticmethod
    def _parse_retroarch_cfg(cfg_path: Path) -> dict[str, str]:
        """Lê o retroarch.cfg sem tentar reformatar ou modificar o arquivo nativo."""
        result: dict[str, str] = {}
        text = cfg_path.read_text(encoding="utf-8-sig", errors="replace")
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
                value = value[1:-1]
            result[key] = value
        return result

    @staticmethod
    def _resolve_retroarch_path(value: str, root: Path) -> Path | str:
        """Resolve caminhos nativos do RA, inclusive o marcador ':\\'."""
        value = value.strip()
        if not value or value == "default":
            return value
        if value.startswith(":\\") or value.startswith(":/"):
            return (root / value[2:].replace("\\", os.sep).replace("/", os.sep)).resolve()
        return Path(value).expanduser().resolve() if Path(value).is_absolute() else (root / value).resolve()

    def import_retroarch_config(self, executable: Path) -> dict[str, Path | str]:
        """Descobre a instalação pelo retroarch.exe e importa diretórios do retroarch.cfg."""
        executable = Path(executable).expanduser().resolve()
        if executable.name.casefold() != "retroarch.exe" or not executable.is_file():
            raise FileNotFoundError(f"Selecione o retroarch.exe válido: {executable}")
        root = executable.parent
        cfg = root / "retroarch.cfg"
        if not cfg.is_file():
            raise FileNotFoundError(f"retroarch.cfg não encontrado junto de {executable}")
        raw = self._parse_retroarch_cfg(cfg)
        native = {
            key: self._resolve_retroarch_path(raw[key], root)
            for key in raw
            if key in self.RETROARCH_DIRECTORY_KEYS
        }
        self.retroarch_path = executable
        self.retroarch_dir = root
        self.retroarch_config_file = cfg
        self.retroarch_native_paths = native
        config_dir = native.get("rgui_config_directory", root / "config")
        aliases = {
            "config": config_dir,
            "cores": native.get("libretro_directory", root / "cores"),
            "system": native.get("system_directory", root / "system"),
            "assets": native.get("assets_directory", root / "assets"),
            "shaders": native.get("video_shader_directory", root / "shaders"),
            "saves": native.get("savefile_directory", root / "saves"),
            "states": native.get("savestate_directory", root / "states"),
            "downloads": native.get("core_assets_directory", root / "downloads"),
        }
        for name, value in aliases.items():
            if isinstance(value, (Path, str)):
                self.emulator_paths["retroarch"][name] = value if isinstance(value, Path) else Path(value)
        self._derive_retroarch_core_layout()
        return native

    def set_retroarch_executable(self, executable: Path) -> dict[str, Path | str]:
        """Define o retroarch.exe como âncora da instalação e importa seu cfg."""
        return self.import_retroarch_config(executable)

    def _derive_retroarch_core_layout(self) -> None:
        """Calcula a árvore de configurações por core conforme a documentação Libretro."""
        config_root = self.emulator_paths.get("retroarch", {}).get("config") or self.retroarch_dir
        if config_root:
            config_root = Path(config_root)
            self.retroarch_core_config_dir = config_root
            self.retroarch_core_remap_dir = config_root / "remaps"
            self.retroarch_core_shader_dir = config_root

    def retroarch_core_directory(self, core_name: str) -> Path:
        """Retorna /config/<nome-do-core>."""
        if not self.retroarch_core_config_dir:
            raise RuntimeError("Diretório de configuração do RetroArch ainda não foi descoberto.")
        safe = Path(core_name).stem.replace("/", "_").replace("\\", "_")
        return self.retroarch_core_config_dir / safe

    def retroarch_core_paths(self, core_name: str) -> dict[str, Path]:
        """Retorna locais de override, remap, opções e presets do core."""
        core_dir = self.retroarch_core_directory(core_name)
        stem = Path(core_name).stem
        return {
            "config": core_dir,
            "override": core_dir / f"{stem}.cfg",
            "remaps": (self.retroarch_core_remap_dir or core_dir / "remaps") / stem,
            "options": core_dir / f"{stem}.opt",
            "shaders": core_dir,
        }

    def _sync_supermodel_from_native(self) -> None:
        """Importa RomsDirectory do Supermodel.ini quando disponível."""
        if not self.supermodel_dir:
            return
        try:
            native = SupermodelConfig(self.supermodel_dir).read_rom_directory()
        except (OSError, ValueError):
            native = None
        if native:
            self.emulator_paths["supermodel"]["roms"] = native

    def _sync_supermodel_to_native(self) -> None:
        """Publica o diretório de ROMs no Supermodel.ini quando a chave existe."""
        if not self.supermodel_dir:
            return
        roms = self.emulator_paths["supermodel"].get("roms")
        if not roms:
            return
        try:
            native = SupermodelConfig(self.supermodel_dir)
            if native.read_rom_directory() is not None:
                native.write_rom_directory(roms)
        except (OSError, ValueError):
            pass

    def get_emulator_path(self, emulator: str, name: str) -> Path | None:
        """Retorna um diretório de conteúdo persistido para um emulador."""
        return self.emulator_paths.get(emulator, {}).get(name)

    def set_emulator_path(self, emulator: str, name: str, path: Path | None) -> None:
        """Define um diretório de conteúdo de emulador e o mantém em memória."""
        self.emulator_paths.setdefault(emulator, {})[name] = Path(path) if path else None

    def get_flycast_rom_paths(self) -> list[Path]:
        """Retorna os diretórios de ROM do Flycast, no máximo quatro."""
        return list(self.flycast_rom_paths[:4])

    def set_flycast_rom_paths(self, paths: list[Path]) -> None:
        """Define até quatro diretórios de ROM do Flycast."""
        self.flycast_rom_paths = [Path(path) for path in paths if path][:4]
        self.emulator_paths["flycast"]["roms"] = self.flycast_rom_paths[0] if self.flycast_rom_paths else None

    def save(self):
        """Salva configurações de forma atômica."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if self.mame_dir:
            canonical_mame = self.mame_dir.expanduser() / "mame.exe"
            self.mame_path = canonical_mame if canonical_mame.is_file() else None
        self._sync_supermodel_to_native()
        payload = {
            "mame_path": str(self.mame_path) if self.mame_path else "", "flycast_path": str(self.flycast_path) if self.flycast_path else "", "supermodel_path": str(self.supermodel_path) if self.supermodel_path else "", "fbneo_path": str(self.fbneo_path) if self.fbneo_path else "", "retroarch_path": str(self.retroarch_path) if self.retroarch_path else "",
            "mame_dir": str(self.mame_dir) if self.mame_dir else "", "flycast_dir": str(self.flycast_dir) if self.flycast_dir else "", "supermodel_dir": str(self.supermodel_dir) if self.supermodel_dir else "", "fbneo_dir": str(self.fbneo_dir) if self.fbneo_dir else "", "retroarch_dir": str(self.retroarch_dir) if self.retroarch_dir else "",
            "mame_version": self.mame_version or "", "flycast_version": self.flycast_version or "", "supermodel_version": self.supermodel_version or "", "fbneo_version": self.fbneo_version or "", "retroarch_version": self.retroarch_version or "",
            "emulator_paths": {emulator: {name: str(path) if path else "" for name, path in paths.items()} for emulator, paths in self.emulator_paths.items()},
            "retroarch_native_paths": {key: str(value) if isinstance(value, Path) else value for key, value in self.retroarch_native_paths.items()},
            "retroarch_config_file": str(self.retroarch_config_file) if self.retroarch_config_file else "",
            "flycast_rom_paths": [str(path) for path in self.flycast_rom_paths[:4]],
            "chdman_path": str(self.chdman_path) if self.chdman_path else "", "ini_path": str(self.ini_path) if self.ini_path else "", "catver_path": str(self.catver_path) if self.catver_path else "",
            "source_dirs": [str(p) for p in self.source_dirs[:3]], "destination_dir": str(self.destination_dir) if self.destination_dir else "", "output_layout": self.output_layout,
            "cache_dir": str(self.cache_dir) if self.cache_dir else "", "cache_limit_mb": self.cache_limit_mb, "scan_workers": self.scan_workers,
        }
        tmp = self.CONFIG_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.CONFIG_FILE)
