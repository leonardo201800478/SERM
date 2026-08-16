"""Modelo de domínio para uma ROM individual de uma máquina MAME."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Rom:
    id: Optional[int] = None
    machine_id: int = 0
    name: str = ""
    size: int = 0
    crc: str = ""
    sha1: str = ""
    merge: str = ""
    region: str = ""
    offset: int = 0
    status: str = ""
    optional: bool = False
    bios: str = ""

    @property
    def is_bios_rom(self) -> bool:
        return bool(self.bios)

    @property
    def expected_hash(self) -> str:
        """CRC é priorizado por ser o identificador principal do MAME."""
        return self.crc or self.sha1

    def to_scan_dict(self) -> dict[str, Any]:
        """Formato consumido por ``RomScanner.scan_rom``."""
        return {
            "name": self.name,
            "size": self.size,
            "crc": (self.crc or "").lower(),
            "sha1": (self.sha1 or "").lower(),
            "merge": self.merge or None,
            "status": self.status or "good",
            "optional": self.optional,
            "bios": self.bios or None,
        }