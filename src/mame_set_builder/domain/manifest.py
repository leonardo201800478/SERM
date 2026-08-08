"""
Definição das entidades para o manifesto do set.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

class FileType(str, Enum):
    ROM = "rom"
    DISK = "disk"
    SAMPLE = "sample"
    BIOS = "bios"
    DEVICE = "device"

@dataclass
class FileRequirement:
    """Representa um arquivo (ROM, CHD, sample) necessário para o set."""
    machine_name: str           # máquina que requer este arquivo
    file_type: FileType         # rom, disk, sample, bios, device
    file_name: str              # nome do arquivo (ex.: "pacman.6e")
    source_machine: str         # máquina de onde este arquivo vem (ex.: "pacman", "neogeo")
    size: Optional[int] = None
    crc: Optional[str] = None
    sha1: Optional[str] = None
    merge: Optional[str] = None # se for merge, para qual arquivo

@dataclass
class SetManifest:
    """Manifesto completo para o set personalizado."""
    mame_version: str
    dataset_fingerprint: str
    profile_name: str
    selected_machines: List[str] = field(default_factory=list)
    required_files: List[FileRequirement] = field(default_factory=list)
    source_path: Optional[str] = None
    destination_path: Optional[str] = None