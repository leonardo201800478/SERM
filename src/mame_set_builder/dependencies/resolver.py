"""
Resolvedor de dependências – coordena a busca de ROMs, BIOS, devices, etc.
"""

import sqlite3
import logging
from typing import List, Set, Dict, Any, Optional
from ..domain.manifest import SetManifest, FileRequirement, FileType
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

    def resolve(self, machine_names: List[str], profile_name: str = "Custom") -> SetManifest:
        """
        Para cada máquina, obtém todas as dependências recursivamente.
        Retorna um SetManifest com todos os arquivos necessários.
        """
        all_machines: Set[str] = set()
        required_files: List[FileRequirement] = []
        visited: Set[str] = set()

        # 1. Para cada máquina, resolve clones, BIOS, devices, etc.
        for name in machine_names:
            self._resolve_machine(name, all_machines, required_files, visited)

        # 2. Monta o manifesto
        manifest = SetManifest(
            mame_version=self._get_mame_version(),
            dataset_fingerprint="",
            profile_name=profile_name,
            selected_machines=list(all_machines),
            required_files=required_files,
        )
        logger.info(f"Resolução concluída: {len(all_machines)} máquinas, {len(required_files)} arquivos.")
        return manifest

    def _resolve_machine(self, machine_name: str, all_machines: Set[str],
                         required_files: List[FileRequirement], visited: Set[str]):
        """Resolve uma única máquina e suas dependências recursivamente."""
        if machine_name in visited:
            return
        visited.add(machine_name)
        all_machines.add(machine_name)

        # Obtém os dados da máquina
        machine = self._get_machine(machine_name)
        if not machine:
            logger.warning(f"Máquina '{machine_name}' não encontrada no banco.")
            return

        # 1. Clones: herda ROMs do cloneof
        clone_of = machine.get("cloneof")
        if clone_of:
            # Adiciona a máquina pai à lista de selecionadas
            self._resolve_machine(clone_of, all_machines, required_files, visited)

        # 2. ROMs da própria máquina (e também do cloneof, mas já resolvido)
        roms = self.rom_resolver.get_roms(machine_name)
        for rom in roms:
            required_files.append(
                FileRequirement(
                    machine_name=machine_name,
                    file_type=FileType.ROM,
                    file_name=rom["name"],
                    source_machine=machine_name,
                    size=rom.get("size"),
                    crc=rom.get("crc"),
                    sha1=rom.get("sha1"),
                    merge=rom.get("merge"),
                )
            )

        # 3. BIOS necessárias
        bios_refs = self.bios_resolver.get_bios_for_machine(machine_name)
        for bios_name in bios_refs:
            self._resolve_machine(bios_name, all_machines, required_files, visited)

        # 4. Devices referenciados
        device_refs = self.device_resolver.get_devices_for_machine(machine_name)
        for dev_name in device_refs:
            self._resolve_machine(dev_name, all_machines, required_files, visited)

        # 5. Discos (CHDs)
        disks = self.chd_resolver.get_disks(machine_name)
        for disk in disks:
            required_files.append(
                FileRequirement(
                    machine_name=machine_name,
                    file_type=FileType.DISK,
                    file_name=disk["name"],
                    source_machine=machine_name,
                    sha1=disk.get("sha1"),
                    merge=disk.get("merge"),
                )
            )

        # 6. Samples
        samples = self.sample_resolver.get_samples(machine_name)
        for sample_name in samples:
            required_files.append(
                FileRequirement(
                    machine_name=machine_name,
                    file_type=FileType.SAMPLE,
                    file_name=sample_name,
                    source_machine=machine_name,
                )
            )

        # 7. Se a máquina é um device ou BIOS, ela mesma deve ser incluída como um arquivo?
        # Normalmente, BIOS e devices são arquivos ROM, mas o MAME espera que o arquivo ZIP
        # correspondente exista. Então adicionamos como ROM também.
        if machine.get("isbios") or machine.get("isdevice"):
            # A ROM da BIOS/device é tipicamente o próprio nome (ex.: "neogeo.zip")
            # Vamos adicionar uma entrada com file_name = machine_name
            # Mas cuidado para não duplicar.
            # Verificamos se já não existe um FileRequirement para este nome como ROM.
            existing = any(
                f.file_name == machine_name and f.file_type == FileType.ROM
                for f in required_files
            )
            if not existing:
                required_files.append(
                    FileRequirement(
                        machine_name=machine_name,
                        file_type=FileType.ROM,
                        file_name=machine_name,
                        source_machine=machine_name,
                    )
                )

    def _get_machine(self, machine_name: str) -> Optional[Dict[str, Any]]:
        cursor = self.conn.execute(
            "SELECT * FROM machine WHERE name = ?", (machine_name,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def _get_mame_version(self) -> str:
        cursor = self.conn.execute("SELECT version FROM dataset ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        return row["version"] if row else "unknown"