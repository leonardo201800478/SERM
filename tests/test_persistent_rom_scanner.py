from __future__ import annotations

import zipfile
from pathlib import Path

from app.mame.persistent_rom_scanner import PersistentRomScanner


def test_persistent_index_reuses_unchanged_zip(tmp_path: Path) -> None:
    roms = tmp_path / "roms"
    roms.mkdir()
    source = roms / "source.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("foo.bin", b"1234")

    index = tmp_path / "index.sqlite3"
    scanner = PersistentRomScanner([roms], index_path=index, enable_alternate_search=True)

    first = scanner.build_archive_index()
    assert first == 1
    before = index.stat().st_mtime_ns

    second = scanner.build_archive_index()
    assert second == 1
    assert index.exists()
    assert index.stat().st_mtime_ns >= before


def test_persistent_index_finds_rom_by_crc_and_size(tmp_path: Path) -> None:
    roms = tmp_path / "roms"
    roms.mkdir()
    source = roms / "source.zip"
    data = b"1234"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("foo.bin", data)

    import binascii

    scanner = PersistentRomScanner([roms], index_path=tmp_path / "index.sqlite3", enable_alternate_search=True)
    scanner.build_archive_index()

    result = scanner._find_indexed_zip_rom(
        "target",
        {"name": "foo.bin", "size": len(data), "crc": f"{binascii.crc32(data) & 0xffffffff:08x}"},
    )
    assert result is not None
    assert result.status.value == "valid"
