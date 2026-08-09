import json
from pathlib import Path

class AppConfig:
    CONFIG_DIR = Path.home() / ".mame-set-builder"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    DATA_DIR = CONFIG_DIR / "data"

    def __init__(self):
        self.mame_path: Path = None
        self.ini_path: Path = None
        self.db_path: Path = self.DATA_DIR / "mame_set_builder.db"
        self.load()

    def load(self):
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("mame_path"):
                        self.mame_path = Path(data["mame_path"])
                    if data.get("ini_path"):
                        self.ini_path = Path(data["ini_path"])
                    if data.get("db_path"):
                        self.db_path = Path(data["db_path"])
            except Exception:
                pass

    def save(self):
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "mame_path": str(self.mame_path) if self.mame_path else "",
                "ini_path": str(self.ini_path) if self.ini_path else "",
                "db_path": str(self.db_path) if self.db_path else ""
            }, f, indent=2)