from app.mame.ini_parser import MameIniParser
from pathlib import Path

class IniService:
    def __init__(self, ini_path: Path):
        self.parser = MameIniParser(ini_path)
        self.parser.load()

    def get_rompath(self) -> str:
        return self.parser.get('rompath', '')

    def set_rompath(self, value: str):
        self.parser.set('rompath', value)

    def get_samplepath(self) -> str:
        return self.parser.get('samplepath', '')

    def set_samplepath(self, value: str):
        self.parser.set('samplepath', value)

    def get_artpath(self) -> str:
        return self.parser.get('artpath', '')

    def set_artpath(self, value: str):
        self.parser.set('artpath', value)

    def get_cfgpath(self) -> str:
        return self.parser.get('cfg_directory', '')

    def set_cfgpath(self, value: str):
        self.parser.set('cfg_directory', value)

    def save(self):
        self.parser.save()