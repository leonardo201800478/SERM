import json
import os
from pathlib import Path

from app.emulators.supermodel_config import SupermodelConfig


class AppConfig:
    """Configuração persistente do ARCADE MANAGER.

    ``*_dir`` é a fonte canônica da instalação de cada emulador.
    ``*_path`` representa somente o executável efetivamente instalado.
    ``*_version`` guarda a última versão confirmada pela instalação/atualização.
    ``emulator_paths`` guarda diretórios de conteúdo compartilhados pela GUI,
    catálogo e futuras rotinas de execução/reconstrução.

    Para o Supermodel, o diretório de ROMs é sincronizado com a configuração
    nativa ``RomsDirectory`` do ``Config/Supermodel.ini``.
    """

    CONFIG_DIR = Path.home() / ".mame-set-builder"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    DB_DIR = PROJECT_ROOT / "data" / "database"
    DB_PATH = DB_DIR / "mame_set_builder.db"
    SCAN_DIR = DB_DIR / "scan"

    EMULATOR_PATH_DEFAULTS = {
        "flycast": {
            "roms": "roms", "bios": "data", "vmu": "data", "saves": "data",
            "states": "data", "textures": "data", "boxart": "data", "cheats": "cheats",
        },
        "supermodel": {
            "roms": "ROMs", "config": "Config", "nvram": "NVRAM", "saves": "Saves", "assets": "Assets",
        },
        "fbneo": {
            "roms": "roms",
            "neocd": "neocdiso",
            "previews": "support/previews", "titles": "support/titles", "cheats": "support/cheats",
            "hiscore": "support/hiscores", "samples": "support/samples", "hdd": "support/hdd",
            "ips": "support/ips", "romdata": "support/romdata", "icons": "support/icons",
            "neocd_covers": "support/neocdz", "neocd_previews": "support/neocdzpreviews",
            "blend": "support/blend", "select": "support/select", "versus": "support/versus",
            "howto": "support/howto", "scores": "support/scores", "bosses": "support/bosses",
            "gameover": "support/gameover", "flyers": "support/flyers", "marquees": "support/marquees",
            "controls": "support/cpanel", "cabinets": "support/cabinets", "pcbs": "support/pcbs",
            "history": "support/history", "commands": "support/commands", "eeprom": "config/games",
        },
    }

    def __init__(self):
        self.mame_path: Path | None = None
        self.flycast_path: Path | None = None
        self.supermodel_path: Path | None = None
        self.fbneo_path: Path | None = None
        self.mame_dir: Path | None = None
        self.flycast_dir: Path | None = None
        self.supermodel_dir: Path | None = None
        self.fbneo_dir: Path | None = None
        self.mame_version: str | None = None
        self.flycast_version: str | None = None
        self.supermodel_version: str | None = None
        self.fbneo_version: str | None = None
        self.emulator_paths: dict[str, dict[str, Path | None]] = {
            emulator: {name: None for name in paths}
            for emulator, paths in self.EMULATOR_PATH_DEFAULTS.items()
        }
        self.flycast_rom_paths: list[Path] = []
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
        """Carrega configurações e saneia caminhos de executáveis antigos."""
        if not self.CONFIG_FILE.exists():
            return
        try:
            data = json.loads(self.CONFIG_FILE.read_text(encoding="utf-8"))
            self.mame_path = Path(data["mame_path"]) if data.get("mame_path") else None
            self.flycast_path = Path(data["flycast_path"]) if data.get("flycast_path") else None
            self.supermodel_path = Path(data["supermodel_path"]) if data.get("supermodel_path") else None
            self.fbneo_path = Path(data["fbneo_path"]) if data.get("fbneo_path") else None
            self.mame_dir = self._load_dir(data, "mame_dir", self.mame_path)
            self.flycast_dir = self._load_dir(data, "flycast_dir", self.flycast_path)
            self.supermodel_dir = self._load_dir(data, "supermodel_dir", self.supermodel_path)
            self.fbneo_dir = self._load_dir(data, "fbneo_dir", self.fbneo_path)
            self.mame_version = data.get("mame_version") or None
            self.flycast_version = data.get("flycast_version") or None
            self.supermodel_version = data.get("supermodel_version") or None
            self.fbneo_version = data.get("fbneo_version") or None

            persisted_paths = data.get("emulator_paths", {})
            for emulator, defaults in self.EMULATOR_PATH_DEFAULTS.items():
                stored = persisted_paths.get(emulator, {})
                for name in defaults:
                    value = stored.get(name)
                    self.emulator_paths[emulator][name] = Path(value) if value else None

            stored_flycast_roms = data.get("flycast_rom_paths")
            if isinstance(stored_flycast_roms, list):
                self.flycast_rom_paths = [Path(value) for value in stored_flycast_roms if value][:4]
            elif isinstance(stored_flycast_roms, str) and stored_flycast_roms.strip():
                self.flycast_rom_paths = [Path(value.strip()) for value in stored_flycast_roms.split(";") if value.strip()][:4]
            else:
                legacy_rom = self.emulator_paths.get("flycast", {}).get("roms")
                self.flycast_rom_paths = [legacy_rom] if legacy_rom else []

            self._sync_supermodel_from_native()

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
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    @staticmethod
    def _load_dir(data: dict, key: str, executable: Path | None) -> Path | None:
        """Lê um diretório persistido, usando a pasta do executável como fallback."""
        value = data.get(key)
        if value:
            return Path(value)
        if executable and executable.suffix.casefold() == ".exe":
            return executable.parent
        return None

    def _sync_supermodel_from_native(self) -> None:
        """Importa RomsDirectory do Supermodel.ini quando disponível."""
        if not self.supermodel_dir:
            return
        try:
            native = SupermodelConfig(self.supermodel_dir).read_rom_directory()
        except (OSError, ValueError):
            native = None
        if native:
            self.emulator_paths.setdefault("supermodel", {})["roms"] = native

    def _sync_supermodel_to_native(self) -> None:
        """Publica o diretório de ROMs no Supermodel.ini."""
        if not self.supermodel_dir:
            return
        roms = self.emulator_paths.get("supermodel", {}).get("roms")
        if not roms:
            return
        try:
            SupermodelConfig(self.supermodel_dir).write_rom_directory(roms)
        except (OSError, ValueError):
            # Falha no arquivo nativo não deve impedir o restante da
            # configuração do aplicativo de ser persistida.
            pass

    def get_emulator_path(self, emulator: str, name: str) -> Path | None:
        """Retorna um diretório de conteúdo persistido para um emulador."""
        return self.emulator_paths.get(emulator, {}).get(name)

    def set_emulator_path(self, emulator: str, name: str, path: Path | None) -> None:
        """Define um diretório de conteúdo de emulador e o mantém em memória."""
        if emulator not in self.emulator_paths:
            self.emulator_paths[emulator] = {}
        self.emulator_paths[emulator][name] = Path(path) if path else None

    def get_flycast_rom_paths(self) -> list[Path]:
        """Retorna os diretórios de ROM do Flycast, no máximo quatro."""
        return list(self.flycast_rom_paths[:4])

    def set_flycast_rom_paths(self, paths: list[Path]) -> None:
        """Define até quatro diretórios de ROM do Flycast."""
        self.flycast_rom_paths = [Path(path) for path in paths if path][:4]
        self.emulator_paths.setdefault("flycast", {})["roms"] = self.flycast_rom_paths[0] if self.flycast_rom_paths else None

    def save(self):
        """Salva configurações de forma atômica."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if self.mame_dir:
            canonical_mame = self.mame_dir.expanduser() / "mame.exe"
            self.mame_path = canonical_mame if canonical_mame.is_file() else None
        self._sync_supermodel_to_native()
        payload = {
            "mame_path": str(self.mame_path) if self.mame_path else "",
            "flycast_path": str(self.flycast_path) if self.flycast_path else "",
            "supermodel_path": str(self.supermodel_path) if self.supermodel_path else "",
            "fbneo_path": str(self.fbneo_path) if self.fbneo_path else "",
            "mame_dir": str(self.mame_dir) if self.mame_dir else "",
            "flycast_dir": str(self.flycast_dir) if self.flycast_dir else "",
            "supermodel_dir": str(self.supermodel_dir) if self.supermodel_dir else "",
            "fbneo_dir": str(self.fbneo_dir) if self.fbneo_dir else "",
            "mame_version": self.mame_version or "",
            "flycast_version": self.flycast_version or "",
            "supermodel_version": self.supermodel_version or "",
            "fbneo_version": self.fbneo_version or "",
            "emulator_paths": {
                emulator: {name: str(path) if path else "" for name, path in paths.items()}
                for emulator, paths in self.emulator_paths.items()
            },
            "flycast_rom_paths": [str(path) for path in self.flycast_rom_paths[:4]],
            "chdman_path": str(self.chdman_path) if self.chdman_path else "",
            "ini_path": str(self.ini_path) if self.ini_path else "",
            "catver_path": str(self.catver_path) if self.catver_path else "",
            "source_dirs": [str(p) for p in self.source_dirs[:3]],
            "destination_dir": str(self.destination_dir) if self.destination_dir else "",
            "output_layout": self.output_layout,
            "cache_dir": str(self.cache_dir) if self.cache_dir else "",
            "cache_limit_mb": self.cache_limit_mb,
            "scan_workers": self.scan_workers,
        }
        tmp = self.CONFIG_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.CONFIG_FILE)
