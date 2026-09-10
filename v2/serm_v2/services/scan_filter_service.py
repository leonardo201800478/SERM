"""Compatibilidade para consumidores antigos de filtros MAME.

A implementação efetiva está em ``arcade.mame_filter_v2_service``. Este
adaptador mantém os nomes públicos antigos enquanto elimina a construção
incorreta de ArcadeGame e qualquer regra duplicada da GUI legada.
"""

from __future__ import annotations

from pathlib import Path

from .arcade.mame_filter_v2_service import MameFilterV2Service


class ScanFilterService:
    """Facade compatível apontando para o motor MAME V2."""

    @classmethod
    def facets_mame(cls, scan_path: Path):
        return MameFilterV2Service.facets(scan_path)

    @classmethod
    def preview_mame(cls, scan_path: Path, profile, fundamental_values, category_values=None, advanced_values=None):
        state = cls._state(profile, fundamental_values, category_values, advanced_values)
        return MameFilterV2Service.preview(scan_path, state)

    @classmethod
    def apply_mame(cls, scan_path: Path, profile, fundamental_values, category_values=None, advanced_values=None):
        state = cls._state(profile, fundamental_values, category_values, advanced_values)
        return MameFilterV2Service.apply(scan_path, state)

    @staticmethod
    def _state(profile, fundamental_values, category_values, advanced_values):
        from types import SimpleNamespace

        advanced = advanced_values or {}
        return SimpleNamespace(
            profile_id=str(getattr(profile, "profile_id", "mame-v2")),
            mame_set_type=str(getattr(profile, "mame_set_type", "split")),
            mame_clone_policy=str(getattr(profile, "mame_clone_policy", "with_clones")),
            mame_include_bios=bool(getattr(profile, "mame_include_bios", False)),
            mame_include_devices=bool(getattr(profile, "mame_include_devices", False)),
            mame_include_chd=bool(getattr(profile, "mame_include_chd", True)),
            mame_include_optional=bool(getattr(profile, "mame_include_optional", True)),
            mame_working_only=bool(getattr(profile, "mame_working_only", False)),
            fundamental=dict(fundamental_values or {}),
            categories=list((category_values or {}).get("categories", [])),
            subcategories=list((category_values or {}).get("subcategories", [])),
            content=list(advanced.get("content", [])),
            playability=list(advanced.get("playability", [])),
            genre=list(advanced.get("genre", [])),
            hardware=list(advanced.get("hardware", [])),
            manufacturer=list(advanced.get("manufacturer", [])),
            series=list(advanced.get("series", [])),
            input=list(advanced.get("input", [])),
            wheel=list(advanced.get("wheel", [])),
            database_path=None,
        )


__all__ = ["ScanFilterService"]
