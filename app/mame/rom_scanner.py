# app/mame/rom_scanner.py
import zipfile
import zlib
from pathlib import Path
from typing import List, Optional
import logging

from app.core.models.scan_result import ScanResult, MachineScanResult, RomFile, ScanStatus

logger = logging.getLogger(__name__)


class RomScanner:
    def __init__(self, rom_paths: List[Path], log_emitter=None):
        self.rom_paths = [Path(p) for p in rom_paths if Path(p).exists()]
        self._cache = {}
        self.log_emitter = log_emitter  # Objeto com métodos log_line.emit() e progress.emit()

    def _log(self, message: str):
        """Envia mensagem para o emissor de log, se existir."""
        if self.log_emitter and hasattr(self.log_emitter, 'log_line'):
            self.log_emitter.log_line.emit(message)
        else:
            logger.info(message)

    def _progress(self, value: int, message: str):
        """Atualiza progresso."""
        if self.log_emitter and hasattr(self.log_emitter, 'progress'):
            self.log_emitter.progress.emit(value, message)

    def scan_machines(self, machines: List[dict]) -> ScanResult:
        total = len(machines)
        self._log(f"Iniciando escaneamento de {total} máquinas.")
        result = ScanResult(version="unknown")

        for idx, machine_data in enumerate(machines):
            if idx % 10 == 0:
                self._progress(int(idx / total * 100), f"Escaneando {idx+1}/{total}...")
            self._log(f"🔄 Escaneando {machine_data.get('name', 'unknown')}...")
            machine_result = self._scan_single_machine(machine_data)
            result.machines.append(machine_result)
            self._log(f"   ✅ {machine_result.name}: {machine_result.status.label}")

        self._progress(100, "Finalizando...")
        result.update_summary()
        self._log("Escaneamento concluído.")
        return result

    def _scan_single_machine(self, machine_data: dict) -> MachineScanResult:
        name = machine_data.get('name', '')
        description = machine_data.get('description', '')
        cloneof = machine_data.get('cloneof')

        machine_result = MachineScanResult(name=name, description=description, cloneof=cloneof)

        for rom_info in machine_data.get('roms', []):
            rom_file = self._scan_rom(rom_info, name)
            machine_result.roms.append(rom_file)
            status_symbol = {
                ScanStatus.OK: "✅",
                ScanStatus.FIXABLE: "🟡",
                ScanStatus.MISSING: "❌",
                ScanStatus.UNAVAILABLE: "🔴",
                ScanStatus.CORRUPTED: "⬛",
            }.get(rom_file.status, "❓")
            self._log(f"   {status_symbol} {rom_file.name}: {rom_file.status.label}")

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

        found = False
        for rom_path in self.rom_paths:
            # Tenta no ZIP da máquina
            zip_path = rom_path / f"{machine_name}.zip"
            if zip_path.exists():
                if self._check_in_zip(zip_path, rom_name, rom_file):
                    found = True
                    break

            # Tenta no ZIP de merge (ROM compartilhada)
            if merge:
                merge_zip = rom_path / f"{merge}.zip"
                if merge_zip.exists():
                    if self._check_in_zip(merge_zip, rom_name, rom_file):
                        found = True
                        break

            # Tenta como arquivo avulso
            file_path = rom_path / rom_name
            if file_path.exists():
                if self._check_file(file_path, rom_file):
                    found = True
                    break

        if not found:
            rom_file.status = ScanStatus.MISSING
            if rom_file.merge:
                self._log(f"   ❌ {rom_name} ausente (merge: {rom_file.merge})")
            else:
                self._log(f"   ❌ {rom_name} ausente")

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
            self._log(f"   ⚠️ Erro ao ler ZIP {zip_path}: {e}")
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
            self._log(f"   ⚠️ Erro ao ler arquivo {file_path}: {e}")
        return False