"""Filtros avançados do MAME baseados no CATLIST persistido."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Final

from ..runtime.paths import data_root, database_path

FILTERS_FILE: Final[Path] = data_root() / "mame_category_filters.json"


class MameCategoryFilterService:
    """Consulta classificações CATLIST já importadas e persiste a seleção por perfil."""

    @staticmethod
    def _read() -> dict[str, dict]:
        try:
            raw = json.loads(FILTERS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    @classmethod
    def load(cls, profile_id: str) -> dict[str, list[str]]:
        raw = cls._read().get(str(profile_id), {})
        return {
            "categories": [str(v) for v in raw.get("categories", []) if str(v).strip()],
            "subcategories": [str(v) for v in raw.get("subcategories", []) if str(v).strip()],
        }

    @classmethod
    def save(cls, profile_id: str, values: dict[str, list[str]]) -> None:
        data = cls._read()
        data[str(profile_id)] = {
            "categories": sorted({str(v) for v in values.get("categories", []) if str(v).strip()}),
            "subcategories": sorted(
                {str(v) for v in values.get("subcategories", []) if str(v).strip()}
            ),
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
    def _database(database: Path | None = None) -> Path:
        return Path(database) if database is not None else database_path()

    @classmethod
    def tree(cls, database: Path | None = None) -> list[dict[str, object]]:
        """Retorna categorias/subcategorias CATLIST com quantidade de machines."""
        db_path = cls._database(database)
        if not db_path.is_file():
            return []
        query = """
            SELECT COALESCE(NULLIF(TRIM(category), ''), '[Sem categoria]') AS category,
                   COALESCE(NULLIF(TRIM(subcategory), ''), '') AS subcategory,
                   COUNT(DISTINCT machine_id) AS machines
            FROM mame_classification
            WHERE resolved_status = 'resolved'
            GROUP BY category, subcategory
            ORDER BY category COLLATE NOCASE, subcategory COLLATE NOCASE
        """
        with sqlite3.connect(db_path, timeout=30.0) as db:
            rows = db.execute(query).fetchall()
        return [
            {"category": str(row[0]), "subcategory": str(row[1]), "machines": int(row[2] or 0)}
            for row in rows
        ]

    @classmethod
    def matching_machine_names(
        cls, selected: dict[str, list[str]], database: Path | None = None
    ) -> set[str]:
        """Retorna nomes de machines classificados por qualquer seleção CATLIST."""
        categories = {str(v) for v in selected.get("categories", [])}
        subcategories = {str(v) for v in selected.get("subcategories", [])}
        if not categories and not subcategories:
            return set()
        db_path = cls._database(database)
        if not db_path.is_file():
            return set()
        clauses: list[str] = []
        params: list[str] = []
        if categories:
            placeholders = ",".join("?" for _ in categories)
            clauses.append(f"category IN ({placeholders})")
            params.extend(sorted(categories))
        if subcategories:
            placeholders = ",".join("?" for _ in subcategories)
            clauses.append(f"subcategory IN ({placeholders})")
            params.extend(sorted(subcategories))
        query = f"""
            SELECT DISTINCT machine_name
            FROM mame_classification
            WHERE resolved_status = 'resolved' AND ({" OR ".join(clauses)})
        """
        with sqlite3.connect(db_path, timeout=30.0) as db:
            return {str(row[0]) for row in db.execute(query, params) if row[0]}


__all__ = ["MameCategoryFilterService"]
