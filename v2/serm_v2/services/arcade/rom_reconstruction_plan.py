"""Plano de reconstrucao fisica de ROMs do Arcade Studio.

Esta camada resolve a origem logica de cada ROM antes de qualquer operacao de
filesystem. Ela entende parent/clone, ``romof`` e ``merge`` por meio dos
metadados normalizados pelo provider, mas permanece independente de SQLite,
filesystem e ferramentas externas.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from ...models.arcade import ArcadeGame, ArcadeRom


class RomSourceKind(StrEnum):
    """Origem logica usada para satisfazer uma ROM."""

    SELF = "self"
    PARENT = "parent"
    ROMOF = "romof"
    MERGED = "merged"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class RomReconstructionPlan:
    """Instrucao auditavel para obter uma ROM catalogada."""

    machine_name: str
    rom_name: str
    source_machine: str | None
    source_rom_name: str
    source_kind: RomSourceKind
    reason: str


@dataclass(frozen=True, slots=True)
class RomReconstructionPlanResult:
    """Plano completo de origem para as ROMs selecionadas."""

    items: tuple[RomReconstructionPlan, ...]

    @property
    def missing_count(self) -> int:
        return sum(item.source_kind is RomSourceKind.MISSING for item in self.items)

    @property
    def resolved_count(self) -> int:
        return len(self.items) - self.missing_count

    @property
    def is_complete(self) -> bool:
        return self.missing_count == 0


class ArcadeRomReconstructionPlanner:
    """Determina de qual maquina cada ROM deve ser obtida."""

    def plan(self, games: Iterable[ArcadeGame]) -> RomReconstructionPlanResult:
        catalog = {game.machine_name: game for game in games}
        items: list[RomReconstructionPlan] = []

        for game in catalog.values():
            for rom in game.roms:
                items.append(self._plan_rom(game, rom, catalog))

        return RomReconstructionPlanResult(tuple(items))

    def _plan_rom(
        self,
        game: ArcadeGame,
        rom: ArcadeRom,
        catalog: Mapping[str, ArcadeGame],
    ) -> RomReconstructionPlan:
        metadata = rom.metadata
        merge = self._text(metadata.get("merge"))
        romof = self._text(metadata.get("romof")) or self._text(game.metadata.get("romof"))

        # Em MAME, merge identifica o nome da ROM que deve ser procurado no
        # parent. A relacao e preferida a qualquer inferencia por nome de jogo.
        if merge and game.parent_name and game.parent_name in catalog:
            parent = catalog[game.parent_name]
            if any(candidate.machine_name == merge for candidate in parent.roms):
                return RomReconstructionPlan(
                    game.machine_name,
                    rom.machine_name,
                    parent.machine_name,
                    merge,
                    RomSourceKind.MERGED,
                    "ROM marcada como merge e encontrada no parent",
                )

        if romof and romof != game.machine_name and romof in catalog:
            target = catalog[romof]
            if any(candidate.machine_name == rom.machine_name for candidate in target.roms):
                return RomReconstructionPlan(
                    game.machine_name,
                    rom.machine_name,
                    target.machine_name,
                    rom.machine_name,
                    RomSourceKind.ROMOF,
                    "ROM encontrada na maquina indicada por romof",
                )

        if game.parent_name and game.parent_name in catalog:
            parent = catalog[game.parent_name]
            if any(candidate.machine_name == rom.machine_name for candidate in parent.roms):
                return RomReconstructionPlan(
                    game.machine_name,
                    rom.machine_name,
                    parent.machine_name,
                    rom.machine_name,
                    RomSourceKind.PARENT,
                    "mesmo nome de ROM encontrado no parent",
                )

        return RomReconstructionPlan(
            game.machine_name,
            rom.machine_name,
            game.machine_name,
            rom.machine_name,
            RomSourceKind.SELF,
            "ROM pertence ao proprio machine set",
        )

    @staticmethod
    def _text(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


__all__ = [
    "ArcadeRomReconstructionPlanner",
    "RomReconstructionPlan",
    "RomReconstructionPlanResult",
    "RomSourceKind",
]
