from dataclasses import dataclass
from typing import Optional

@dataclass
class MameInstallation:
    id: Optional[int] = None
    version: str = ''
    executable_path: str = ''
    executable_hash: str = ''
    detected_at: str = ''