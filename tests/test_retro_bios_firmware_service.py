import hashlib
import io
import json
import zipfile
import zlib
from pathlib import Path

import pytest
from serm_v2.services import ares_firmware_service
from serm_v2.services.ares_firmware_service import (
    AresFirmwareEntry,
    AresFirmwareMatch,
    AresFirmwareScan,
    AresFirmwareService,
)
from serm_v2.services.reconstruction_service import (
    ReconstructionError,
    ReconstructionService,
)


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


def test_scan_marks_catalog_named_wrong_hash_as_invalid(tmp_path) -> None:
    wrong = b"wrong firmware"
    path = tmp_path / "bios.bin"
    path.write_bytes(wrong)
    expected = b"correct firmware"
    payload = {
        "items": [
            {
                "id": "ares",
                "profile": {
                    "emulator": "ares",
                    "files": [
                        {
                            "name": "bios.bin",
                            "sha256": hashlib.sha256(expected).hexdigest(),
                            "size": len(expected),
                        }
                    ],
                },
            }
        ]
    }
    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="ares")

    scan = AresFirmwareService.scan(tmp_path, entries, emulator="ares")

    assert scan.matches == ()
    assert len(scan.invalid) == 1
    assert scan.invalid[0].entry.name == "bios.bin"
    assert scan.invalid[0].match_mode == "invalid"
    assert scan.missing == (entries[0],)


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



def test_ares_neo_geo_zip_satisfies_aes_and_mvs_members(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    archive_path = source / "neogeo.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("neo-epo.bin", b"aes bios")
        archive.writestr("sp-45.sp1", b"mvs bios")

    payload = {
        "items": [{
            "id": "ares",
            "profile": {
                "emulator": "ares",
                "files": [
                    {"name": "neo-epo.bin", "system": "neo-geo", "required": True},
                    {"name": "sp-45.sp1", "system": "neo-geo", "required": True},
                ],
            },
        }]
    }
    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="ares")

    scan = AresFirmwareService.scan(source, entries, emulator="ares")

    assert {match.entry.name for match in scan.matches} == {"neo-epo.bin", "sp-45.sp1"}
    assert all(match.archive_member for match in scan.matches)
    assert all(match.match_mode == "archive" for match in scan.matches)
    assert scan.missing == ()
    assert {entry.container_name for entry in entries} == {"neogeo.zip"}


def test_catalog_archive_entries_require_the_declared_zip(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    loose = source / "bios.bin"
    loose.write_bytes(b"archive BIOS")
    archive_path = source / "required.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("bios.bin", b"archive BIOS")

    payload = {
        "items": [{
            "id": "testemu",
            "profile": {
                "emulator": "Test",
                "files": [{
                    "name": "bios.bin",
                    "archive": "required.zip",
                    "sha256": hashlib.sha256(b"archive BIOS").hexdigest(),
                }],
            },
        }]
    }
    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="testemu")

    scan = AresFirmwareService.scan(source, entries, emulator="testemu")

    assert len(scan.matches) == 1
    assert scan.matches[0].archive_member == "bios.bin"
    assert scan.matches[0].path == str(archive_path)
    assert scan.matches[0].match_mode == "hash"
    assert entries[0].archive_required is True


def test_scan_recognizes_the_zip_container_itself(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    archive_path = source / "bios.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("bios.bin", b"payload")

    data = archive_path.read_bytes()
    payload = {
        "items": [{
            "id": "testemu",
            "profile": {
                "emulator": "Test",
                "files": [{
                    "name": "bios.zip",
                    "sha256": hashlib.sha256(data).hexdigest(),
                }],
            },
        }]
    }
    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="testemu")

    scan = AresFirmwareService.scan(source, entries, emulator="testemu")

    assert len(scan.matches) == 1
    assert scan.matches[0].entry.name == "bios.zip"
    assert scan.matches[0].archive_member is None
    assert scan.matches[0].match_mode == "hash"




