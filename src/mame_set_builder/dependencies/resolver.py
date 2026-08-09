import sqlite3
import logging
from typing import List, Set, Dict, Any

from ..domain.manifest import FileRequirement, FileType, SetManifest
from .clone_resolver import CloneResolver
from .bios_resolver import BiosResolver
from .device_resolver import DeviceResolver
from .rom_resolver import RomResolver
from .chd_resolver import ChdResolver
from .sample_resolver import SampleResolver

logger = logging.getLogger(__name__)

class DependencyResolver:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.clone_resolver = CloneResolver(conn)
        self.bios_resolver = BiosResolver(conn)
        self.device_resolver = DeviceResolver(conn)
        self.rom_resolver = RomResolver(conn)
        self.chd_resolver = ChdResolver(conn)
        self.sample_resolver = SampleResolver(conn)

    def resolve(self, machine_names: List[str], profile_name: str = "Custom",
                source_path: str = "", dest_path: str = "") -> SetManifest:
        """
        Resolve todas as dependências para as máquinas selecionadas.
        Retorna um SetManifest completo.
        """
        all_machines: Set[str] = set()
        required_files: List[FileRequirement] = []
        visited: Set[str] = set()

        for name in machine_names:
            self._resolve_machine(name, all_machines, required_files, visited)

        cursor = self.conn.execute("SELECT version FROM dataset ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        version = row[0] if row else "unknown"

        cursor2 = self.conn.execute("SELECT id FROM dataset ORDER BY id DESC LIMIT 1")
        row2 = cursor2.fetchone()
        fingerprint = str(row2[0]) if row2 else ""

        manifest = SetManifest(
            mame_version=version,
            dataset_fingerprint=fingerprint,
            profile_name=profile_name,
            selected_machines=list(all_machines),
            required_files=required_files,
            source_path=source_path,
            destination_path=dest_path,
        )
        logger.info(f"Resolução concluída: {len(all_machines)} máquinas, {len(required_files)} arquivos.")
        return manifest

    def _resolve_machine(self, machine_name: str, all_machines: Set[str],
                         required_files: List[FileRequirement], visited: Set[str]):
        if machine_name in visited:
            return
        visited.add(machine_name)
        all_machines.add(machine_name)

        cursor = self.conn.execute("SELECT * FROM machine WHERE name = ?", (machine_name,))
        machine = cursor.fetchone()
        if not machine:
            logger.warning(f"Máquina '{machine_name}' não encontrada.")
            return
        machine = dict(machine)

        # Clone
        clone_of = machine.get("cloneof")
        if clone_of:
            self._resolve_machine(clone_of, all_machines, required_files, visited)

        # ROMs
        roms = self.rom_resolver.get_roms(machine_name)
        for rom in roms:
            required_files.append(FileRequirement(
                machine_name=machine_name,
                file_type=FileType.ROM,
                file_name=rom["name"],
                source_machine=machine_name,
                size=rom.get("size"),
                crc=rom.get("crc"),
                sha1=rom.get("sha1"),
                merge=rom.get("merge"),
                logical_name=rom["name"],
                required=not rom.get("optional", False),
                dependency_reason=f"ROM da máquina {machine_name}"
            ))

        # BIOS
        bios_refs = self.bios_resolver.get_bios_for_machine(machine_name)
        for bios_name in bios_refs:
            self._resolve_machine(bios_name, all_machines, required_files, visited)

        # Devices
        device_refs = self.device_resolver.get_devices_for_machine(machine_name)
        for dev_name in device_refs:
            self._resolve_machine(dev_name, all_machines, required_files, visited)

        # CHDs
        disks = self.chd_resolver.get_disks(machine_name)
        for disk in disks:
            required_files.append(FileRequirement(
                machine_name=machine_name,
                file_type=FileType.CHD,
                file_name=f"{disk['name']}.chd",
                source_machine=machine_name,
                sha1=disk.get("sha1"),
                merge=disk.get("merge"),
                logical_name=disk["name"],
                required=not disk.get("optional", False),
                dependency_reason=f"CHD da máquina {machine_name}"
            ))

        # Samples
        samples = self.sample_resolver.get_samples(machine_name)
        for sample_name in samples:
            required_files.append(FileRequirement(
                machine_name=machine_name,
                file_type=FileType.SAMPLE,
                file_name=sample_name,
                source_machine=machine_name,
                required=True,
                dependency_reason=f"Sample da máquina {machine_name}"
            ))

        # BIOS/Device como ZIP
        if machine.get("isbios") or machine.get("isdevice"):
            existing = any(f.file_name == machine_name and f.file_type == FileType.ROM for f in required_files)
            if not existing:
                required_files.append(FileRequirement(
                    machine_name=machine_name,
                    file_type=FileType.ROM,
                    file_name=f"{machine_name}.zip",
                    source_machine=machine_name,
                    logical_name=machine_name,
                    required=True,
                    dependency_reason=f"{'BIOS' if machine.get('isbios') else 'Device'} {machine_name}"
                ))