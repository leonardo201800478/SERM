"""Reconstrucao logica de ROMs para o Arcade Studio.

O engine nao conhece filesystem ou qualquer ferramenta externa. Ele recebe a
definicao catalogada das ROMs e um inventario fisico fornecido pelo SERM.

A resolucao fisica usa primeiro o plano logico de origem (merge, romof,
parent ou self) e somente depois procura o arquivo por identidade criptografica.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from ...models.arcade import ArcadeGame, ArcadeRom, RomStatus
from .rom_reconstruction_plan import ArcadeRomReconstructionPlanner, RomSourceKind


class RomMatchKind(StrEnum):
    """Tipo de correspondencia encontrada no inventario."""

    SHA1 = "sha1"
    MD5 = "md5"
    CRC_SIZE = "crc_size"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class PhysicalRom:
    """Arquivo fisico identificado pelo inventario do SERM."""

    path: str
    size: int
    crc: str | None = None
    sha1: str | None = None
    md5: str | None = None


@dataclass(frozen=True, slots=True)
class RomReconstruction:
    """Resultado da tentativa de localizar uma ROM catalogada."""

    machine_name: str
    rom_name: str
    match: PhysicalRom | None
    kind: RomMatchKind
    candidates: tuple[PhysicalRom, ...] = ()
    source_machine: str | None = None
    source_rom_name: str | None = None
    source_kind: RomSourceKind = RomSourceKind.SELF

    @property
    def is_resolved(self) -> bool:
        return self.match is not None and self.kind is not RomMatchKind.AMBIGUOUS


@dataclass(frozen=True, slots=True)
class ReconstructionResult:
    """Resultado auditavel de uma reconstrucao."""

    items: tuple[RomReconstruction, ...]

    @property
    def resolved_count(self) -> int:
        return sum(item.is_resolved for item in self.items)

    @property
    def missing_count(self) -> int:
        return sum(item.kind is RomMatchKind.MISSING for item in self.items)

    @property
    def ambiguous_count(self) -> int:
        return sum(item.kind is RomMatchKind.AMBIGUOUS for item in self.items)

    @property
    def is_complete(self) -> bool:
        return not self.missing_count and not self.ambiguous_count


class ArcadeRomReconstructionEngine:
    """Resolve componentes catalogados contra o inventario fisico do SERM."""

    def reconstruct(
        self,
        games: Iterable[ArcadeGame],
        inventory: Iterable[PhysicalRom],
    ) -> ReconstructionResult:
        catalog_games = tuple(games)
        physical = tuple(inventory)
        index = self._build_index(physical)
        plans = ArcadeRomReconstructionPlanner().plan(catalog_games)
        results: list[RomReconstruction] = []

        for plan in plans.items:
            game = next(game for game in catalog_games if game.machine_name == plan.machine_name)
            rom = next(rom for rom in game.roms if rom.machine_name == plan.rom_name)
            source_rom = rom
            if plan.source_machine and plan.source_machine != game.machine_name:
                source_game = next(
                    (item for item in catalog_games if item.machine_name == plan.source_machine),
                    None,
                )
                if source_game is not None:
                    source_rom = next(
                        (item for item in source_game.roms if item.machine_name == plan.source_rom_name),
                        rom,
                    )
            results.append(
                self._resolve(
                    plan.machine_name,
                    rom,
                    index,
                    source_machine=plan.source_machine,
                    source_rom_name=plan.source_rom_name,
                    source_kind=plan.source_kind,
                    source_rom=source_rom,
                )
            )

        return ReconstructionResult(items=tuple(results))

    @staticmethod
    def _build_index(inventory: tuple[PhysicalRom, ...]) -> Mapping[str, tuple[PhysicalRom, ...]]:
        index: dict[str, list[PhysicalRom]] = {}
        for item in inventory:
            if item.sha1:
                index.setdefault(f"sha1:{item.sha1.casefold()}", []).append(item)
            if item.md5:
                index.setdefault(f"md5:{item.md5.casefold()}", []).append(item)
            if item.crc is not None:
                index.setdefault(f"crc:{item.crc.casefold()}:{item.size}", []).append(item)
        return {key: tuple(value) for key, value in index.items()}

    @staticmethod
    def _resolve(
        machine_name: str,
        rom: ArcadeRom,
        index: Mapping[str, tuple[PhysicalRom, ...]],
        *,
        source_machine: str | None,
        source_rom_name: str | None,
        source_kind: RomSourceKind,
        source_rom: ArcadeRom,
    ) -> RomReconstruction:
        metadata = source_rom.metadata
        sha1 = ArcadeRomReconstructionEngine._text(metadata.get("sha1"))
        md5 = ArcadeRomReconstructionEngine._text(metadata.get("md5"))
        crc = ArcadeRomReconstructionEngine._text(metadata.get("crc"))
        size = ArcadeRomReconstructionEngine._int(metadata.get("size"))

        for kind, key in (
            (RomMatchKind.SHA1, f"sha1:{sha1.casefold()}" if sha1 else None),
            (RomMatchKind.MD5, f"md5:{md5.casefold()}" if md5 else None),
            (RomMatchKind.CRC_SIZE, f"crc:{crc.casefold()}:{size}" if crc and size is not None else None),
        ):
            if key is None:
                continue
            candidates = index.get(key, ())
            if len(candidates) == 1:
                return RomReconstruction(
                    machine_name, rom.machine_name, candidates[0], kind, (),
                    source_machine, source_rom_name, source_kind,
                )
            if len(candidates) > 1:
                return RomReconstruction(
                    machine_name, rom.machine_name, None, RomMatchKind.AMBIGUOUS,
                    candidates, source_machine, source_rom_name, source_kind,
                )

        return RomReconstruction(
            machine_name, rom.machine_name, None, RomMatchKind.MISSING, (),
            source_machine, source_rom_name, source_kind,
        )

    @staticmethod
    def _text(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _int(value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


__all__ = [
    "ArcadeRomReconstructionEngine",
    "PhysicalRom",
    "ReconstructionResult",
    "RomMatchKind",
    "RomReconstruction",
]
