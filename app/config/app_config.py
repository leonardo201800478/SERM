# app/config/app_config.py
import json
from pathlib import Path

class AppConfig:
    CONFIG_DIR = Path.home() / ".mame-set-builder"
    CONFIG_FILE = CONFIG_DIR / "config.json"

    # Raiz do projeto: sobe 2 níveis a partir do diretório deste arquivo
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # ajustado para 3 níveis
    DB_DIR = PROJECT_ROOT / "data" / "database"
    DB_PATH = DB_DIR / "mame_set_builder.db"

    def __init__(self):
        self.mame_path: Path = None
        self.ini_path: Path = None
        self.db_path: Path = self.DB_PATH
        self._ensure_directories()
        self.load()

    def _ensure_directories(self):
        self.DB_DIR.mkdir(parents=True, exist_ok=True)

    def load(self):
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("mame_path"):
                        self.mame_path = Path(data["mame_path"])
                    if data.get("ini_path"):
                        self.ini_path = Path(data["ini_path"])
            except Exception:
                pass

    def save(self):
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "mame_path": str(self.mame_path) if self.mame_path else "",
                "ini_path": str(self.ini_path) if self.ini_path else ""
            }, f, indent=2)