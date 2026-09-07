from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from serm_v2.services.arcade.rom_archive_scan import (
    RomArchiveFormatError,
    RomArchiveScanner,
)


def test_scans_zip_entries_with_physical_identity(tmp_path: Path) -> None:
    archive = tmp_path / "sf2.zip"
    payload = b"rom-data"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("sf2.01", payload)
        handle.writestr("empty-dir/", b"")

    result = RomArchiveScanner().scan(archive)

    assert result.entries_scanned == 1
    assert result.entries_skipped == 1
    assert result.inventory[0].path.endswith("!sf2.01")
    assert result.inventory[0].size == len(payload)
    assert result.inventory[0].sha1 == hashlib.sha1(payload).hexdigest()
    assert result.inventory[0].md5 == hashlib.md5(payload).hexdigest()
    assert result.inventory[0].crc == "c2c7e5b6"


def test_rejects_non_zip(tmp_path: Path) -> None:
    path = tmp_path / "game.7z"
    path.write_bytes(b"not supported")

    with pytest.raises(RomArchiveFormatError):
        RomArchiveScanner().scan(path)
