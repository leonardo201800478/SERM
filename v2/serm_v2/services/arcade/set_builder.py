"""Montagem deterministica de sets do Arcade Studio.

Esta camada transforma a selecao logica produzida pelo Filter Engine em uma
selecao consistente de maquinas, respeitando a topologia parent/clone e as
referencias de ROM usadas pelo MAME. A implementacao e deliberadamente
agnostica ao armazenamento fisico: nao verifica arquivos no disco.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from ...models.arcade import ArcadeGame, ArcadePlatform, ArcadeSet, ArcadeSetType


class SetBuildDecision(StrEnum):
    """Classificacao de cada maquina durante a montagem."""

    SELECTED = "selected"
    DEPENDENCY = "dependency"
    EXCLUDED = "excluded"
    MISSING_DEPENDENCY = "missing_dependency"
    UNSATISFIED_DEPENDENCY = "unsatisfied_dependency"
    CYCLE = "cycle"


class SetBuildError(ValueError):
    """Erro estrutural que impede a montagem segura do set."""


@dataclass(frozen=True, slots=True)
class SetBuildTrace:
    """Explicacao auditavel da inclusao ou exclusao de uma maquina."""

    machine_name: str
    decision: SetBuildDecision
    reason: str
    dependency_of: str | None = None


@dataclass(frozen=True, slots=True)
class SetBuildResult:
    """Resultado completo da montagem, incluindo auditoria."""

    arcade_set: ArcadeSet
    traces: tuple[SetBuildTrace, ...]
    missing_dependencies: tuple[str, ...] = ()
    unsatisfied_dependencies: tuple[str, ...] = ()
    cycles: tuple[tuple[str, ...], ...] = ()

    @property
    def selected_count(self) -> int:
        return sum(trace.decision is SetBuildDecision.SELECTED for trace in self.traces)

    @property
    def dependency_count(self) -> int:
        return sum(trace.decision is SetBuildDecision.DEPENDENCY for trace in self.traces)

    @property
    def is_valid(self) -> bool:
        return not (
            self.missing_dependencies
            or self.unsatisfied_dependencies
            or self.cycles
        )


class ArcadeSetBuilder:
    """Resolve dependencias logicas de um conjunto sem tocar no catalogo."""

    def build(
        self,
        games: Iterable[ArcadeGame],
        selected_names: Iterable[str] | None = None,
        *,
        name: str = "arcade-set",
        platform: ArcadePlatform = ArcadePlatform.MAME,
        set_type: ArcadeSetType = ArcadeSetType.SPLIT,
        include_bios: bool = False,
        include_devices: bool = False,
        include_chd: bool = True,
    ) -> SetBuildResult:
        catalog_games = tuple(games)
        catalog = {}
        for game in catalog_games:
            if game.machine_name in catalog:
                raise SetBuildError(f"Catalogo contem maquina duplicada: {game.machine_name}")
            catalog[game.machine_name] = game

        selected = tuple(dict.fromkeys(selected_names or catalog.keys()))
        unknown = tuple(machine for machine in selected if machine not in catalog)
        if unknown:
            raise SetBuildError(f"Maquinas selecionadas inexistentes: {', '.join(unknown)}")

        included: dict[str, SetBuildTrace] = {}
        missing: set[str] = set()
        unsatisfied: set[str] = set()
        cycles: list[tuple[str, ...]] = []

        def visit(machine_name: str, dependency_of: str | None, stack: tuple[str, ...]) -> None:
            if machine_name in stack:
                cycle = stack[stack.index(machine_name):] + (machine_name,)
                if cycle not in cycles:
                    cycles.append(cycle)
                return
            existing = included.get(machine_name)
            if existing is not None:
                if dependency_of is None and existing.decision is SetBuildDecision.DEPENDENCY:
                    included[machine_name] = SetBuildTrace(
                        machine_name,
                        SetBuildDecision.SELECTED,
                        "maquina selecionada",
                    )
                return
            game = catalog.get(machine_name)
            if game is None:
                missing.add(machine_name)
                return

            parent = game.parent_name
            if parent:
                visit(parent, machine_name, stack + (machine_name,))
            for dependency in self._dependency_names(game):
                visit(dependency, machine_name, stack + (machine_name,))

            if self._metadata_flag(game, "is_bios") and not include_bios:
                decision = SetBuildDecision.EXCLUDED
                reason = "BIOS desabilitado"
                if dependency_of is not None:
                    unsatisfied.add(machine_name)
                    decision = SetBuildDecision.UNSATISFIED_DEPENDENCY
                    reason = f"BIOS necessario para {dependency_of}, mas BIOS esta desabilitado"
                included[machine_name] = SetBuildTrace(
                    machine_name, decision, reason, dependency_of
                )
                return
            if self._metadata_flag(game, "is_device") and not include_devices:
                decision = SetBuildDecision.EXCLUDED
                reason = "device desabilitado"
                if dependency_of is not None:
                    unsatisfied.add(machine_name)
                    decision = SetBuildDecision.UNSATISFIED_DEPENDENCY
                    reason = f"device necessario para {dependency_of}, mas devices estao desabilitados"
                included[machine_name] = SetBuildTrace(
                    machine_name, decision, reason, dependency_of
                )
                return

            decision = SetBuildDecision.SELECTED if dependency_of is None else SetBuildDecision.DEPENDENCY
            reason = "maquina selecionada" if decision is SetBuildDecision.SELECTED else f"dependencia de {dependency_of}"
            included[machine_name] = SetBuildTrace(machine_name, decision, reason, dependency_of)

        for machine in selected:
            visit(machine, None, ())

        for machine in sorted(missing):
            included[machine] = SetBuildTrace(
                machine, SetBuildDecision.MISSING_DEPENDENCY, "dependencia nao encontrada"
            )

        for machine in sorted(unsatisfied):
            trace = included[machine]
            included[machine] = SetBuildTrace(
                machine,
                SetBuildDecision.UNSATISFIED_DEPENDENCY,
                trace.reason,
                trace.dependency_of,
            )

        ordered_names = sorted(
            machine
            for machine, trace in included.items()
            if trace.decision in {SetBuildDecision.SELECTED, SetBuildDecision.DEPENDENCY}
        )
        result_set = ArcadeSet(
            name=name,
            platform=platform,
            set_type=set_type,
            include_bios=include_bios,
            include_devices=include_devices,
            include_chd=include_chd,
        )
        result_set.add_games(catalog[machine] for machine in ordered_names)

        return SetBuildResult(
            arcade_set=result_set,
            traces=tuple(included[machine] for machine in sorted(included)),
            missing_dependencies=tuple(sorted(missing)),
            unsatisfied_dependencies=tuple(sorted(unsatisfied)),
            cycles=tuple(cycles),
        )

    @staticmethod
    def _metadata_flag(game: ArcadeGame, key: str) -> bool:
        value = game.metadata.get(key)
        if isinstance(value, bool):
            return value
        return str(value).strip().casefold() in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def _dependency_names(game: ArcadeGame) -> tuple[str, ...]:
        """Extrai referencias declaradas pelo provider sem adivinhar nomes."""
        metadata = game.metadata
        values: list[str] = []
        for key in ("dependencies", "devices", "device_refs", "bios", "bios_refs"):
            value = metadata.get(key)
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, Mapping):
                values.extend(str(item) for item in value.keys())
            elif isinstance(value, (list, tuple, set, frozenset)):
                values.extend(str(item) for item in value)
        return tuple(dict.fromkeys(value for value in values if value))


__all__ = [
    "ArcadeSetBuilder",
    "SetBuildDecision",
    "SetBuildError",
    "SetBuildResult",
    "SetBuildTrace",
]
