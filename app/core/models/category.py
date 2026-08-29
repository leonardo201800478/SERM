"""Modelo para categorias de máquinas."""
from dataclasses import dataclass


@dataclass
class Category:
    id: int | None = None
    name: str = ""
    display_name: str = ""
    source: str = "manual"