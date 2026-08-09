"""
Gerenciamento de configurações do MAME Set Builder (JSON).
"""

import json
from pathlib import Path
from typing import Dict, Any

class Settings:
    CONFIG_FILE = "mame_set_builder_config.json"

    @classmethod
    def get_config_path(cls) -> Path:
        return Path(__file__).parent.parent.parent / cls.CONFIG_FILE

    @classmethod
    def load(cls) -> Dict[str, Any]:
        path = cls.get_config_path()
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return cls.defaults()

    @classmethod
    def defaults(cls) -> Dict[str, Any]:
        return {
            "mame_executable": "",
            "mame_version": "",
            "rom_paths": [],
            "sample_path": "",
            "artwork_path": "",
            "software_path": "",
            "fullset_path": "",
            "folders_path": "",
        }

    @classmethod
    def save(cls, config: Dict[str, Any]) -> None:
        path = cls.get_config_path()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)