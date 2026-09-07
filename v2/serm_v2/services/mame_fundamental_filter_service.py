"""Persistência dos filtros fundamentais do MAME por profile_id.

A configuração usa semântica direta: ``True`` significa INCLUIR a categoria
e ``False`` significa EXCLUIR. A interface apresenta a categoria incluída em
verde e a categoria excluída em vermelho.

A seleção acontece somente depois do scan, sobre o snapshot bruto. Este
serviço guarda apenas a configuração; não consulta o catálogo nem o
filesystem durante a auditoria.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from ..runtime.paths import data_root

# Arquivo V2 separado para não interpretar configurações criadas pela antiga
# semântica, na qual True significava "excluir".
FILTERS_FILE: Final[Path] = data_root() / "mame_fundamental_filters_v2.json"

# True = permanece no set; False = é excluída.
DEFAULT_FILTERS: Final[dict[str, bool]] = {
    "mechanical": False,
    "dance": True,
    "console": True,
    "handheld": True,
    "fruit_machines": False,
    "quiz": True,
    "tabletop": True,
}

FILTER_DEFINITIONS: Final[dict[str, dict[str, object]]] = {
    "mechanical": {
        "label": "Máquinas mecânicas / eletromecânicas",
        "description": "Verde = incluir no set. Vermelho = excluir Mechanical/Electromechanical e equivalentes.",
    },
    "dance": {
        "label": "Máquinas de dança",
        "description": "Verde = incluir no set. Vermelho = excluir máquinas classificadas como Dance.",
    },
    "console": {
        "label": "Consoles",
        "description": "Verde = incluir no set. Vermelho = excluir máquinas classificadas como console/game console.",
    },
    "handheld": {
        "label": "Portáteis / Handhelds",
        "description": "Verde = incluir no set. Vermelho = excluir máquinas classificadas como handheld/portable.",
    },
    "fruit_machines": {
        "label": "Fruit Machines e derivados",
        "description": "Verde = incluir no set. Vermelho = excluir Fruit Machine, Slot, Casino, Gambling, Redemption e Medal.",
    },
    "quiz": {
        "label": "Quiz / Trivia",
        "description": "Verde = incluir no set. Vermelho = excluir máquinas classificadas como Quiz/Trivia.",
    },
    "tabletop": {
        "label": "Tabletop",
        "description": "Verde = incluir no set. Vermelho = excluir máquinas classificadas como Tabletop.",
    },
}

CATEGORY_PATTERNS: Final[dict[str, tuple[str, ...]]] = {
    "mechanical": ("mechanical", "electromechanical", "pinball"),
    "dance": ("dance",),
    "console": ("console",),
    "handheld": ("handheld", "portable"),
    "fruit_machines": (
        "fruit machine",
        "fruit_machine",
        "slot machine",
        "slot_machine",
        "casino",
        "gambling",
        "redemption",
        "medal game",
        "medal_game",
    ),
    "quiz": ("quiz", "trivia"),
    "tabletop": ("tabletop", "table top"),
}


class MameFundamentalFilterService:
    """Persiste e consulta somente a configuração dos filtros fundamentais."""

    @staticmethod
    def _read() -> dict[str, dict[str, bool]]:
        try:
            raw = json.loads(FILTERS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        if not isinstance(raw, dict):
            return {}
        return {
            profile_id: {
                key: bool(values.get(key, default)) for key, default in DEFAULT_FILTERS.items()
            }
            for profile_id, values in raw.items()
            if isinstance(profile_id, str) and isinstance(values, dict)
        }

    @classmethod
    def load(cls, profile_id: str) -> dict[str, bool]:
        values = cls._read().get(str(profile_id), {})
        return {key: bool(values.get(key, default)) for key, default in DEFAULT_FILTERS.items()}

    @classmethod
    def save(cls, profile_id: str, values: dict[str, bool]) -> None:
        data = cls._read()
        data[str(profile_id)] = {
            key: bool(values.get(key, default)) for key, default in DEFAULT_FILTERS.items()
        }
        FILTERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        FILTERS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def delete(cls, profile_id: str) -> None:
        data = cls._read()
        data.pop(str(profile_id), None)
        FILTERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        FILTERS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def summary(values: dict[str, bool]) -> str:
        included = sum(1 for enabled in values.values() if enabled)
        excluded = len(values) - included
        return f"{included} incluída(s) | {excluded} excluída(s)"


__all__ = [
    "DEFAULT_FILTERS",
    "FILTER_DEFINITIONS",
    "CATEGORY_PATTERNS",
    "MameFundamentalFilterService",
]
