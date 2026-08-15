# app/core/services/rom_scan_service.py
from pathlib import Path
from typing import List

from app.core.models.scan_result import ScanResult
from app.mame.rom_scanner import RomScanner

class RomScanService:
    def __init__(self, rom_paths: List[Path]):
        self.rom_paths = rom_paths
        self.scanner = RomScanner(rom_paths)

    def scan_machines(self, xml_path: Path) -> ScanResult:
        import xml.etree.ElementTree as ET

        machines = []
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for machine_elem in root.findall("machine"):
            machine = {
                'name': machine_elem.get('name', ''),
                'description': '',
                'cloneof': machine_elem.get('cloneof', ''),
                'roms': [],
                'disks': []
            }
            desc_elem = machine_elem.find("description")
            if desc_elem is not None:
                machine['description'] = desc_elem.text or ''
            for rom_elem in machine_elem.findall("rom"):
                machine['roms'].append({
                    'name': rom_elem.get('name', ''),
                    'size': int(rom_elem.get('size', 0)),
                    'crc': rom_elem.get('crc', ''),
                    'sha1': rom_elem.get('sha1', ''),
                    'merge': rom_elem.get('merge', ''),
                })
            for disk_elem in machine_elem.findall("disk"):
                machine['disks'].append({
                    'name': disk_elem.get('name', ''),
                    'sha1': disk_elem.get('sha1', ''),
                })
            machines.append(machine)

        return self.scanner.scan_machines(machines)