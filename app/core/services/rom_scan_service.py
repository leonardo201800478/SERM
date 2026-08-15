from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, List

from app.core.models.scan_result import ScanResult
from app.mame.listxml_parser import iter_machines
from app.mame.rom_scanner import RomScanner


class RomScanService:
    def __init__(self, rom_paths: List[Path], *, workers: int | None = None):
        self.rom_paths = [Path(p) for p in rom_paths]
        self.scanner = RomScanner(self.rom_paths, workers=workers)

    def scan_machines(self, xml_path: Path, *, progress_callback: Callable[[int, int, str], None] | None = None) -> ScanResult:
        machines: list[dict] = []
        for machine in iter_machines(xml_path):
            machines.append({
                "name": machine.name,
                "description": machine.description,
                "cloneof": machine.cloneof,
                "roms": [
                    {"name": r.name, "size": r.size, "crc": r.crc, "sha1": r.sha1, "merge": r.merge}
                    for r in machine.roms
                ],
                "disks": [{"name": d.name, "sha1": d.sha1, "merge": d.merge} for d in machine.disks],
            })
        return self.scanner.scan_machines(machines, progress_callback=progress_callback)
