from pathlib import Path
from app.mame.ini_parser import MameIniParser

class IniService:
    def __init__(self, ini_path: Path):
        self.parser = MameIniParser(ini_path)
        self.parser.load()

    def get_rompath(self) -> str:
        return self.parser.get('rompath', '')

    def get_samplepath(self) -> str:
        return self.parser.get('samplepath', '')

    def get_artpath(self) -> str:
        return self.parser.get('artpath', '')

    def get_cfgpath(self) -> str:
        return self.parser.get('cfg_directory', '')

    def get_nvrampath(self) -> str:
        return self.parser.get('nvram_directory', '')

    def get_statepath(self) -> str:
        return self.parser.get('state_directory', '')

    def get_snappath(self) -> str:
        return self.parser.get('snapshot_directory', '')

    def get_diffpath(self) -> str:
        return self.parser.get('diff_directory', '')

    def get_inipath(self) -> str:
        return self.parser.get('inipath', '')

    def set_rompath(self, value: str):
        self.parser.set('rompath', value)

    def set_samplepath(self, value: str):
        self.parser.set('samplepath', value)

    def set_artpath(self, value: str):
        self.parser.set('artpath', value)

    def set_cfgpath(self, value: str):
        self.parser.set('cfg_directory', value)

    def set_nvrampath(self, value: str):
        self.parser.set('nvram_directory', value)

    def set_statepath(self, value: str):
        self.parser.set('state_directory', value)

    def set_snappath(self, value: str):
        self.parser.set('snapshot_directory', value)

    def set_diffpath(self, value: str):
        self.parser.set('diff_directory', value)

    def set_inipath(self, value: str):
        self.parser.set('inipath', value)

    def save(self):
        self.parser.save()