def test_scan_requires_retroarch_nested_output_path_even_when_hash_matches(tmp_path: Path) -> None:
    source = tmp_path / "system"
    source.mkdir()
    correct = source / "dc"
    correct.mkdir()
    data = b"dreamcast bios"
    wrong = source / "dc_boot.bin"
    wrong.write_bytes(data)

    digest = hashlib.sha256(data).hexdigest()
    payload = {
        "items": [{
            "id": "retroarch",
            "profile": {
                "emulator": "RetroArch",
                "type": "libretro",
                "files": [{
                    "name": "dc_boot.bin",
                    "path": "dc/dc_boot.bin",
                    "sha256": digest,
                }],
            },
        }],
    }
    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="retroarch")
    scan = AresFirmwareService.scan(source, entries, emulator="retroarch")

    assert scan.matches == ()
    assert scan.missing == entries


def test_bizhawk_sha1_match_is_accepted_from_firmware_root(tmp_path: Path) -> None:
    source = tmp_path / "Firmware"
    source.mkdir()
    data = b"bizhawk firmware"
    firmware = source / "boot.rom"
    firmware.write_bytes(data)

    payload = {
        "items": [{
            "id": "bizhawk",
            "profile": {
                "emulator": "BizHawk",
                "files": [{
                    "name": "boot.rom",
                    "sha1": hashlib.sha1(data, usedforsecurity=False).hexdigest(),
                }],
            },
        }],
    }
    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="bizhawk")
    scan = AresFirmwareService.scan(source, entries, emulator="bizhawk")

    assert len(scan.matches) == 1
    assert scan.matches[0].match_mode == "hash"
    assert scan.missing == ()


def test_bizhawk_wrong_sha1_by_name_is_invalid_and_missing(tmp_path: Path) -> None:
    source = tmp_path / "Firmware"
    source.mkdir()
    firmware = source / "boot.rom"
    firmware.write_bytes(b"wrong dump")

    payload = {
        "items": [{
            "id": "bizhawk",
            "profile": {
                "emulator": "BizHawk",
                "files": [{
                    "name": "boot.rom",
                    "sha1": "0" * 40,
                }],
            },
        }],
    }
    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="bizhawk")
    scan = AresFirmwareService.scan(source, entries, emulator="bizhawk")

    assert scan.matches == ()
    assert scan.invalid[0].match_mode == "invalid"
    assert scan.invalid[0].entry.name == "boot.rom"
    assert scan.missing[0].name == "boot.rom"




def test_retroarch_info_is_structural_authority(tmp_path: Path) -> None:
    from serm_v2.services.retroarch_bios_service import RetroArchBiosService

    install = tmp_path / "retroarch"
    system = install / "system"
    info = install / "info"
    system.mkdir(parents=True)
    info.mkdir()
    (info / "bluemsx_libretro.info").write_text(
        'firmware_count = 2\n'
        'firmware0_path = "Databases/msxromdb.xml"\n'
        'firmware0_opt = "false"\n'
        'firmware1_path = "Machines/Shared Roms/MSX.rom"\n'
        'firmware1_opt = "false"\n',
        encoding="utf-8",
    )
    entries = (
        AresFirmwareEntry(
            name="msxromdb.xml",
            system="MSX",
            description="database",
            required=True,
            sha1=hashlib.sha1(b"db", usedforsecurity=False).hexdigest(),
            output_path="Databases/msxromdb.xml",
            profile_id="bluemsx",
        ),
        AresFirmwareEntry(
            name="MSX.rom",
            system="MSX",
            description="machines",
            required=True,
            sha1=hashlib.sha1(b"rom", usedforsecurity=False).hexdigest(),
            output_path="Machines/Shared Roms/MSX.rom",
            profile_id="bluemsx",
        ),
    )
    result = RetroArchBiosService._firmware_from_info(
        info / "bluemsx_libretro.info",
        RetroArchBiosService._parse_info(info / "bluemsx_libretro.info"),
        entries,
    )
    assert [entry.output_path for entry in result] == [
        "Databases/msxromdb.xml",
        "Machines/Shared Roms/MSX.rom",
    ]
    assert all(entry.required for entry in result)


def test_retroarch_info_optional_firmware_is_not_required(tmp_path: Path) -> None:
    from serm_v2.services.retroarch_bios_service import RetroArchBiosService

    info = tmp_path / "genesis_plus_gx_libretro.info"
    info.write_text(
        'firmware_count = 2\n'
        'firmware0_path = "bios_MD.bin"\n'
        'firmware0_opt = "true"\n'
        'firmware1_path = "bios_CD_E.bin"\n'
        'firmware1_opt = "true"\n',
        encoding="utf-8",
    )
    result = RetroArchBiosService._firmware_from_info(
        info,
        RetroArchBiosService._parse_info(info),
        (),
    )
    assert len(result) == 2
    assert all(not entry.required for entry in result)


