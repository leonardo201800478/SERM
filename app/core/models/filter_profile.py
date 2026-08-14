"""Modelo para perfis de filtro."""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class FilterCriteria:
    """Critérios de filtro."""
    categories: List[str] = field(default_factory=list)
    emulation_status: List[str] = field(default_factory=list)
    include_clones: bool = True
    include_categories: List[str] = field(default_factory=list)   # verde (forçar inclusão)
    exclude_categories: List[str] = field(default_factory=list)   # vermelho (forçar exclusão)
    include_bios: bool = True
    include_devices: bool = True
    include_chd: bool = True
    set_type: str = "split"
    arcade_systems: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "categories": self.categories,
            "include_categories": self.include_categories,
            "exclude_categories": self.exclude_categories,
            "emulation_status": self.emulation_status,
            "include_clones": self.include_clones,
            "include_bios": self.include_bios,
            "include_devices": self.include_devices,
            "include_chd": self.include_chd,
            "set_type": self.set_type,
            "arcade_systems": self.arcade_systems
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FilterCriteria":
        # Migração: se houver 'categories' e não houver 'include_categories', usar categories como include
        include_cats = data.get("include_categories", [])
        exclude_cats = data.get("exclude_categories", [])
        old_categories = data.get("categories", [])
        if not include_cats and old_categories:
            include_cats = old_categories
        return cls(
            categories=old_categories,  # manter para compatibilidade
            include_categories=include_cats,
            exclude_categories=exclude_cats,
            emulation_status=data.get("emulation_status", []),
            include_clones=data.get("include_clones", True),
            include_bios=data.get("include_bios", True),
            include_devices=data.get("include_devices", True),
            include_chd=data.get("include_chd", True),
            set_type=data.get("set_type", "split"),
            arcade_systems=data.get("arcade_systems", [])
        )

@dataclass
class FilterProfile:
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    criteria: FilterCriteria = field(default_factory=FilterCriteria)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    is_default: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "criteria": self.criteria.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_default": self.is_default
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FilterProfile":
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            description=data.get("description", ""),
            criteria=FilterCriteria.from_dict(data.get("criteria", {})),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            is_default=data.get("is_default", False)
        )