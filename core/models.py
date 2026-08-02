# core/models.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class Machine:
    name: str
    description: Optional[str] = None
    year: Optional[str] = None
    manufacturer: Optional[str] = None
    cloneof: Optional[str] = None
    working: bool = False
    ismechanical: bool = False
    isdevice: bool = False
    # Novos campos vindos dos .ini
    category: Optional[str] = None
    genre: Optional[str] = None
    genre_ows: Optional[str] = None
    machine_category: Optional[str] = None
    machine_type: Optional[str] = None
    players: Optional[str] = None
    resolution: Optional[str] = None
    version: Optional[str] = None
    working_arcade: Optional[bool] = None