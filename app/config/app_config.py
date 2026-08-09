import json
from pathlib import Path

class AppConfig:
    CONFIG_DIR = Path.home() / ".mame-set-builder"
    CONFIG_FILE = CONFIG_DIR / "config.json"

    def __init__(self):
        self.mame_path: Path = None
        self.load()

    def load(self):
        if self.CONFIG_FILE.exists():
            with open(self.CONFIG_FILE, 'r') as f:
                data = json.load(f)
                path_str = data.get('mame_path')
                if path_str:
                    self.mame_path = Path(path_str)

    def save(self):
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.CONFIG_FILE, 'w') as f:
            json.dump({'mame_path': str(self.mame_path) if self.mame_path else ''}, f)