def test_retroarch_info_without_firmware_does_not_create_bios(tmp_path: Path) -> None:
    from serm_v2.services.retroarch_bios_service import RetroArchBiosService

    info = tmp_path / "nes_libretro.info"
    info.write_text(
        'systemname = "Nintendo Entertainment System"\n'
        'systemid = "nes"\n',
        encoding="utf-8",
    )
    assert RetroArchBiosService._firmware_from_info(
        info, RetroArchBiosService._parse_info(info), ()
    ) == []





def test_ares_source_catalog_matches_firmware_declarations() -> None:
    entries = AresFirmwareService._ares_source_entries()

    assert len(entries) == 39
    assert sum(entry.is_verifiable for entry in entries) == 34
    assert len({entry.key for entry in entries}) == len(entries)
    assert {
        (entry.system, entry.region)
        for entry in entries
        if entry.system == "Saturn"
    } == {
        ("Saturn", "US"),
        ("Saturn", "Japan"),
        ("Saturn", "Europe"),
    }


def test_ares_destination_scan_validates_physical_destination_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = next(
        item
        for item in AresFirmwareService._ares_source_entries()
        if item.system == "Famicom Disk System"
    )
    destination = tmp_path / "destination"
    destination.mkdir()
    firmware = destination / "BIOS"
    firmware.write_bytes(b"fds")

    def fake_hash_file(path: Path, algorithms: frozenset[str]) -> dict[str, object]:
        assert path == firmware
        assert algorithms == {"sha256"}
        return {
            "size": 3,
            "sha256": entry.sha256,
            "sha1": "",
            "md5": "",
            "crc32": "",
        }

    monkeypatch.setattr(
        AresFirmwareService, "_hash_file_for_algorithms", staticmethod(fake_hash_file)
    )
    result = AresFirmwareService.scan(
        destination,
        (entry,),
        catalog_version="ARES source test",
        emulator="ares",
    )

    assert result.source_directory == str(destination.resolve())
    assert result.missing == ()
    assert len(result.matches) == 1
    assert result.matches[0].path == str(firmware)
    assert result.matches[0].match_mode == "hash"


def test_scan_uses_only_hash_algorithms_declared_by_catalog() -> None:
    entry = AresFirmwareEntry(
        name="bios.bin",
        system="Test",
        description="test",
        required=True,
        sha256="a" * 64,
    )

    assert AresFirmwareService._required_hash_algorithms((entry,)) == {"sha256"}
    identity = AresFirmwareService._hash_stream(io.BytesIO(b"payload"), {"sha256"})
    assert identity["sha256"] == hashlib.sha256(b"payload").hexdigest()
    assert identity["sha1"] == ""
    assert identity["md5"] == ""
    assert identity["crc32"] == ""


def test_ares_configured_scan_uses_settings_assignments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fds = next(
        entry
        for entry in AresFirmwareService._ares_source_entries()
        if entry.system == "Famicom Disk System"
    )
    saturn = next(
        entry
        for entry in AresFirmwareService._ares_source_entries()
        if entry.system == "Saturn" and entry.region == "US"
    )
    fds_path = tmp_path / "fds.bin"
    saturn_path = tmp_path / "saturn.bin"
    fds_path.write_bytes(b"fds")
    saturn_path.write_bytes(b"saturn")
    settings = tmp_path / "settings.bml"
    settings.write_text(
        "Famicom Disk System:\n"
        "  Firmware:\n"
        f"    BIOS.Japan: {fds_path}\n"
        "Saturn:\n"
        "  Firmware:\n"
        f"    BIOS.US: {saturn_path}\n",
        encoding="utf-8",
    )

    real_hash_file = AresFirmwareService._hash_file

    def fake_hash_file(path: Path) -> dict[str, object]:
        if path == fds_path:
            return {
                "size": 3,
                "sha256": fds.sha256,
                "sha1": "",
                "md5": "",
                "crc32": "",
            }
        return real_hash_file(path)

    monkeypatch.setattr(AresFirmwareService, "_hash_file", staticmethod(fake_hash_file))
    result = AresFirmwareService.scan_configured(
        settings,
        (fds, saturn),
        catalog_version="ARES source test",
    )

    assert {match.entry.system for match in result.matches} == {
        "Famicom Disk System",
        "Saturn",
    }
    assert result.missing == ()
    assert result.invalid == ()
    assert {match.match_mode for match in result.matches} == {"hash", "configured"}


