from dataclasses import dataclass


@dataclass
class MameInstallation:
    id: int | None = None
    version: str = ''
    executable_path: str = ''
    executable_hash: str = ''
    detected_at: str = ''