from dataclasses import dataclass
from typing import Optional

@dataclass
class Disk:
    id: Optional[int] = None
    machine_id: int = 0
    name: str = ''
    sha1: str = ''
    merge: str = ''
    region: str = ''
    index: int = 0
    writable: bool = False
    status: str = 'good'
    optional: bool = False