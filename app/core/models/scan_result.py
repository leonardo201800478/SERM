# app/core/models/scan_result.py
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


class ScanStatus(Enum):
    NOT_SCANNED = "not_scanned"
    MISSING = "missing"
    OK = "ok"
    FIXABLE = "fixable"
    UNAVAILABLE = "unavailable"
    CORRUPTED = "corrupted"

    @property
    def color(self) -> str:
        colors = {
            ScanStatus.NOT_SCANNED: "#808080",
            ScanStatus.MISSING: "#808080",
            ScanStatus.OK: "#00AA00",
            ScanStatus.FIXABLE: "#FFAA00",
            ScanStatus.UNAVAILABLE: "#FF0000",
            ScanStatus.CORRUPTED: "#000000",
        }
        return colors.get(self, "#808080")

    @property
    def label(self) -> str:
        labels = {
            ScanStatus.NOT_SCANNED: "Não escaneado",
            ScanStatus.MISSING: "Ausente",
            ScanStatus.OK: "OK",
            ScanStatus.FIXABLE: "Corrigível",
            ScanStatus.UNAVAILABLE: "Indisponível",
            ScanStatus.CORRUPTED: "Corrompido",
        }
        return labels.get(self, "Desconhecido")


@dataclass
class RomFile:
    name: str
    size: int
    crc: str
    sha1: Optional[str] = None
    merge: Optional[str] = None
    region: Optional[str] = None
    status: ScanStatus = ScanStatus.NOT_SCANNED
    found_in: Optional[Path] = None
    expected_path: Optional[Path] = None
    actual_crc: Optional[str] = None
    actual_size: Optional[int] = None

    def is_valid(self) -> bool:
        return (self.status == ScanStatus.OK and
                self.crc == self.actual_crc and
                self.size == self.actual_size)


@dataclass
class MachineScanResult:
    name: str
    description: str
    cloneof: Optional[str] = None
    status: ScanStatus = ScanStatus.NOT_SCANNED
    roms: List[RomFile] = field(default_factory=list)
    total_size: int = 0
    children: List['MachineScanResult'] = field(default_factory=list)
    icon_path: Optional[Path] = None

    def get_status_color(self) -> str:
        return self.status.color

    def update_status(self):
        if not self.roms:
            self.status = ScanStatus.NOT_SCANNED
            return
        statuses = [r.status for r in self.roms]
        if all(s == ScanStatus.OK for s in statuses):
            self.status = ScanStatus.OK
        elif any(s == ScanStatus.CORRUPTED for s in statuses):
            self.status = ScanStatus.CORRUPTED
        elif any(s == ScanStatus.UNAVAILABLE for s in statuses):
            self.status = ScanStatus.UNAVAILABLE
        elif any(s == ScanStatus.FIXABLE for s in statuses):
            self.status = ScanStatus.FIXABLE
        elif all(s == ScanStatus.MISSING for s in statuses):
            self.status = ScanStatus.MISSING
        else:
            self.status = ScanStatus.NOT_SCANNED


@dataclass
class ScanResult:
    version: str
    total_machines: int = 0
    machines: List[MachineScanResult] = field(default_factory=list)
    scan_time: Optional[float] = None
    roms_total: int = 0
    bios_total: int = 0
    devices_total: int = 0
    chds_total: int = 0
    ok_count: int = 0
    fixable_count: int = 0
    missing_count: int = 0
    unavailable_count: int = 0
    corrupted_count: int = 0

    def update_summary(self):
        self.roms_total = 0
        self.bios_total = 0
        self.devices_total = 0
        self.chds_total = 0
        self.ok_count = 0
        self.fixable_count = 0
        self.missing_count = 0
        self.unavailable_count = 0
        self.corrupted_count = 0
        for machine in self.machines:
            self.roms_total += 1
            if machine.status == ScanStatus.OK:
                self.ok_count += 1
            elif machine.status == ScanStatus.FIXABLE:
                self.fixable_count += 1
            elif machine.status == ScanStatus.MISSING:
                self.missing_count += 1
            elif machine.status == ScanStatus.UNAVAILABLE:
                self.unavailable_count += 1
            elif machine.status == ScanStatus.CORRUPTED:
                self.corrupted_count += 1