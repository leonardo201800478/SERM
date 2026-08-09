"""Modelo para categorias de máquinas."""
from dataclasses import dataclass
from typing import Optional

@dataclass
class Category:
    id: Optional[int] = None
    name: str = ""
    display_name: str = ""
    source: str = "manual"