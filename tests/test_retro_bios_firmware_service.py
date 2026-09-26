import hashlib
import json
import zipfile
import zlib
from pathlib import Path

import pytest

from serm_v2.services import ares_firmware_service
from serm_v2.services.ares_firmware_service import AresFirmwareService
from serm_v2.services.ares_firmware_service import AresFirmwareScan
from serm_v2.services.reconstruction_service import ReconstructionError, ReconstructionService


def test_catalog_selects_mapped_emulator_and_preserves_hash_metadata() -> None:
    payload = {
        "generated_at": "2026-09-20",
        "items": [
            {
                "id": "mupen64plus_next",
                "profile": {
                    "emulator": "Mupen64Plus-Next",
                    "profiled_date": "2026-09-20",
                    "files": [
                        {
                            "name": "IPL.n64",
                            "system": "nintendo-64",
                            "md5": "0123456789abcdef0123456789abcdef",
                            "size": 4096,
                            "required": False,
                            "validation": ["md5", "size"],
                        }
                    ],
                },
            },
            {
                "id": "mame",
                "profile": {
                    "emulator": "MAME",
                    "files": [{"name": "mame-bios.zip", "sha256": "a" * 64}],
                },
            },
        ],
    }

    entries, version = AresFirmwareService._parse_catalog(payload, emulator="rmg")

    assert version == "2026-09-20"
    assert len(entries) == 1
    assert entries[0].name == "IPL.n64"
    assert entries[0].md5 == "0123456789abcdef0123456789abcdef"
    assert entries[0].validation == ("md5", "size")
    assert entries[0].output_path == "IPL.n64"


def test_retroarch_catalog_aggregates_libretro_profiles_but_never_mame() -> None:
    payload = {
        "items": [
            {
                "id": "snes9x",
                "profile": {
                    "emulator": "Snes9x",
                    "type": "libretro",
                    "files": [{"name": "dsp1.rom", "sha1": "b" * 40}],
                },
            },
            {
                "id": "mame",
                "profile": {
                    "emulator": "MAME",
                    "type": "libretro",
                    "files": [{"name": "mame.zip", "sha256": "c" * 64}],
                },
            },
            {
                "id": "mame_2016",
                "profile": {
                    "emulator": "MAME 2003 Plus",
                    "type": "libretro",
                    "files": [{"name": "mame2016.zip", "sha256": "f" * 64}],
                },
            },
            {
                "id": "duckstation",
                "profile": {
                    "emulator": "DuckStation",
                    "type": "standalone",
                    "files": [{"name": "scph.bin", "md5": "d" * 32}],
                },
            },
        ]
    }

    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="retroarch")

    assert [entry.name for entry in entries] == ["dsp1.rom"]


def test_unmapped_emulator_does_not_borrow_another_profile() -> None:
    payload = {
        "items": [
            {
                "id": "ares",
                "profile": {
                    "emulator": "ares",
                    "files": [{"name": "bios.rom", "sha256": "e" * 64}],
                },
            }
        ]
    }

    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="bizhawk")

    assert entries == ()


def test_scan_matches_renamed_loose_and_zip_content_by_catalog_hashes(tmp_path) -> None:
    loose_data = b"duckstation bios"
    zipped_data = b"altirra firmware"
    archive_path = tmp_path / "unknown_bundle.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("renamed/member.rom", zipped_data)
    loose_path = tmp_path / "renamed-file.bin"
    loose_path.write_bytes(loose_data)
    payload = {
        "items": [
            {
                "id": "duckstation",
                "profile": {
                    "emulator": "DuckStation",
                    "files": [
                        {
                            "name": "scph1000.bin",
                            "md5": hashlib.md5(loose_data, usedforsecurity=False).hexdigest(),
                            "size": len(loose_data),
                        }
                    ],
                },
            },
            {
                "id": "altirra",
                "profile": {
                    "emulator": "Altirra",
                    "files": [
                        {
                            "name": "atari.rom",
                            "crc32": f"{zlib.crc32(zipped_data):08x}",
                            "size": len(zipped_data),
                        }
                    ],
                },
            },
        ]
    }
    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="duckstation")
    altirra_entries, _altirra_version = AresFirmwareService._parse_catalog(
        payload, emulator="altirra"
    )

    duckstation_scan = AresFirmwareService.scan(tmp_path, entries, emulator="duckstation")
    altirra_scan = AresFirmwareService.scan(tmp_path, altirra_entries, emulator="altirra")

    assert duckstation_scan.matches[0].entry.name == "scph1000.bin"
    assert duckstation_scan.matches[0].path == str(loose_path)
    assert altirra_scan.matches[0].entry.name == "atari.rom"
    assert altirra_scan.matches[0].path == str(archive_path)
    assert altirra_scan.matches[0].archive_member == "renamed/member.rom"


