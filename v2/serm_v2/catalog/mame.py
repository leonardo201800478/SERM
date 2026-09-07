"""Provider MAME para o Arcade Studio.

Nesta primeira versão o catálogo é normalizado a partir do snapshot bruto do
scan V2. O provider não copia nem altera XML/DAT de origem e mantém detalhes
específicos do formato MAME fora da futura UI.
"""

from __future__ import annotations

from pathlib import Path

from ..models.arcade import ArcadeGame, ArcadePlatform, ArcadeRom, RomStatus
from ..services.scan_file_repository import ScanFileRepository
from ..services.scan_repository import ScanRepository
from .base import ArcadeCatalogProvider


class MameCatalogProvider(ArcadeCatalogProvider):
    """Expõe um snapshot de scan MAME como catálogo Arcade Studio."""

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
        path = self.source()
        if path is None or not path.is_file():
            self._games = {}
            return self._games
        payload = ScanFileRepository.load(path)
        evidence = payload.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = []
        grouped: dict[str, list[dict]] = {}
        for row in evidence:
            if isinstance(row, dict):
                machine_name = str(row.get("machine_name") or "").strip()
                if machine_name:
                    grouped.setdefault(machine_name, []).append(row)
        games: dict[str, ArcadeGame] = {}
        for machine_name, items in grouped.items():
            first = items[0]
            parent = str(first.get("cloneof") or "").strip() or None
            categories = self._strings(first.get("categories"))
            games[machine_name] = ArcadeGame(
                machine_name=machine_name,
                display_name=str(first.get("description") or machine_name),
                platform=self.platform,
                parent_name=parent,
                category=categories[0] if categories else None,
                subcategory=categories[1] if len(categories) > 1 else None,
                roms=tuple(self._rom(machine_name, row) for row in items),
                metadata={
                    "scan_id": self.scan_id,
                    "categories": categories,
                    "cloneof": parent,
                    "isbios": bool(first.get("isbios")),
                    "isdevice": bool(first.get("isdevice")),
                    "ismechanical": bool(first.get("ismechanical")),
                    "runnable": first.get("runnable"),
                },
            )
        self._games = games
        return games

    @staticmethod
    def _strings(value: object) -> list[str]:
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        if value is None:
            return []
        return [str(value).strip()] if str(value).strip() else []

    @staticmethod
    def _rom(machine_name: str, row: dict) -> ArcadeRom:
        status_map = {
            "CURRENT": RomStatus.OK,
            "DUPLICATE": RomStatus.OK,
            "MISSING": RomStatus.MISSING,
            "WRONG": RomStatus.INVALID,
            "ERROR": RomStatus.INVALID,
        }
        status = str(row.get("status") or "").upper()
        return ArcadeRom(
            machine_name=machine_name,
            display_name=str(row.get("rom_name") or machine_name),
            platform=ArcadePlatform.MAME,
            rom_status=status_map.get(status, RomStatus.UNKNOWN),
            is_bios=bool(row.get("isbios")),
            is_device=bool(row.get("isdevice")),
            has_chd=bool(row.get("chd")) or bool(row.get("disk_name")),
            working=row.get("runnable"),
            metadata={
                "scan_item_id": row.get("id"),
                "path": row.get("path"),
                "archive_path": row.get("archive_path"),
                "archive_member": row.get("archive_member"),
                "merge_name": row.get("merge_name"),
                "optional": bool(row.get("optional")),
                "expected_size": row.get("expected_size"),
                "actual_size": row.get("actual_size"),
            },
        )

    def games(self) -> list[ArcadeGame]:
        """Retorna os títulos em ordem estável pelo machine name."""
        games = self._load()
        return [games[name] for name in sorted(games)]

    def game(self, machine_name: str) -> ArcadeGame | None:
        """Localiza um título pelo nome técnico MAME."""
        return self._load().get(str(machine_name).strip())


__all__ = ["MameCatalogProvider"]
