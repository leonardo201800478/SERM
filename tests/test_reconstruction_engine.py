from __future__ import annotations

import binascii
import zipfile
from pathlib import Path

from app.mame.reconstruction_engine import ReconstructionEngine, ReconstructionMachine, ReconstructionRom


def _rom(name: str, data: bytes, source_zip: Path, member: str) -> ReconstructionRom:
    crc = f"{binascii.crc32(data) & 0xFFFFFFFF:08x}"
    return ReconstructionRom(
        machine="game",
        rom_name=name,
        expected_size=len(data),
        expected_crc=crc,
        expected_sha1=None,
        status="valid",
        source_archive=str(source_zip),
        source_member=member,
        source_kind="zip",
    )


def test_reconstruction_uses_individual_roms_and_removes_extras(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    expected_a = b"AAAA"
    expected_b = b"BBBB"
    source_zip = source / "game.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("wrong_name.bin", expected_a)
        archive.writestr("b.bin", expected_b)
        archive.writestr("extra.txt", b"must not be copied")

    machine = ReconstructionMachine(
        name="game",
        roms=[
            _rom("a.bin", expected_a, source_zip, "wrong_name.bin"),
            _rom("b.bin", expected_b, source_zip, "b.bin"),
        ],
    )

    result = ReconstructionEngine([source], destination).reconstruct([machine], repair=True)

    assert result.repaired == 1
    output = destination / "game.zip"
    assert output.is_file()
    with zipfile.ZipFile(output, "r") as archive:
        assert set(archive.namelist()) == {"a.bin", "b.bin"}
        assert archive.read("a.bin") == expected_a
        assert archive.read("b.bin") == expected_b


def test_missing_source_never_creates_empty_zip(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()

    machine = ReconstructionMachine(
        name="missing_game",
        roms=[
            ReconstructionRom(
                machine="missing_game",
                rom_name="missing.bin",
                expected_size=4,
                expected_crc="12345678",
                expected_sha1=None,
                status="missing",
                source_archive=None,
                source_member=None,
                source_kind=None,
            )
        ],
    )

    result = ReconstructionEngine([source], destination).reconstruct([machine], repair=True)

    assert result.repaired == 0
    assert result.external == 1
    assert not (destination / "missing_game.zip").exists()
