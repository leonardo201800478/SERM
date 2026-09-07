"""Provider MAME para o Arcade Studio.

Nesta primeira versão o catálogo é derivado do snapshot persistido pelo scan
V2. O provider não copia nem altera o XML/DAT de origem e mantém a resolução
MAME isolada da futura UI.
"""

from __future__ import annotations

from pathlib import Path

from ..models.arcade import ArcadeGame, ArcadePlatform, ArcadeRom, RomStatus
from ..services.scan_repository import ScanRepository
from .base import ArcadeCatalogProvider


class MameCatalogProvider(ArcadeCatalogProvider):
    """Expõe um scan MAME como catálogo normalizado do Arcade Studio."""

    platform = ArcadePlatform.MAME

    def __init__(self, repository: ScanRepository, scan_id: str) -> None:
        self._repository = repository
        self.scan_id = str(scan_id)
        self._games: dict[str, ArcadeGame] | None = None

    def source(self) -> Path | None:
        """Retorna o snapshot bruto associado ao scan, se existir."""
        return self._repository.raw_file(self.scan_id)

    def _load(self) -> dict[str, ArcadeGame]:
        if self._games is not None:
            return self._games

        rows = self._repository.evidence(self.scan_id)
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            machine_name = str(row.get("machine_name") or "").strip()
            if machine_name:
                grouped.setdefault(machine_name, []).append(row)

        games: dict[str, ArcadeGame] = {}
        for machine_name, items in grouped.items():
            first = items[0]
            parent = str(first.get("parent_name") or first.get("parent") or "").strip() or None
            display_name = str(first.get("description") or first.get("machine_name") or machine_name)
            roms = tuple(self._rom(machine_name, row) for row in items)
            games[machine_name] = ArcadeGame(
                machine_name=machine_name,
                display_name=display_name,
                platform=self.platform,
                parent_name=parent,
                roms=roms,
                metadata={"scan_id": self.scan_id},
            )

        self._games = games
        return games

    @staticmethod
    def _rom(machine_name: str, row: dict) -> ArcadeRom:
        status = str(row.get("status") or "").upper()
        status_map = {
            "CURRENT": RomStatus.OK,
            "DUPLICATE": RomStatus.OK,
            "MISSING": RomStatus.MISSING,
            "WRONG": RomStatus.INVALID,
            "ERROR": RomStatus.INVALID,
        }
        return ArcadeRom(
            machine_name=machine_name,
            display_name=str(row.get("rom_name") or machine_name),
            platform=ArcadePlatform.MAME,
            rom_status=status_map.get(status, RomStatus.UNKNOWN),
            metadata={
                "scan_item_id": row.get("id"),
                "path": row.get("path"),
                "archive_path": row.get("archive_path"),
                "archive_member": row.get("archive_member"),
                "expected_size": row.get("expected_size"),
                "actual_size": row.get("actual_size"),
            },
        )

    def games(self) -> list[ArcadeGame]:
        """Retorna os títulos em ordem estável pelo machine name."""
        return [self._load()[name] for name in sorted(self._load())]

    def game(self, machine_name: str) -> ArcadeGame | None:
        return self._load().get(str(machine_name).strip())


__all__ = ["MameCatalogProvider"]
