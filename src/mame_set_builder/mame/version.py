# src/mame_set_builder/mame/version.py
from dataclasses import dataclass
from .executable import MAMEExecutable

@dataclass
class MAMEVersion:
    major: int
    minor: int
    full: str

    @classmethod
    def from_executable(cls, exe: MAMEExecutable) -> "MAMEVersion":
        ver_str = exe.get_version()
        parts = ver_str.split('.')
        return cls(major=int(parts[0]), minor=int(parts[1]), full=ver_str)