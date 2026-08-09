from dataclasses import dataclass
from typing import Optional

@dataclass
class Rom:
    id: Optional[int] = None
    machine_id: int = 0
    name: str = ''
    size: int = 0
    crc: str = ''
    sha1: str = ''
    merge: str = ''
    region: str = ''
    offset: int = 0
    status: str = ''
    optional: bool = False
    bios: str = ''