def test_ares_configured_scan_reports_hash_mismatch(tmp_path: Path) -> None:
    fds = next(
        entry
        for entry in AresFirmwareService._ares_source_entries()
        if entry.system == "Famicom Disk System"
    )
    firmware = tmp_path / "wrong.bin"
    firmware.write_bytes(b"wrong")
    settings = tmp_path / "settings.bml"
    settings.write_text(
        "Famicom Disk System:\n"
        "  Firmware:\n"
        f"    BIOS.Japan: {firmware}\n",
        encoding="utf-8",
    )

    result = AresFirmwareService.scan_configured(
        settings,
        (fds,),
        catalog_version="ARES source test",
    )

    assert result.matches == ()
    assert result.missing == ()
    assert len(result.invalid) == 1
    assert result.invalid[0].match_mode == "invalid"


def test_ares_merge_does_not_import_retro_bios_only_entries() -> None:
    source_only = AresFirmwareEntry(
        name="not-from-ares.bin",
        system="RetroBIOS only",
        description="extra",
        required=True,
        sha256="a" * 64,
    )

    merged = AresFirmwareService._merge_ares_source_entries((source_only,))

    assert all(entry.system != "RetroBIOS only" for entry in merged)
    assert len(merged) == 39


def test_ares_source_catalog_contains_exact_firmware_hashes() -> None:
    entries = AresFirmwareService._ares_source_entries()
    by_system = {(entry.system, entry.description): entry for entry in entries}

    fds = next(entry for entry in entries if entry.system == "Famicom Disk System")
    assert fds.sha256 == "fdc1a76e654feea993fcb38366e05ee5f4eb641f86fe6bebaeefd412e112dd72"

    laser_jp = next(
        entry for entry in entries
        if entry.system == "LaserActive (SEGA PAC)" and entry.description.endswith("NTSC-J v1.02")
    )
    assert laser_jp.sha256 == "dca942d977217f703d8d1c6eb1aeb6b32c78ecc421486bbb46c459d385161c94"

    laser_us = next(
        entry for entry in entries
        if entry.system == "LaserActive (SEGA PAC)" and entry.description.endswith("NTSC-U v1.04")
    )
    assert laser_us.sha256 == "e89b5a319f66406611ec82fe5c4aa6827c175a05135bd7bd177366cba0465021"
    assert by_system


def test_ares_source_catalog_identifies_neo_geo_archive_members() -> None:
    entries = AresFirmwareService._ares_source_entries()
    aes = next(entry for entry in entries if entry.system == "Neo Geo AES")
    mvs = next(entry for entry in entries if entry.system == "Neo Geo MVS")

    assert aes.name == "neo-epo.bin"
    assert aes.container_name == "neogeo.zip"
    assert not aes.is_verifiable
    assert mvs.name == "sp-45.sp1"
    assert mvs.container_name == "neogeo.zip"
    assert not mvs.is_verifiable


def test_ares_source_hash_does_not_fall_back_to_filename(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    bios = source / "BIOS"
    bios.write_bytes(b"wrong ARES dump")
    entry = next(
        entry for entry in AresFirmwareService._ares_source_entries()
        if entry.system == "Famicom Disk System"
    )

    scan = AresFirmwareService.scan(source, (entry,), emulator="ares")

    assert scan.matches == ()
    assert scan.missing == (entry,)


def test_ares_source_entries_are_merged_with_retrobios(monkeypatch) -> None:
    retrobios_entry = AresFirmwareEntry(
        name="BIOS",
        system="Famicom Disk System",
        description="RetroBIOS",
        required=True,
        sha256="0" * 64,
    )
    merged = AresFirmwareService._merge_ares_source_entries((retrobios_entry,))

    fds = [entry for entry in merged if entry.system == "Famicom Disk System"]
    assert len(fds) == 1
    assert fds[0].sha256 == "fdc1a76e654feea993fcb38366e05ee5f4eb641f86fe6bebaeefd412e112dd72"
    assert fds[0].profile_id == "ares-source"


def test_ares_neo_geo_direct_files_remain_supported(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "neo-epo.bin").write_bytes(b"aes bios")
    (source / "sp-45.sp1").write_bytes(b"mvs bios")

    payload = {
        "items": [{
            "id": "ares",
            "profile": {
                "emulator": "ares",
                "files": [
                    {"name": "neo-epo.bin", "system": "neo-geo", "required": True},
                    {"name": "sp-45.sp1", "system": "neo-geo", "required": True},
                ],
            },
        }]
    }
    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="ares")

    scan = AresFirmwareService.scan(source, entries, emulator="ares")

    assert {match.entry.name for match in scan.matches} == {"neo-epo.bin", "sp-45.sp1"}
    assert all(match.match_mode == "name" for match in scan.matches)
    assert scan.missing == ()


