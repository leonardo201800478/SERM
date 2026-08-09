"""
Representação de um arquivo necessário para o set.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

class FileType(str, Enum):
    ROM = "rom"
    DISK = "disk"
    SAMPLE = "sample"
    BIOS = "bios"
    DEVICE = "device"
    CHD = "chd"

@dataclass
class FileRequirement:
    """Um arquivo (ROM, CHD, sample) necessário para o set."""
    logical_name: str                # nome lógico (ex.: "pacman.6e")
    file_name: str                   # nome do arquivo físico (ex.: "pacman.6e" ou "neogeo.zip")
    file_type: FileType
    source_machine: str              # máquina que fornece este arquivo
    size: Optional[int] = None
    crc: Optional[str] = None
    sha1: Optional[str] = None
    merge: Optional[str] = None      # se for merge, para qual arquivo
    required: bool = True            # se é obrigatório
    dependency_reason: str = ""      # explicação de por que é necessário