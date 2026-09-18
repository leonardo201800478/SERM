"""Planejamento e reconstrução física de CHDs para o Arcade Studio.

CHD não é tratado como uma ROM comum. O hash presente no ListXML identifica o
conteúdo lógico do disco; o arquivo ``.chd`` é um contêiner comprimido e pode
ter um hash de arquivo diferente. O inventário físico deve, portanto, fornecer
os hashes lógicos extraídos do CHD.

A reconstrução é executada pelo SERM e não depende de RomVault. A camada aqui
é independente de filesystem: recebe um inventário de CHDs já analisados e
retorna exatamente qual arquivo deve satisfazer cada disco catalogado.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from ...models.arcade import ArcadeDisk, ArcadeGame
from .rom_reconstruction_plan import RomSourceKind


class ChdMatchKind(StrEnum):
    """Tipo de identidade usado para localizar um CHD."""

    SHA1 = "sha1"
    MD5 = "md5"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class PhysicalChd:
    """CHD físico com identidade lógica extraída pelo SERM."""

    path: str
    logical_sha1: str | None = None
    logical_md5: str | None = None
    file_size: int | None = None
    file_sha1: str | None = None
    disk_name: str | None = None


@dataclass(frozen=True, slots=True)
class ChdReconstructionPlan:
    """Origem lógica de um CHD catalogado."""

    machine_name: str
    disk_name: str
    source_machine: str | None
    source_disk_name: str | None
    source_kind: RomSourceKind
    reason: str


@dataclass(frozen=True, slots=True)
class ChdReconstruction:
    """Resultado da resolução de um disco catalogado."""

    machine_name: str
    disk_name: str
    match: PhysicalChd | None
    kind: ChdMatchKind
    candidates: tuple[PhysicalChd, ...] = ()
    source_machine: str | None = None
    source_disk_name: str | None = None
    source_kind: RomSourceKind = RomSourceKind.SELF

    @property
    def is_resolved(self) -> bool:
        return self.match is not None and self.kind not in {
            ChdMatchKind.AMBIGUOUS,
            ChdMatchKind.INVALID,
        }


@dataclass(frozen=True, slots=True)
class ChdReconstructionResult:
    """Resultado auditável da reconstrução de todos os CHDs."""

    items: tuple[ChdReconstruction, ...]

    @property
    def resolved_count(self) -> int:
        return sum(item.is_resolved for item in self.items)

    @property
    def missing_count(self) -> int:
        return sum(item.kind is ChdMatchKind.MISSING for item in self.items)

    @property
    def ambiguous_count(self) -> int:
        return sum(item.kind is ChdMatchKind.AMBIGUOUS for item in self.items)

    @property
    def invalid_count(self) -> int:
        return sum(item.kind is ChdMatchKind.INVALID for item in self.items)

    @property
    def is_complete(self) -> bool:
        return not self.missing_count and not self.ambiguous_count and not self.invalid_count


class ArcadeChdReconstructionEngine:
    """Reconstrói CHDs catalogados usando a identidade lógica do disco."""

    def plan(self, games: Iterable[ArcadeGame]) -> tuple[ChdReconstructionPlan, ...]:
        """Gera o plano de origem sem tocar no filesystem."""
        catalog = {game.machine_name: game for game in games}
        plans: list[ChdReconstructionPlan] = []
        for game in catalog.values():
            for disk in game.disks:
                plans.append(self._plan_disk(game, disk, catalog))
        return tuple(plans)

    def reconstruct(
        self,
        games: Iterable[ArcadeGame],
        inventory: Iterable[PhysicalChd],
    ) -> ChdReconstructionResult:
        """Resolve cada CHD contra o inventário físico do SERM."""
        catalog_games = tuple(games)
        catalog = {game.machine_name: game for game in catalog_games}
        physical = tuple(inventory)
        index = self._build_index(physical)
        results: list[ChdReconstruction] = []

        for plan in self.plan(catalog_games):
            game = catalog[plan.machine_name]
            disk = next(disk for disk in game.disks if disk.name == plan.disk_name)
            if plan.source_kind is RomSourceKind.MISSING:
                results.append(
                    ChdReconstruction(
                        game.machine_name,
                        disk.name,
                        None,
                        ChdMatchKind.INVALID,
                        source_machine=plan.source_machine,
                        source_disk_name=plan.source_disk_name,
                        source_kind=plan.source_kind,
                    )
                )
                continue
            source_disk = disk
            if plan.source_machine and plan.source_disk_name:
                source_game = catalog.get(plan.source_machine)
                if source_game is None:
                    results.append(
                        ChdReconstruction(
                            game.machine_name,
                            disk.name,
                            None,
                            ChdMatchKind.INVALID,
                            source_machine=plan.source_machine,
                            source_disk_name=plan.source_disk_name,
                            source_kind=plan.source_kind,
                        )
                    )
                    continue
                source_disk = next(
                    (candidate for candidate in source_game.disks if candidate.name == plan.source_disk_name),
                    None,
                )
                if source_disk is None:
                    results.append(
                        ChdReconstruction(
                            game.machine_name,
                            disk.name,
                            None,
                            ChdMatchKind.INVALID,
                            source_machine=plan.source_machine,
                            source_disk_name=plan.source_disk_name,
                            source_kind=plan.source_kind,
                        )
                    )
                    continue
            results.append(
                self._resolve(
                    game.machine_name,
                    disk.name,
                    source_disk,
                    index,
                    plan.source_machine,
                    plan.source_disk_name,
                    plan.source_kind,
                )
            )
        return ChdReconstructionResult(tuple(results))

    @staticmethod
    def _plan_disk(
        game: ArcadeGame,
        disk: ArcadeDisk,
        catalog: Mapping[str, ArcadeGame],
    ) -> ChdReconstructionPlan:
        merge = ArcadeChdReconstructionEngine._text(disk.merge)
        if merge:
            if not game.parent_name or game.parent_name not in catalog:
                return ChdReconstructionPlan(
                    game.machine_name,
                    disk.name,
                    game.parent_name,
                    merge,
                    RomSourceKind.MISSING,
                    "CHD possui merge explícito, mas o parent não está catalogado",
                )
            parent = catalog[game.parent_name]
            if not any(candidate.name == merge for candidate in parent.disks):
                return ChdReconstructionPlan(
                    game.machine_name,
                    disk.name,
                    parent.machine_name,
                    merge,
                    RomSourceKind.MISSING,
                    "CHD possui merge explícito, mas o disco não existe no parent",
                )
            return ChdReconstructionPlan(
                game.machine_name,
                disk.name,
                parent.machine_name,
                merge,
                RomSourceKind.MERGED,
                "CHD marcada como merge e encontrada no parent",
            )

        if game.parent_name and game.parent_name in catalog:
            parent = catalog[game.parent_name]
            if any(candidate.name == disk.name for candidate in parent.disks):
                return ChdReconstructionPlan(
                    game.machine_name,
                    disk.name,
                    parent.machine_name,
                    disk.name,
                    RomSourceKind.PARENT,
                    "mesmo CHD encontrado no parent",
                )

        return ChdReconstructionPlan(
            game.machine_name,
            disk.name,
            game.machine_name,
            disk.name,
            RomSourceKind.SELF,
            "CHD pertence ao próprio machine set",
        )

    @staticmethod
    def _build_index(inventory: tuple[PhysicalChd, ...]) -> Mapping[str, tuple[PhysicalChd, ...]]:
        index: dict[str, list[PhysicalChd]] = {}
        for item in inventory:
            if item.logical_sha1:
                index.setdefault(f"sha1:{item.logical_sha1.casefold()}", []).append(item)
            if item.logical_md5:
                index.setdefault(f"md5:{item.logical_md5.casefold()}", []).append(item)
        return {key: tuple(value) for key, value in index.items()}

    @classmethod
    def _resolve(
        cls,
        machine_name: str,
        disk_name: str,
        disk: ArcadeDisk,
        index: Mapping[str, tuple[PhysicalChd, ...]],
        source_machine: str | None,
        source_disk_name: str | None,
        source_kind: RomSourceKind,
    ) -> ChdReconstruction:
        for kind, key in (
            (ChdMatchKind.SHA1, cls._key("sha1", disk.sha1)),
            (ChdMatchKind.MD5, cls._key("md5", disk.md5)),
        ):
            if key is None:
                continue
            candidates = index.get(key, ())
            if len(candidates) == 1:
                return ChdReconstruction(
                    machine_name,
                    disk_name,
                    candidates[0],
                    kind,
                    source_machine=source_machine,
                    source_disk_name=source_disk_name,
                    source_kind=source_kind,
                )
            if len(candidates) > 1:
                return ChdReconstruction(
                    machine_name,
                    disk_name,
                    None,
                    ChdMatchKind.AMBIGUOUS,
                    candidates,
                    source_machine,
                    source_disk_name,
                    source_kind,
                )
        return ChdReconstruction(
            machine_name,
            disk_name,
            None,
            ChdMatchKind.MISSING,
            source_machine=source_machine,
            source_disk_name=source_disk_name,
            source_kind=source_kind,
        )

    @staticmethod
    def _key(kind: str, value: str | None) -> str | None:
        return f"{kind}:{value.casefold()}" if value else None

    @staticmethod
    def _text(value: object) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        return value or None


__all__ = [
    "ArcadeChdReconstructionEngine",
    "ChdMatchKind",
    "ChdReconstruction",
    "ChdReconstructionPlan",
    "ChdReconstructionResult",
    "PhysicalChd",
]
