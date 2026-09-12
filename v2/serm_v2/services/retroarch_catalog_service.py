"""Catálogo de cores RetroArch com semântica de filtro explícita."""

from __future__ import annotations

from collections.abc import Iterable

from .emulator_manager import CoreInfo, RetroArchManager


class RetroArchCatalogService:
    """Orquestra fontes Stable/Nightly e aplica filtros em uma única etapa."""

    @staticmethod
    def _merge_sources(stable: Iterable[CoreInfo], nightly: Iterable[CoreInfo]) -> tuple[CoreInfo, ...]:
        """Mescla fontes por nome, preservando Stable como fonte canônica."""
        merged: dict[str, CoreInfo] = {}
        for core in stable:
            merged[core.core_name.casefold()] = core
        for core in nightly:
            key = core.core_name.casefold()
            if key not in merged:
                merged[key] = core
        return tuple(sorted(merged.values(), key=lambda item: item.core_name.casefold()))

    @classmethod
    def fetch(
        cls, manager: RetroArchManager, *, include_nightly: bool
    ) -> tuple[tuple[CoreInfo, ...], str]:
        """Obtém um snapshot bruto, sem misturar seleção de filtros com a origem."""
        stable = manager.list_cores("stable", current_only=False, hide_games=False)
        if not include_nightly:
            return stable, "Stable"
        nightly = manager.list_cores("nightly", current_only=False, hide_games=False)
        return cls._merge_sources(stable, nightly), "Stable + Nightly adicionais"

    @staticmethod
    def filter_snapshot(
        cores: Iterable[CoreInfo], *, current_only: bool, hide_games: bool
    ) -> tuple[CoreInfo, ...]:
        """Aplica exclusivamente os filtros de conteúdo ao snapshot já carregado."""
        return tuple(
            core
            for core in cores
            if (not current_only or not RetroArchManager.is_legacy_core(core))
            and (not hide_games or not RetroArchManager.is_game_or_engine_core(core))
        )


__all__ = ["RetroArchCatalogService"]