def test_ares_neo_geo_archive_state_is_explicit() -> None:
    payload = {
        "items": [{
            "id": "ares",
            "profile": {
                "emulator": "ares",
                "files": [{"name": "neo-epo.bin", "system": "neo-geo", "required": True}],
            },
        }]
    }
    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="ares")

    entry = entries[0]
    assert entry.container_name == "neogeo.zip"
    assert entry.panel_state(True, match_mode="archive") == "PRESENTE — ARQUIVO COMPATÍVEL"
    assert "neogeo.zip" in entry.panel_state_detail(True, match_mode="archive")


def test_enrich_entries_from_database_marks_repository_and_release_availability() -> None:
    entry = AresFirmwareService._parse_catalog(
        {
            "generated_at": "2026-09-26",
            "items": [
                {
                    "id": "testemu",
                    "profile": {
                        "emulator": "Test Emulator",
                        "files": [
                            {
                                "name": "bios.bin",
                                "sha256": "a" * 64,
                                "required": True,
                            }
                        ],
                    },
                }
            ],
        },
        emulator="testemu",
    )[0][0]

    database = {
        "files": [
            {
                "name": "bios.bin",
                "sha256": "a" * 64,
                "repo_path": "bios/Test/bios.bin",
            },
            {
                "name": "large.bin",
                "sha256": "b" * 64,
                "release_asset": "large.bin",
            },
        ]
    }

    enriched = AresFirmwareService._enrich_entries_from_database((entry,), database)

    assert enriched[0].catalog_available
    assert enriched[0].repository_path == "bios/Test/bios.bin"
    assert enriched[0].availability_label == "DISPONÍVEL (REPOSITÓRIO)"


def test_database_records_ignore_hash_only_entries_without_storage() -> None:
    records = AresFirmwareService._database_records(
        {
            "files": [
                {"name": "missing.bin", "sha256": "a" * 64},
                {"name": "available.bin", "sha256": "b" * 64, "repo_path": "bios/available.bin"},
            ]
        }
    )

    assert len(records) == 1
    assert records[0]["name"] == "available.bin"


