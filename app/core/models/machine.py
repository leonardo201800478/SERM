"""Modelo de domínio para uma máquina MAME."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.models.disk import Disk
from app.core.models.rom import Rom


@dataclass
class Machine:
    id: int | None = None
    mame_installation_id: int = 0
    name: str = ""
    description: str = ""
    year: str = ""
    manufacturer: str = ""
    sourcefile: str = ""
    cloneof: str = ""
    romof: str = ""
    sampleof: str = ""
    is_bios: bool = False
    is_device: bool = False
    is_mechanical: bool = False
    runnable: bool = True
    emulation_status: str = ""
    driver_status: str = ""
    savestate: bool = False
    requires_artwork: bool = False
    unofficial: bool = False
    nosoundhardware: bool = False
    incomplete: bool = False
    roms: list[Rom] = field(default_factory=list)
    disks: list[Disk] = field(default_factory=list)

    @property
    def is_clone(self) -> bool:
        return bool(self.cloneof)

    def to_scan_dict(self) -> dict[str, Any]:
        """Representação consumida por ``RomScanner``/``RomScanService``.

        Mantém um único formato tanto para objetos ``Machine`` vindos do
        parser streaming quanto para dicionários lidos diretamente de um
        LISTXML já filtrado em disco (ver ``scan_roms_tab.py``).
        """
        return {
            "name": self.name,
            "description": self.description,
            "cloneof": self.cloneof or None,
            "roms": [rom.to_scan_dict() for rom in self.roms],
            "disks": [disk.to_scan_dict() for disk in self.disks],
        }