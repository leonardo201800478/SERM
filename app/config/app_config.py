import json
from pathlib import Path

class AppConfig:
    CONFIG_DIR = Path.home() / ".mame-set-builder"
    CONFIG_FILE = CONFIG_DIR / "config.json"

    def __init__(self):
        self.mame_path: Path = None
        self.ini_path: Path = None
        self.load()

    def load(self):
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get('mame_path'):
                        self.mame_path = Path(data['mame_path'])
                    if data.get('ini_path'):
                        self.ini_path = Path(data['ini_path'])
            except Exception:
                pass

    def save(self):
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'mame_path': str(self.mame_path) if self.mame_path else '',
                'ini_path': str(self.ini_path) if self.ini_path else ''
            }, f, indent=2)