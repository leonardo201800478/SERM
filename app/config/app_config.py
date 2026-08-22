import json
import os
from pathlib import Path


class AppConfig:
    """Configuração persistente do MAME Set Builder.

    ``*_dir`` é a fonte canônica da instalação de cada emulador.
    ``*_path`` representa somente o executável efetivamente instalado.
    Pacotes baixados (.exe/.7z/.zip) nunca devem ser persistidos como executáveis.
    """

    CONFIG_DIR = Path.home() / ".mame-set-builder"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    DB_DIR = PROJECT_ROOT / "data" / "database"
    DB_PATH = DB_DIR / "mame_set_builder.db"
    SCAN_DIR = DB_DIR / "scan"

    def __init__(self):
        self.mame_path: Path | None = None
        self.flycast_path: Path | None = None
        self.supermodel_path: Path | None = None
        self.fbneo_path: Path | None = None

        self.mame_dir: Path | None = None
        self.flycast_dir: Path | None = None
        self.supermodel_dir: Path | None = None
        self.fbneo_dir: Path | None = None

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

            # O diretório configurado é a autoridade. Se houver mame.exe nele,
            # qualquer caminho antigo (inclusive mame0289b_x64.exe) é descartado.
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

    def save(self):
        """Salva configurações de forma atômica, mantendo apenas executáveis válidos."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        if self.mame_dir:
            canonical_mame = self.mame_dir.expanduser() / "mame.exe"
            self.mame_path = canonical_mame if canonical_mame.is_file() else None

        payload = {
            "mame_path": str(self.mame_path) if self.mame_path else "",
            "flycast_path": str(self.flycast_path) if self.flycast_path else "",
            "supermodel_path": str(self.supermodel_path) if self.supermodel_path else "",
            "fbneo_path": str(self.fbneo_path) if self.fbneo_path else "",
            "mame_dir": str(self.mame_dir) if self.mame_dir else "",
            "flycast_dir": str(self.flycast_dir) if self.flycast_dir else "",
            "supermodel_dir": str(self.supermodel_dir) if self.supermodel_dir else "",
            "fbneo_dir": str(self.fbneo_dir) if self.fbneo_dir else "",
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