def test_reconstruction_keeps_neo_geo_bios_inside_neogeo_zip(tmp_path: Path) -> None:
    source = tmp_path / "neogeo.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("neo-epo.bin", b"aes bios")
        archive.writestr("sp-45.sp1", b"mvs bios")
    destination = tmp_path / "destination"
    filter_path = tmp_path / "firmware-filter.json"
    filter_path.write_text(
        json.dumps(
            {
                "format": "SERM-FILTER-V2",
                "source": "ares-firmware",
                "system": "ares",
                "filters": {"verification": "catalog", "preserve_destination_files": True},
                "evidence": [
                    {
                        "output_name": "neo-epo.bin",
                        "path": str(source),
                        "archive_path": str(source),
                        "archive_member": "neo-epo.bin",
                        "container_output_name": "neogeo.zip",
                        "status": "CURRENT",
                    },
                    {
                        "output_name": "sp-45.sp1",
                        "path": str(source),
                        "archive_path": str(source),
                        "archive_member": "sp-45.sp1",
                        "container_output_name": "neogeo.zip",
                        "status": "CURRENT",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = ReconstructionService.plan(filter_path, destination)
    result = ReconstructionService.execute(plan)

    assert result["created_count"] == 1
    rebuilt = destination / "neogeo.zip"
    with zipfile.ZipFile(rebuilt) as archive:
        assert archive.namelist() == ["neo-epo.bin", "sp-45.sp1"]
        assert archive.read("neo-epo.bin") == b"aes bios"
        assert archive.read("sp-45.sp1") == b"mvs bios"


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


def test_pack_name_for_path_identifies_platform_pack(tmp_path: Path) -> None:
    packs = tmp_path / "retrobios_packs"
    source = packs / "Nintendo 64" / "firmware"
    source.mkdir(parents=True)
    bios = source / "IPL.n64"
    bios.write_bytes(b"bios")

    from serm_v2.services.retrobios_pack_service import RetroBiosPackService

    assert (
        RetroBiosPackService.pack_name_for_path(bios, source=packs)
        == "Nintendo 64_BIOS_Pack.zip"
    )
    assert RetroBiosPackService.pack_name_for_path(bios, source=tmp_path) == ""



def test_ares_filter_file_requests_preserving_destination(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ares_firmware_service, "scans_root", lambda: tmp_path / "scans")
    scan = AresFirmwareScan("v1", str(tmp_path / "source"), (), (), 0)

    filter_path = AresFirmwareService.write_filter_file(scan, ())
    payload = json.loads(filter_path.read_text(encoding="utf-8"))

    assert payload["filters"]["preserve_destination_files"] is True

def test_enrich_entries_from_gaps_marks_emulator_coverage_gap() -> None:
    entry = AresFirmwareService._parse_catalog(
        {"items": [{"id": "testemu", "profile": {"emulator": "Test Emulator", "files": [{"name": "bios.bin", "system": "test-system", "sha256": "a" * 64}]}}]},
        emulator="testemu",
    )[0][0]
    gaps = {"items": [
        {"layer": "platform", "name": "bios.bin", "system": "test-system", "status": "missing"},
        {"layer": "emulator", "name": "bios.bin", "emulator": "Test Emulator", "system": "test-system", "in_repo": True, "status": "bios", "required": True, "reason": "Arquivo usado pelo emulador, mas não declarado pela camada da plataforma."},
    ]}
    enriched = AresFirmwareService._enrich_entries_from_gaps((entry,), gaps)
    assert enriched[0].gap_layer == "emulator"
    assert enriched[0].gap_status == "bios"
    assert enriched[0].gap_in_repo is True
    assert enriched[0].coverage_label == "LACUNA DE COBERTURA"
    assert "não declarado" in enriched[0].gap_reason


def test_gap_records_ignore_platform_layer() -> None:
    records = AresFirmwareService._gap_records({"items": [{"layer": "platform", "name": "platform.bin"}, {"layer": "emulator", "name": "emulator.bin"}]})
    assert len(records) == 1
    assert records[0]["name"] == "emulator.bin"

def test_distribution_label_distinguishes_release_repository_and_gap() -> None:
    base = AresFirmwareService._parse_catalog(
        {"items": [{"id": "testemu", "profile": {"emulator": "Test", "files": [{"name": "bios.bin", "sha256": "a" * 64}]}}]},
        emulator="testemu",
    )[0][0]
    database = {"files": [{"name": "bios.bin", "sha256": "a" * 64, "release_asset": "bios.bin"}]}
    release = AresFirmwareService._enrich_entries_from_database((base,), database)[0]
    assert release.distribution_label == "OBTENÇÃO: RELEASE"

    repository = AresFirmwareService._enrich_entries_from_database(
        (base,), {"files": [{"name": "bios.bin", "sha256": "a" * 64, "repo_path": "bios/bios.bin"}]}
    )[0]
    assert repository.distribution_label == "OBTENÇÃO: REPOSITÓRIO"

    gap = AresFirmwareService._enrich_entries_from_gaps(
        (base,), {"items": [{"layer": "emulator", "name": "bios.bin", "system": "", "status": "bios", "in_repo": False}]}
    )[0]
    assert gap.distribution_label == "OBTENÇÃO: LACUNA"


def test_panel_state_classifies_required_available_and_optional_entries() -> None:
    payload = {
        "items": [{
            "id": "testemu",
            "profile": {
                "emulator": "Test",
                "files": [
                    {"name": "valid.bin", "sha256": "a" * 64, "required": True},
                    {"name": "plain.bin", "required": True},
                    {"name": "missing.bin", "sha256": "b" * 64, "required": True},
                    {"name": "hle.bin", "required": False},
                ],
            },
        }]
    }
    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="testemu")
    database = {
        "files": [
            {"name": "valid.bin", "sha256": "a" * 64, "release_asset": "valid.bin"},
            {"name": "plain.bin", "repo_path": "bios/plain.bin"},
            {"name": "hle.bin", "repo_path": "bios/hle.bin"},
        ]
    }
    enriched = AresFirmwareService._enrich_entries_from_database(entries, database)

    by_name = {entry.name: entry for entry in enriched}
    assert by_name["valid.bin"].panel_state(True) == "VALIDADO"
    assert by_name["valid.bin"].panel_state_detail(True) == "Arquivo encontrado; hash correto."
    assert by_name["plain.bin"].panel_state(True) == "PRESENTE — HASH NÃO VERIFICÁVEL"
    assert by_name["missing.bin"].panel_state(False) == "AUSENTE — NÃO DISPONÍVEL"
    assert by_name["hle.bin"].panel_state(False) == "HLE / OPCIONAL"


def test_panel_state_marks_required_entry_with_catalog_payload_as_available() -> None:
    payload = {
        "items": [{
            "id": "testemu",
            "profile": {
                "emulator": "Test",
                "files": [{"name": "missing.bin", "sha256": "c" * 64, "required": True}],
            },
        }]
    }
    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="testemu")
    enriched = AresFirmwareService._enrich_entries_from_database(
        entries,
        {"files": [{"name": "missing.bin", "sha256": "c" * 64, "release_asset": "missing.bin"}]},
    )
    assert enriched[0].panel_state(False) == "AUSENTE — DISPONÍVEL"


def test_scan_does_not_accept_same_filename_when_hash_does_not_match(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    firmware = source / "kick13.rom"
    firmware.write_bytes(b"dump with different identity")
    payload = {
        "items": [{
            "id": "amiberry",
            "profile": {
                "emulator": "Amiberry",
                "files": [{
                    "name": "kick13.rom",
                    "sha256": "0" * 64,
                    "size": len(firmware.read_bytes()),
                }],
            },
        }]
    }
    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="amiberry")

    scan = AresFirmwareService.scan(source, entries, emulator="amiberry")

    assert len(scan.matches) == 1
    assert scan.matches[0].path == str(firmware)
    assert scan.matches[0].match_mode == "name"
    assert scan.matches[0].entry.name == "kick13.rom"


def test_scan_prefers_hash_match_over_same_filename_fallback(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    firmware = source / "bios.bin"
    data = b"correct BIOS"
    firmware.write_bytes(data)
    payload = {
        "items": [{
            "id": "testemu",
            "profile": {
                "emulator": "Test",
                "files": [{
                    "name": "bios.bin",
                    "sha256": hashlib.sha256(data).hexdigest(),
                }],
            },
        }]
    }
    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="testemu")

    scan = AresFirmwareService.scan(source, entries, emulator="testemu")

    assert len(scan.matches) == 1
    assert scan.matches[0].match_mode == "hash"
    assert scan.matches[0].entry.name == "bios.bin"


def test_panel_state_distinguishes_filename_fallback() -> None:
    payload = {
        "items": [{
            "id": "testemu",
            "profile": {
                "emulator": "Test",
                "files": [{"name": "bios.bin", "sha256": "a" * 64, "required": True}],
            },
        }]
    }
    entries, _version = AresFirmwareService._parse_catalog(payload, emulator="testemu")

    assert entries[0].panel_state(True, match_mode="hash") == "VALIDADO"
    assert entries[0].panel_state(True, match_mode="name") == "PRESENTE — NOME COMPATÍVEL"
    assert "não coincidiu" in entries[0].panel_state_detail(True, match_mode="name")


def test_ares_source_reconstruction_uses_physical_filename_for_loose_firmware(tmp_path: Path) -> None:
    source = tmp_path / "ColecoVision - BIOS (World).bin"
    source.write_bytes(b"coleco")
    entry = AresFirmwareEntry(
        name="BIOS",
        system="ColecoVision",
        description="ARES source: World",
        required=True,
        profile_id="ares-source",
        region="World",
    )

    evidence = AresFirmwareMatch(entry, str(source)).to_evidence()

    assert evidence["output_name"] == source.name

