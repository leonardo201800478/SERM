# app/mame/rom_scanner.py
import zipfile
import zlib
from pathlib import Path
from typing import List, Optional
import logging

from app.core.models.scan_result import ScanResult, MachineScanResult, RomFile, ScanStatus

logger = logging.getLogger(__name__)

class RomScanner:
    def __init__(self, rom_paths: List[Path]):
        self.rom_paths = [Path(p) for p in rom_paths if Path(p).exists()]
        self._cache = {}

    def scan_machines(self, machines: List[dict]) -> ScanResult:
        result = ScanResult(version="unknown")
        for machine_data in machines:
            machine_result = self._scan_single_machine(machine_data)
            result.machines.append(machine_result)
        result.update_summary()
        return result

    def _scan_single_machine(self, machine_data: dict) -> MachineScanResult:
        name = machine_data.get('name', '')
        description = machine_data.get('description', '')
        cloneof = machine_data.get('cloneof')

        machine_result = MachineScanResult(name=name, description=description, cloneof=cloneof)

        for rom_info in machine_data.get('roms', []):
            rom_file = self._scan_rom(rom_info, name)
            machine_result.roms.append(rom_file)

        machine_result.update_status()
        machine_result.total_size = sum(r.size for r in machine_result.roms if r.status == ScanStatus.OK)
        return machine_result

    def _scan_rom(self, rom_info: dict, machine_name: str) -> RomFile:
        rom_name = rom_info.get('name', '')
        expected_size = rom_info.get('size', 0)
        expected_crc = rom_info.get('crc', '').lower()
        expected_sha1 = rom_info.get('sha1', '').lower()
        merge = rom_info.get('merge')

        rom_file = RomFile(
            name=rom_name,
            size=expected_size,
            crc=expected_crc,
            sha1=expected_sha1 if expected_sha1 else None,
            merge=merge,
            status=ScanStatus.MISSING
        )

        for rom_path in self.rom_paths:
            # Tenta no ZIP da máquina
            zip_path = rom_path / f"{machine_name}.zip"
            if zip_path.exists() and self._check_in_zip(zip_path, rom_name, rom_file):
                return rom_file

            # Tenta no ZIP de merge (ROM compartilhada)
            if merge:
                merge_zip = rom_path / f"{merge}.zip"
                if merge_zip.exists() and self._check_in_zip(merge_zip, rom_name, rom_file):
                    return rom_file

            # Tenta como arquivo avulso
            file_path = rom_path / rom_name
            if file_path.exists() and self._check_file(file_path, rom_file):
                return rom_file

        return rom_file

    def _check_in_zip(self, zip_path: Path, rom_name: str, rom_file: RomFile) -> bool:
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                if rom_name in zf.namelist():
                    info = zf.getinfo(rom_name)
                    actual_size = info.file_size
                    with zf.open(rom_name) as f:
                        data = f.read()
                        actual_crc = format(zlib.crc32(data) & 0xFFFFFFFF, '08x')

                    rom_file.found_in = zip_path
                    rom_file.actual_size = actual_size
                    rom_file.actual_crc = actual_crc

                    if actual_size == rom_file.size and actual_crc == rom_file.crc:
                        rom_file.status = ScanStatus.OK
                    elif actual_crc == rom_file.crc:
                        rom_file.status = ScanStatus.FIXABLE
                    else:
                        rom_file.status = ScanStatus.CORRUPTED
                    return True
        except Exception as e:
            logger.warning(f"Erro ao ler ZIP {zip_path}: {e}")
        return False

    def _check_file(self, file_path: Path, rom_file: RomFile) -> bool:
        try:
            actual_size = file_path.stat().st_size
            with open(file_path, 'rb') as f:
                data = f.read()
                actual_crc = format(zlib.crc32(data) & 0xFFFFFFFF, '08x')

            rom_file.found_in = file_path.parent
            rom_file.actual_size = actual_size
            rom_file.actual_crc = actual_crc

            if actual_size == rom_file.size and actual_crc == rom_file.crc:
                rom_file.status = ScanStatus.OK
            elif actual_crc == rom_file.crc:
                rom_file.status = ScanStatus.FIXABLE
            else:
                rom_file.status = ScanStatus.CORRUPTED
            return True
        except Exception as e:
            logger.warning(f"Erro ao ler arquivo {file_path}: {e}")
        return False