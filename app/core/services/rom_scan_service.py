from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, List

from app.core.models.scan_result import ScanResult
from app.mame.listxml_parser import iter_machines
from app.mame.persistent_rom_scanner import PersistentRomScanner


class RomScanService:
    """Orquestra o scan usando o índice persistente de fontes ROM.

    O índice SQLite é reutilizado entre execuções. Assim, a busca alternativa
    por uma ROM existente em outro ZIP deixa de reconstruir um índice completo
    em memória toda vez que o scanner encontra uma ROM ausente.
    """

    def __init__(self, rom_paths: List[Path], *, workers: int | None = None):
        self.rom_paths = [Path(p) for p in rom_paths]
        self.scanner = PersistentRomScanner(
            self.rom_paths,
            workers=workers,
            enable_alternate_search=True,
        )

    def scan_machines(
        self,
        xml_path: Path,
        *,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> ScanResult:
        """Lê o LISTXML e executa o scan físico das máquinas selecionadas."""
        machines: list[dict] = []
        for machine in iter_machines(xml_path):
            machines.append({
                "name": machine.name,
                "description": machine.description,
                "cloneof": machine.cloneof,
                "roms": [
                    {
                        "name": r.name,
                        "size": r.size,
                        "crc": r.crc,
                        "sha1": r.sha1,
                        "merge": r.merge,
                    }
                    for r in machine.roms
                ],
                "disks": [
                    {
                        "name": d.name,
                        "sha1": d.sha1,
                        "merge": d.merge,
                    }
                    for d in machine.disks
                ],
            })
        return self.scanner.scan_machines(
            machines,
            progress_callback=progress_callback,
        )