def test_reconstruction_preserves_unrelated_emulator_install_files(tmp_path: Path) -> None:
    source = tmp_path / "verified-bios.bin"
    source.write_bytes(b"verified BIOS")
    destination = tmp_path / "retroarch"
    destination.mkdir()
    executable = destination / "retroarch.exe"
    executable.write_bytes(b"emulator executable")
    filter_path = tmp_path / "firmware-filter.json"
    filter_path.write_text(
        json.dumps(
            {
                "format": "SERM-FILTER-V2",
                "source": "retroarch",
                "system": "retroarch",
                "filters": {"bios_only": True, "preserve_destination_files": True},
                "evidence": [
                    {
                        "output_name": "system/bios.bin",
                        "path": str(source),
                        "status": "CURRENT",
                        "categories": ["type:bios"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    unrelated = destination / "keep-me.txt"
    unrelated.write_text("unrelated", encoding="utf-8")

    plan = ReconstructionService.plan(filter_path, destination)
    ReconstructionService.execute(plan)

    assert executable.read_bytes() == b"emulator executable"
    assert (destination / "system" / "bios.bin").read_bytes() == b"verified BIOS"
    assert unrelated.read_text(encoding="utf-8") == "unrelated"


def test_firmware_plan_rejects_conflicting_catalog_paths(tmp_path: Path) -> None:
    first = tmp_path / "bios-one.bin"
    second = tmp_path / "bios-two.bin"
    first.write_bytes(b"first BIOS")
    second.write_bytes(b"second BIOS")
    destination = tmp_path / "destination"
    filter_path = tmp_path / "firmware-filter.json"
    filter_path.write_text(
        json.dumps(
            {
                "format": "SERM-FILTER-V2",
                "source": "retroarch",
                "system": "retroarch",
                "filters": {"bios_only": True, "preserve_destination_files": True},
                "evidence": [
                    {
                        "output_name": "system/shared.bin",
                        "path": str(first),
                        "status": "CURRENT",
                        "categories": ["type:bios"],
                    },
                    {
                        "output_name": "system/shared.bin",
                        "path": str(second),
                        "status": "CURRENT",
                        "categories": ["type:bios"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ReconstructionError, match="Conflito de BIOS/firmware"):
        ReconstructionService.plan(filter_path, destination)


def test_catalog_cleanup_removes_only_invalid_known_firmware(tmp_path: Path) -> None:
    valid_data = b"valid console BIOS"
    invalid_data = b"wrong dump"
    valid_file = tmp_path / "system" / "bios.bin"
    invalid_file = tmp_path / "other" / "bios.bin"
    unknown_file = tmp_path / "retroarch.exe"
    valid_file.parent.mkdir()
    invalid_file.parent.mkdir()
    valid_file.write_bytes(valid_data)
    invalid_file.write_bytes(invalid_data)
    unknown_file.write_bytes(b"emulator")
    payload = {
        "items": [
            {
                "id": "testemu",
                "profile": {
                    "emulator": "Test Emulator",
                    "files": [
                        {
                            "name": "bios.bin",
                            "sha256": hashlib.sha256(valid_data).hexdigest(),
                        }
                    ],
                },
            }
        ]
    }
    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="testemu")

    removed = AresFirmwareService.clean_invalid_files(tmp_path, entries)

    assert removed == (invalid_file,)
    assert valid_file.read_bytes() == valid_data
    assert unknown_file.read_bytes() == b"emulator"


def test_scan_matches_profiles_without_checksums_by_filename(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    firmware = source / "kick13.rom"
    firmware.write_bytes(b"amiga firmware")
    payload = {
        "items": [
            {
                "id": "amiberry",
                "profile": {
                    "emulator": "Amiberry",
                    "files": [{"name": "kick13.rom", "size": 14}],
                },
            }
        ]
    }
    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="amiberry")

    scan = AresFirmwareService.scan(source, entries, emulator="amiberry")

    assert len(scan.matches) == 1
    assert scan.matches[0].path == str(firmware)
    assert scan.missing == ()
    assert scan.files_examined == 1
    assert not entries[0].is_verifiable

def test_ares_filter_file_requests_preserving_destination(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ares_firmware_service, "scans_root", lambda: tmp_path / "scans")
    scan = AresFirmwareScan("v1", str(tmp_path / "source"), (), (), 0)

    filter_path = AresFirmwareService.write_filter_file(scan, ())
    payload = json.loads(filter_path.read_text(encoding="utf-8"))

    assert payload["filters"]["preserve_destination_files"] is True
