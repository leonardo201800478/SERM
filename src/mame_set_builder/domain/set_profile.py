from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class EmulationStatus(str, Enum):
    GOOD = "good"
    IMPERFECT = "imperfect"
    PRELIMINARY = "preliminary"
    ALL = "all"

class SetType(str, Enum):
    NON_MERGED = "non_merged"
    SPLIT = "split"
    MERGED = "merged"

class RomSetType(str, Enum):
    ALL = "all"
    PARENT = "parent"
    CLONE = "clone"

@dataclass
class SetProfile:
    """Perfil de seleção para construção do set."""
    name: str = "Meu Set"

    # Filtros de categoria (expandidos)
    categories: List[str] = field(default_factory=list)

    # Tipo de ROM set
    rom_set_type: RomSetType = RomSetType.ALL

    # Filtros de recursos
    use_chd: bool = False
    use_sample: bool = False
    use_bios: bool = False

    # MameCab only (restrição)
    mamecab_only: bool = False

    # Filtro de emulação
    emulation_status: EmulationStatus = EmulationStatus.PRELIMINARY

    # Tipo de set (merged/split/non-merged)
    set_type: SetType = SetType.SPLIT

    # Opções de clones
    include_clones: bool = True

    # Manter BIOS, Devices, Samples
    keep_bios: bool = True
    keep_devices: bool = True
    keep_samples: bool = False

    # Manter CHDs
    keep_chds: bool = True

    # Formato de arquivo destino
    archive_format: str = "zip"

    # Caminhos
    source_path: Optional[str] = None
    destination_path: Optional[str] = None

    # Filtros adicionais (ano, fabricante, etc.)
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    manufacturer: Optional[str] = None

    def __post_init__(self):
        if self.set_type == SetType.MERGED and not self.include_clones:
            raise ValueError("Em conjuntos Merged, não é possível excluir clones individualmente.")