import json
import zipfile
from pathlib import Path

import pytest

from serm_v2.services.reconstruction_service import ReconstructionError, ReconstructionService


def test_mame_reconstruction_keeps_only_current_items_and_cleans_destination(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    source_archive = source / "pacman.zip"
    target_archive = destination / "pacman.zip"

    with zipfile.ZipFile(source_archive, "w") as archive:
        archive.writestr("good.bin", b"valid")
        archive.writestr("bad.bin", b"invalid")
    with zipfile.ZipFile(target_archive, "w") as archive:
        archive.writestr("good.bin", b"valid")
        archive.writestr("stale.bin", b"stale")
    stale_file = destination / "orphan.txt"
    stale_file.write_text("stale", encoding="utf-8")

    filter_path = tmp_path / "filter.json"
    filter_path.write_text(
        json.dumps(
            {
                "format": "SERM-FILTER-V1",
                "source": "mame",
                "system": "arcade",
                "evidence": [
                    {
                        "machine_name": "pacman",
                        "status": "CURRENT",
                        "archive_path": str(target_archive),
                        "archive_member": "good.bin",
                    },
                    {
                        "machine_name": "pacman",
                        "status": "CURRENT",
                        "archive_path": str(source_archive),
                        "archive_member": "good.bin",
                    },
                    {
                        "machine_name": "pacman",
                        "status": "WRONG",
                        "archive_path": str(source_archive),
                        "archive_member": "bad.bin",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = ReconstructionService.plan(filter_path, destination)
    result = ReconstructionService.execute(plan)

    assert result["created_count"] == 1
    with zipfile.ZipFile(target_archive) as archive:
        assert archive.namelist() == ["good.bin"]
        assert archive.read("good.bin") == b"valid"
    assert not stale_file.exists()
    with zipfile.ZipFile(source_archive) as archive:
        assert set(archive.namelist()) == {"good.bin", "bad.bin"}


def test_failed_reconstruction_does_not_clean_destination(tmp_path: Path) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()
    stale_file = destination / "keep-on-failure.txt"
    stale_file.write_text("do not delete after failure", encoding="utf-8")
    filter_path = tmp_path / "filter.json"
    filter_path.write_text(
        json.dumps(
            {
                "format": "SERM-FILTER-V1",
                "source": "mame",
                "system": "arcade",
                "evidence": [
                    {
                        "machine_name": "pacman",
                        "status": "CURRENT",
                        "archive_path": str(tmp_path / "missing.zip"),
                        "archive_member": "good.bin",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = ReconstructionService.plan(filter_path, destination)

    with pytest.raises(ReconstructionError, match="Reconstrução concluída com erros"):
        ReconstructionService.execute(plan)

    assert stale_file.read_text(encoding="utf-8") == "do not delete after failure"


def test_source_inside_destination_is_rejected_before_cleanup(tmp_path: Path) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()
    source_archive = destination / "input.zip"
    with zipfile.ZipFile(source_archive, "w") as archive:
        archive.writestr("good.bin", b"valid")
    stale_file = destination / "existing.txt"
    stale_file.write_text("keep", encoding="utf-8")
    filter_path = tmp_path / "filter.json"
    filter_path.write_text(
        json.dumps(
            {
                "format": "SERM-FILTER-V1",
                "source": "mame",
                "system": "arcade",
                "evidence": [
                    {
                        "machine_name": "pacman",
                        "status": "CURRENT",
                        "archive_path": str(source_archive),
                        "archive_member": "good.bin",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    plan = ReconstructionService.plan(filter_path, destination)

    with pytest.raises(ReconstructionError, match="Arquivo de origem dentro"):
        ReconstructionService.execute(plan)

    assert source_archive.is_file()
    assert stale_file.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize(
    ("source_name", "filter_format", "bios_filter_key"),
    (
        ("No-Intro", "SERM-FILTER-V2", "bios_only"),
        ("Redump", "SERM-FILTER-V2", "bios_only"),
        ("RetroArch", "SERM-FILTER-V2", "bios_only"),
        ("BizHawk", "SERM-FILTER-V2", "bios_only"),
    ),
)
def test_no_intro_bios_filter_reconstructs_only_verified_bios_files(
    tmp_path: Path, source_name: str, filter_format: str, bios_filter_key: str
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    source_archive = source / "system.zip"
    with zipfile.ZipFile(source_archive, "w") as archive:
        archive.writestr("bios/system.rom", b"verified bios")
        archive.writestr("game.bin", b"ordinary game")
        archive.writestr("invalid.rom", b"wrong dump")
    filter_path = tmp_path / "filter.json"
    filter_path.write_text(
        json.dumps(
            {
                "format": filter_format,
                "source": source_name,
                "system": "Nintendo System",
                "filters": {bios_filter_key: True},
                "evidence": [
                    {
                        "machine_name": "[BIOS] System",
                        "rom_name": "bios/system.rom",
                        "status": "CURRENT",
                        "categories": ["type:bios"],
                        "archive_path": str(source_archive),
                        "archive_member": "bios/system.rom",
                    },
                    {
                        "machine_name": "[BIOS] System",
                        "rom_name": "invalid.rom",
                        "status": "WRONG",
                        "categories": ["type:bios"],
                        "archive_path": str(source_archive),
                        "archive_member": "invalid.rom",
                    },
                    {
                        "machine_name": "Game",
                        "rom_name": "game.bin",
                        "status": "CURRENT",
                        "categories": ["type:game"],
                        "archive_path": str(source_archive),
                        "archive_member": "game.bin",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = ReconstructionService.plan(filter_path, destination)

    assert plan.item_count == 1
    assert plan.items[0].kind == "firmware_archive"
    assert Path(plan.items[0].output_path) == destination / "bios" / "system.rom"
    ReconstructionService.execute(plan)

    assert (destination / "bios" / "system.rom").read_bytes() == b"verified bios"
    assert sorted(path.relative_to(destination).as_posix() for path in destination.rglob("*")) == [
        "bios",
        "bios/system.rom",
    ]
    with zipfile.ZipFile(source_archive) as archive:
        assert set(archive.namelist()) == {"bios/system.rom", "game.bin", "invalid.rom"}


def test_legacy_include_bios_rebuilds_games_and_extracts_bios(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    source_archive = source / "system.zip"
    with zipfile.ZipFile(source_archive, "w") as archive:
        archive.writestr("bios/system.rom", b"verified bios")
        archive.writestr("game.bin", b"ordinary game")
    filter_path = tmp_path / "filter.json"
    filter_path.write_text(
        json.dumps(
            {
                "format": "SERM-FILTER-V1",
                "source": "No-Intro",
                "system": "Nintendo System",
                "filters": {"include_bios": True},
                "evidence": [
                    {
                        "machine_name": "[BIOS] System",
                        "rom_name": "bios/system.rom",
                        "status": "CURRENT",
                        "categories": ["type:bios"],
                        "archive_path": str(source_archive),
                        "archive_member": "bios/system.rom",
                    },
                    {
                        "machine_name": "Game",
                        "rom_name": "game.bin",
                        "status": "CURRENT",
                        "categories": ["type:game"],
                        "archive_path": str(source_archive),
                        "archive_member": "game.bin",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = ReconstructionService.plan(filter_path, destination)

    assert plan.item_count == 2
    assert {item.kind for item in plan.items} == {"archive", "firmware_archive"}
    ReconstructionService.execute(plan)

    assert (destination / "bios" / "system.rom").read_bytes() == b"verified bios"
    with zipfile.ZipFile(destination / "system.zip") as archive:
        assert archive.namelist() == ["game.bin"]


def test_ares_firmware_filter_uses_shared_reconstruction_executor(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    source_archive = source / "ares-firmware.zip"
    with zipfile.ZipFile(source_archive, "w") as archive:
        archive.writestr("download/colecovision.rom", b"ares bios")
    filter_path = tmp_path / "filter.json"
    filter_path.write_text(
        json.dumps(
            {
                "format": "SERM-FILTER-V1",
                "source": "ares-firmware",
                "system": "ares",
                "evidence": [
                    {
                        "output_name": "colecovision.rom",
                        "archive_path": str(source_archive),
                        "archive_member": "download/colecovision.rom",
                        "sha256": "verified-by-ares-adapter",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = ReconstructionService.plan(filter_path, destination)
    result = ReconstructionService.execute(plan)

    assert result["created_count"] == 1
    assert (destination / "colecovision.rom").read_bytes() == b"ares bios"
    with zipfile.ZipFile(source_archive) as archive:
        assert archive.read("download/colecovision.rom") == b"ares bios"
