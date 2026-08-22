import json
import os
from pathlib import Path


class AppConfig:
    """Configuração persistente do MAME Set Builder."""

    CONFIG_DIR = Path.home() / ".mame-set-builder"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    DB_DIR = PROJECT_ROOT / "data" / "database"
    DB_PATH = DB_DIR / "mame_set_builder.db"
    SCAN_DIR = DB_DIR / "scan"

    def __init__(self):
        # Executáveis dos emuladores. Caminhos opcionais; a ausência significa
        # que o emulador ainda não foi configurado pelo usuário.
        self.mame_path: Path | None = None
        self.flycast_path: Path | None = None
        self.supermodel_path: Path | None = None
        self.fbneo_path: Path | None = None

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
        """Garante os diretórios persistentes do aplicativo, incluindo manifests de scan."""
        self.DB_DIR.mkdir(parents=True, exist_ok=True)
        self.SCAN_DIR.mkdir(parents=True, exist_ok=True)

    def load(self):
        """Carrega configurações sem interromper a aplicação por arquivo inválido."""
        if not self.CONFIG_FILE.exists():
            return
        try:
            data = json.loads(self.CONFIG_FILE.read_text(encoding="utf-8"))
            self.mame_path = Path(data["mame_path"]) if data.get("mame_path") else None
            self.flycast_path = Path(data["flycast_path"]) if data.get("flycast_path") else None
            self.supermodel_path = Path(data["supermodel_path"]) if data.get("supermodel_path") else None
            self.fbneo_path = Path(data["fbneo_path"]) if data.get("fbneo_path") else None
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

    def save(self):
        """Salva as configurações de forma atômica."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "mame_path": str(self.mame_path) if self.mame_path else "",
            "flycast_path": str(self.flycast_path) if self.flycast_path else "",
            "supermodel_path": str(self.supermodel_path) if self.supermodel_path else "",
            "fbneo_path": str(self.fbneo_path) if self.fbneo_path else "",
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
