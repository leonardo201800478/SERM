"""Testes unitários do provider MAME do Arcade Studio."""

from __future__ import annotations

import json
from pathlib import Path

from serm_v2.catalog.mame import MameCatalogProvider
from serm_v2.models.arcade import ArcadePlatform, RomStatus
from serm_v2.services.scan_repository import ScanRepository


def _seed_scan(tmp_path: Path) -> tuple[ScanRepository, Path]:
    repository = ScanRepository(tmp_path / "serm.db")
    scan_path = tmp_path / "mame-scan.json"
    scan_path.write_text(
        json.dumps(
            {
                "scan_id": "scan-1",
                "evidence": [
                    {
                        "machine_name": "sf2",
                        "description": "Street Fighter II",
                        "cloneof": None,
                        "categories": ["Fighter", "2D"],
                        "status": "CURRENT",
                        "rom_name": "sf2.rom",
                        "runnable": True,
                    },
                    {
                        "machine_name": "sf2",
                        "description": "Street Fighter II",
                        "cloneof": None,
                        "categories": ["Fighter", "2D"],
                        "status": "MISSING",
                        "rom_name": "sf2-a.rom",
                        "runnable": True,
                    },
                    {
                        "machine_name": "sf2ce",
                        "description": "Street Fighter II Champion Edition",
                        "cloneof": "sf2",
                        "categories": ["Fighter", "2D"],
                        "status": "CURRENT",
                        "rom_name": "sf2ce.rom",
                        "runnable": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    with repository._connect() as connection:
        connection.execute(
            """INSERT INTO scan_runs (
                scan_id, profile_id, source, system, status, started_at, scan_file_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("scan-1", "profile-1", "MAME", "MAME", "completed", 1.0, str(scan_path)),
        )
    return repository, scan_path


def test_mame_provider_normalizes_games_and_parent_clone(tmp_path: Path) -> None:
    repository, _ = _seed_scan(tmp_path)
    provider = MameCatalogProvider(repository, "scan-1")

    games = provider.games()

    assert [game.machine_name for game in games] == ["sf2", "sf2ce"]
    assert games[0].platform is ArcadePlatform.MAME
    assert games[0].category == "Fighter"
    assert games[0].subcategory == "2D"
    assert games[1].parent_name == "sf2"
    assert games[1].is_clone


def test_mame_provider_consolidates_rom_status(tmp_path: Path) -> None:
    repository, _ = _seed_scan(tmp_path)
    provider = MameCatalogProvider(repository, "scan-1")

    game = provider.game("sf2")

    assert game is not None
    assert game.rom_status is RomStatus.MISSING
    assert provider.game("unknown") is None
