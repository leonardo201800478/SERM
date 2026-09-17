"""Plano unificado de materializacao do Arcade Studio V2.

Esta camada ainda nao grava arquivos. Ela transforma os resultados de
reconstrucao de ROMs/CHDs e o layout do set em um manifesto deterministico,
validando conflitos antes de qualquer operacao fisica.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

from ...models.arcade import ArcadeGame, ArcadeSetType
from .chd_reconstruction import ChdMatchKind, ChdReconstructionResult
from .rom_reconstruction import ReconstructionResult, RomMatchKind
from .set_layout import ArcadeSetLayoutPlanner


class MaterializationKind(StrEnum):
    """Tipo de componente que sera materializado."""

    ROM = "rom"
    CHD = "chd"


@dataclass(frozen=True, slots=True)
class MaterializationEntry:
    """Uma operacao de materializacao prevista pelo manifesto."""

    kind: MaterializationKind
    machine_name: str
    source_machine: str | None
    source_path: str
    destination: str
    archive: str | None = None
    member_name: str | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ReconstructionManifest:
    """Manifesto completo, seguro para revisao antes da escrita."""

    set_name: str
    set_type: ArcadeSetType
    entries: tuple[MaterializationEntry, ...]
    unresolved: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()

    @property
    def is_ready(self) -> bool:
        return not self.unresolved and not self.conflicts

    @property
    def rom_count(self) -> int:
        return sum(entry.kind is MaterializationKind.ROM for entry in self.entries)

    @property
    def chd_count(self) -> int:
        return sum(entry.kind is MaterializationKind.CHD for entry in self.entries)


class ArcadeReconstructionManifestBuilder:
    """Consolida resultados logicos em um plano de materializacao."""

    def build(
        self,
        games: Iterable[ArcadeGame],
        *,
        set_name: str,
        set_type: ArcadeSetType,
        rom_result: ReconstructionResult,
        chd_result: ChdReconstructionResult | None = None,
    ) -> ReconstructionManifest:
        catalog = {game.machine_name: game for game in games}
        layout = ArcadeSetLayoutPlanner().plan(catalog.values(), set_type)
        layout_by_machine = {entry.machine_name: entry for entry in layout.entries}
        entries: list[MaterializationEntry] = []
        unresolved: list[str] = []
        conflicts: list[str] = []
        destinations: dict[str, MaterializationEntry] = {}

        rom_by_key = {(item.machine_name, item.rom_name): item for item in rom_result.items}
        for game in catalog.values():
            layout_entry = layout_by_machine[game.machine_name]
            for rom in game.roms:
                result = rom_by_key.get((game.machine_name, rom.display_name))
                if result is None or result.kind not in {
                    RomMatchKind.SHA1,
                    RomMatchKind.MD5,
                    RomMatchKind.CRC_SIZE,
                }:
                    if result is not None:
                        unresolved.append(
                            f"ROM {game.machine_name}/{rom.display_name}: {result.kind.value}"
                        )
                    else:
                        unresolved.append(
                            f"ROM {game.machine_name}/{rom.display_name}: sem resultado"
                        )
                    continue
                if result.match is None:
                    unresolved.append(
                        f"ROM {game.machine_name}/{rom.display_name}: sem arquivo fisico"
                    )
                    continue

                # SPLIT mantém dependencias no archive de origem; uma ROM
                # resolvida no parent nao deve ser duplicada no clone.
                if set_type is ArcadeSetType.SPLIT and result.source_machine != game.machine_name:
                    continue

                member_name = PurePosixPath(result.source_rom_name or rom.display_name).name
                archive = f"{layout_entry.archive_name}.zip"
                destination = f"{archive}!/{member_name}"
                self._append_unique(
                    entries,
                    destinations,
                    MaterializationEntry(
                        MaterializationKind.ROM,
                        game.machine_name,
                        result.source_machine,
                        result.match.path,
                        destination,
                        archive=archive,
                        member_name=member_name,
                        reason=result.source_kind.value,
                    ),
                    conflicts,
                )

        if chd_result is not None:
            chd_by_key = {(item.machine_name, item.disk_name): item for item in chd_result.items}
            roots = {game.machine_name: self._root_name(game, catalog) for game in catalog.values()}
            for game in catalog.values():
                for disk in game.disks:
                    result = chd_by_key.get((game.machine_name, disk.name))
                    if result is None:
                        unresolved.append(f"CHD {game.machine_name}/{disk.name}: sem resultado")
                        continue
                    if result.kind not in {ChdMatchKind.SHA1, ChdMatchKind.MD5} or result.match is None:
                        unresolved.append(
                            f"CHD {game.machine_name}/{disk.name}: {result.kind.value}"
                        )
                        continue
                    source_machine = result.source_machine or game.machine_name
                    directory_machine = (
                        roots[game.machine_name]
                        if set_type is ArcadeSetType.FULL_MERGED
                        else source_machine
                    )
                    member_name = PurePosixPath(disk.name).name + ".chd"
                    destination = f"{directory_machine}/{member_name}"
                    self._append_unique(
                        entries,
                        destinations,
                        MaterializationEntry(
                            MaterializationKind.CHD,
                            game.machine_name,
                            source_machine,
                            result.match.path,
                            destination,
                            reason=result.source_kind.value,
                        ),
                        conflicts,
                    )

        return ReconstructionManifest(
            set_name=set_name,
            set_type=set_type,
            entries=tuple(entries),
            unresolved=tuple(dict.fromkeys(unresolved)),
            conflicts=tuple(dict.fromkeys(conflicts)),
        )

    @staticmethod
    def _append_unique(
        entries: list[MaterializationEntry],
        destinations: dict[str, MaterializationEntry],
        entry: MaterializationEntry,
        conflicts: list[str],
    ) -> None:
        previous = destinations.get(entry.destination)
        if previous is None:
            destinations[entry.destination] = entry
            entries.append(entry)
            return
        if previous.source_path == entry.source_path:
            return
        conflicts.append(
            f"Destino {entry.destination} possui fontes distintas: "
            f"{previous.source_path} | {entry.source_path}"
        )

    @staticmethod
    def _root_name(game: ArcadeGame, catalog: dict[str, ArcadeGame]) -> str:
        current = game
        seen: set[str] = set()
        while current.parent_name and current.parent_name in catalog:
            if current.machine_name in seen:
                raise ValueError(f"Ciclo parent/clone detectado em {current.machine_name}")
            seen.add(current.machine_name)
            current = catalog[current.parent_name]
        return current.machine_name


__all__ = [
    "ArcadeReconstructionManifestBuilder",
    "MaterializationEntry",
    "MaterializationKind",
    "ReconstructionManifest",
]
