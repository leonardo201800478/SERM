"""Filtros fundamentais do MAME, preservados por profile_id.

Os filtros são deliberadamente separados do FilterProfileData legado para
manter a tela principal compacta. A configuração continua pertencendo ao
perfil através do mesmo profile_id e é consumida pelo scanner e pela estimativa.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from ..runtime.paths import data_root

FILTERS_FILE: Final[Path] = data_root() / "mame_fundamental_filters.json"

DEFAULT_FILTERS: Final[dict[str, bool]] = {
    "mechanical": True,
    "dance": True,
    "console": True,
    "handheld": True,
    "fruit_machines": True,
}

FILTER_DEFINITIONS: Final[dict[str, dict[str, object]]] = {
    "mechanical": {
        "label": "Máquinas mecânicas / eletromecânicas",
        "description": "Exclui máquinas classificadas como Mechanical/Electromechanical e equivalentes.",
    },
    "dance": {
        "label": "Máquinas de dança",
        "description": "Exclui máquinas de dança e categorias derivadas de Dance/Rhythm quando classificadas como máquina de dança.",
    },
    "console": {
        "label": "Consoles",
        "description": "Exclui máquinas classificadas como console/game console.",
    },
    "handheld": {
        "label": "Portáteis / Handhelds",
        "description": "Exclui máquinas classificadas como handheld/portable.",
    },
    "fruit_machines": {
        "label": "Fruit Machines e derivados",
        "description": "Exclui Fruit Machine, Slot Machine, Casino, Gambling, Redemption, Medal e classificações equivalentes.",
    },
}

# Padrões aplicados sobre category/subcategory do CATLIST. A classificação
# continua sendo fonte de enriquecimento; o ListXML permanece intacto.
CATEGORY_PATTERNS: Final[dict[str, tuple[str, ...]]] = {
    "mechanical": ("mechanical", "electromechanical", "pinball"),
    "dance": ("dance",),
    "console": ("console",),
    "handheld": ("handheld", "portable"),
    "fruit_machines": (
        "fruit machine", "fruit_machine", "slot machine", "slot_machine",
        "casino", "gambling", "redemption", "medal game", "medal_game",
    ),
}


class MameFundamentalFilterService:
    """Persiste e consulta os filtros fundamentais por profile_id."""

    @staticmethod
    def _read() -> dict[str, dict[str, bool]]:
        try:
            raw = json.loads(FILTERS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        if not isinstance(raw, dict):
            return {}
        result: dict[str, dict[str, bool]] = {}
        for profile_id, values in raw.items():
            if not isinstance(profile_id, str) or not isinstance(values, dict):
                continue
            result[profile_id] = {
                key: bool(values.get(key, default))
                for key, default in DEFAULT_FILTERS.items()
            }
        return result

    @classmethod
    def load(cls, profile_id: str) -> dict[str, bool]:
        values = cls._read().get(str(profile_id), {})
        return {key: bool(values.get(key, default)) for key, default in DEFAULT_FILTERS.items()}

    @classmethod
    def save(cls, profile_id: str, values: dict[str, bool]) -> None:
        data = cls._read()
        data[str(profile_id)] = {
            key: bool(values.get(key, default))
            for key, default in DEFAULT_FILTERS.items()
        }
        FILTERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        FILTERS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def delete(cls, profile_id: str) -> None:
        data = cls._read()
        data.pop(str(profile_id), None)
        FILTERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        FILTERS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def excluded_machine_names(cls, database: Path, values: dict[str, bool]) -> set[str]:
        """Retorna nomes de máquinas que pertencem aos grupos excluídos."""
        enabled = [key for key, default in DEFAULT_FILTERS.items() if bool(values.get(key, default))]
        if not enabled or not database.is_file():
            return set()

        names: set[str] = set()
        import sqlite3
        with sqlite3.connect(database) as connection:
            for key in enabled:
                patterns = CATEGORY_PATTERNS[key]
                clauses = []
                params: list[str] = []
                for pattern in patterns:
                    like = f"%{pattern.casefold()}%"
                    clauses.append("lower(coalesce(c.category,'')) LIKE ? OR lower(coalesce(c.subcategory,'')) LIKE ?")
                    params.extend((like, like))
                category_sql = " OR ".join(f"({clause})" for clause in clauses)
                query = f"""
                    SELECT DISTINCT m.name
                    FROM mame_classification c
                    JOIN mame_machine m ON m.id=c.machine_id
                    WHERE c.resolved_status='resolved'
                      AND ({category_sql})
                """
                names.update(str(row[0]) for row in connection.execute(query, params) if row[0])

            if "mechanical" in enabled:
                rows = connection.execute(
                    "SELECT name FROM mame_machine WHERE lower(coalesce(ismechanical,'')) IN ('yes','true','1')"
                ).fetchall()
                names.update(str(row[0]) for row in rows if row[0])
        return names

    @classmethod
    def summary(cls, values: dict[str, bool]) -> str:
        active = [str(FILTER_DEFINITIONS[key]["label"]) for key, enabled in values.items() if enabled]
        return f"{len(active)} exclusões ativas" if active else "Nenhuma exclusão ativa"


__all__ = [
    "DEFAULT_FILTERS",
    "FILTER_DEFINITIONS",
    "MameFundamentalFilterService",
]
