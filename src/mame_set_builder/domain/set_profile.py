"""
Definição do perfil de seleção (SetProfile).
Contém todas as opções de filtro e configuração do set.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set
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

@dataclass
class SetProfile:
    """Perfil de seleção para construção do set."""
    name: str = "Meu Set"
    
    # Filtros de categoria
    categories: List[str] = field(default_factory=list)  # ex.: ["Arcade", "Console"]
    
    # Filtro de emulação
    emulation_status: EmulationStatus = EmulationStatus.PRELIMINARY
    
    # Tipo de set
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
    archive_format: str = "zip"  # "zip" ou "7z"
    
    # Caminhos
    source_path: Optional[str] = None
    destination_path: Optional[str] = None
    
    # Filtros adicionais (ano, fabricante, etc.) – futuro
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    manufacturer: Optional[str] = None
    
    def __post_init__(self):
        # Validação básica
        if self.set_type == SetType.MERGED and not self.include_clones:
            raise ValueError("Em conjuntos Merged, não é possível excluir clones individualmente.")