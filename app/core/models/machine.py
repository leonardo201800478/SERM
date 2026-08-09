from dataclasses import dataclass, field
from typing import List, Optional
from app.core.models.rom import Rom

@dataclass
class Machine:
    id: Optional[int] = None
    mame_installation_id: int = 0
    name: str = ''
    description: str = ''
    year: str = ''
    manufacturer: str = ''
    sourcefile: str = ''
    cloneof: str = ''
    romof: str = ''
    sampleof: str = ''
    is_bios: bool = False
    is_device: bool = False
    is_mechanical: bool = False
    runnable: bool = True
    emulation_status: str = ''
    driver_status: str = ''
    savestate: bool = False
    requires_artwork: bool = False
    unofficial: bool = False
    nosoundhardware: bool = False
    incomplete: bool = False
    roms: List[Rom] = field(default_factory=list)