"""Modelo de domínio para um disco/CHD de uma máquina MAME."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Disk:
    id: Optional[int] = None
    machine_id: int = 0
    name: str = ""
    sha1: str = ""
    merge: str = ""
    region: str = ""
    index: int = 0
    writable: bool = False
    status: str = "good"
    optional: bool = False
    size: int = 0  # tamanho físico — o -listxml não fornece; ver chd_scanner.py

    @property
    def disk_index(self) -> int:
        """Alias para a coluna ``disk_index`` do schema atual (o
        LISTXML/parser usa ``index``; o banco usa ``disk_index``)."""
        return self.index

    @disk_index.setter
    def disk_index(self, value: int) -> None:
        self.index = value

    def to_scan_dict(self) -> dict[str, Any]:
        """Formato consumido por ``RomScanner.scan_chd``."""
        return {
            "name": self.name,
            "sha1": (self.sha1 or "").lower(),
            "merge": self.merge or None,
            "region": self.region or None,
            "index": self.index,
            "size": self.size,
        }