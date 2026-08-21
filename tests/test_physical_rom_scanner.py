from __future__ import annotations

import binascii
import zipfile
from pathlib import Path

from app.mame.physical_rom_scanner import PhysicalRomScanner


class _DB:
    conn = None


def test_expected_zip_uses_size_and_crc_without_keyerror(tmp_path: Path) -> None:
    payload = b"test-rom"
    zip_path = tmp_path / "pacman.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("pacman.rom", payload)

    scanner = PhysicalRomScanner(_DB(), [tmp_path])
    unit = scanner._empty_unit("pacman", 1)
    candidate = {
        "rom_id": 1, "machine_id": 1, "machine_name": "pacman",
        "name": "pacman.rom", "size": len(payload),
        "crc": f"{binascii.crc32(payload) & 0xFFFFFFFF:08x}",
        "sha1": "", "merge": None, "optional": False,
    }

    scanner._scan_expected_zip(zip_path, [candidate], unit, lambda: False)

    assert unit["valid"] == 1
    assert unit["records"][0][7] == "valid"


def test_expected_chd_only_checks_machine_path(tmp_path: Path) -> None:
    scanner = PhysicalRomScanner(_DB(), [tmp_path])
    result = scanner._scan_expected_chd("game", {"name": "disk"}, lambda: False)
    assert result["status"] == "missing"

    chd_dir = tmp_path / "game"
    chd_dir.mkdir()
    (chd_dir / "disk.chd").write_bytes(b"not-a-real-chd")
    result = scanner._scan_expected_chd("game", {"name": "disk"}, lambda: False)
    assert result["status"] == "present"
