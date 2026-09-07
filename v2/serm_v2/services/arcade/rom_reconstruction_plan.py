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
    """Determina de qual maquina cada ROM deve ser obtida.

    A identidade da ROM e o nome do arquivo fisico sao conceitos diferentes.
    ``display_name`` e o nome da ROM no ListXML; ``machine_name`` identifica a
    maquina que declara a ROM. A resolucao de origem usa essas duas dimensoes
    explicitamente e nunca compara o nome da maquina com o nome da ROM.
    """

    def plan(self, games: Iterable[ArcadeGame]) -> RomReconstructionPlanResult:
        catalog = {game.machine_name: game for game in games}
        rom_index = self._build_rom_index(catalog)
        items: list[RomReconstructionPlan] = []

        for game in catalog.values():
            for rom in game.roms:
                items.append(self._plan_rom(game, rom, catalog, rom_index))

        return RomReconstructionPlanResult(tuple(items))

    @staticmethod
    def _build_rom_index(
        catalog: Mapping[str, ArcadeGame],
    ) -> Mapping[str, tuple[tuple[str, ArcadeRom], ...]]:
        index: dict[str, list[tuple[str, ArcadeRom]]] = {}
        for machine_name, game in catalog.items():
            for rom in game.roms:
                name = rom.display_name.strip()
                if name:
                    index.setdefault(name.casefold(), []).append((machine_name, rom))
        return {key: tuple(value) for key, value in index.items()}

    def _plan_rom(
        self,
        game: ArcadeGame,
        rom: ArcadeRom,
        catalog: Mapping[str, ArcadeGame],
        rom_index: Mapping[str, tuple[tuple[str, ArcadeRom], ...]],
    ) -> RomReconstructionPlan:
        metadata = rom.metadata
        merge = self._text(metadata.get("merge"))
        romof = self._text(metadata.get("romof")) or self._text(game.metadata.get("romof"))
        parent_name = self._text(game.parent_name)

        # ``merge`` names a ROM, not a machine. Prefer the explicit parent
        # relationship when present, then romof, and only then a unique global
        # ROM-name match. This avoids inventing a dependency from a machine name.
        if merge:
            source = self._find_rom(merge, preferred_machines=(parent_name, romof), rom_index=rom_index)
            if source is not None:
                source_machine, source_rom = source
                if source_machine != game.machine_name or source_rom.display_name != rom.display_name:
                    return RomReconstructionPlan(
                        game.machine_name,
                        rom.display_name,
                        source_machine,
                        source_rom.display_name,
                        RomSourceKind.MERGED,
                        "merge resolvido pela identidade do nome da ROM",
                    )
                return RomReconstructionPlan(
                    game.machine_name,
                    rom.display_name,
                    game.machine_name,
                    source_rom.display_name,
                    RomSourceKind.SELF,
                    "merge referencia a propria ROM do machine set",
                )

            # Um ``merge`` explicito sem ROM de origem catalogada nao pode ser
            # convertido em uma ROM propria por fallback. Isso esconderia uma
            # dependencia semantica e produziria conjuntos incorretos.
            return RomReconstructionPlan(
                game.machine_name,
                rom.display_name,
                None,
                merge,
                RomSourceKind.MISSING,
                "merge definido, mas a ROM de origem nao foi localizada no catalogo",
            )

        if romof and romof != game.machine_name and romof in catalog:
            target = catalog[romof]
            target_rom = self._find_same_rom(target, rom.display_name)
            if target_rom is not None:
                return RomReconstructionPlan(
                    game.machine_name,
                    rom.display_name,
                    target.machine_name,
                    target_rom.display_name,
                    RomSourceKind.ROMOF,
                    "ROM encontrada na maquina indicada por romof",
                )

        if parent_name and parent_name in catalog:
            parent = catalog[parent_name]
            parent_rom = self._find_same_rom(parent, rom.display_name)
            if parent_rom is not None:
                return RomReconstructionPlan(
                    game.machine_name,
                    rom.display_name,
                    parent.machine_name,
                    parent_rom.display_name,
                    RomSourceKind.PARENT,
                    "mesmo nome de ROM encontrado no parent",
                )

        return RomReconstructionPlan(
            game.machine_name,
            rom.display_name,
            game.machine_name,
            rom.display_name,
            RomSourceKind.SELF,
            "ROM pertence ao proprio machine set",
        )

    @classmethod
    def _find_rom(
        cls,
        rom_name: str,
        *,
        preferred_machines: tuple[str | None, ...],
        rom_index: Mapping[str, tuple[tuple[str, ArcadeRom], ...]],
    ) -> tuple[str, ArcadeRom] | None:
        candidates = rom_index.get(rom_name.casefold(), ())
        if not candidates:
            return None

        preferred = {value.casefold() for value in preferred_machines if value}
        preferred_candidates = tuple(item for item in candidates if item[0].casefold() in preferred)
        if len(preferred_candidates) == 1:
            return preferred_candidates[0]
        if len(preferred_candidates) > 1:
            return None

        if len(candidates) == 1:
            return candidates[0]
        return None

    @staticmethod
    def _find_same_rom(game: ArcadeGame, rom_name: str) -> ArcadeRom | None:
        matches = tuple(rom for rom in game.roms if rom.display_name.casefold() == rom_name.casefold())
        return matches[0] if len(matches) == 1 else None

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
