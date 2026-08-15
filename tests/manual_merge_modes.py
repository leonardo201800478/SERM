from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tempfile import TemporaryDirectory
import hashlib
import zipfile
import zlib
import xml.etree.ElementTree as ET

from app.core.models.scan_result import RomFile, MachineScanResult, ScanResult, ScanStatus
from app.core.services.reconstruction_service import ReconstructionOptions, ReconstructionService


def rom(name, data, source, merge=None):
    return RomFile(name=name, size=len(data), crc=f"{zlib.crc32(data) & 0xffffffff:08x}", sha1=hashlib.sha1(data).hexdigest(), merge=merge, status=ScanStatus.OK, found_in=source, found_member=name, actual_size=len(data), actual_crc=f"{zlib.crc32(data) & 0xffffffff:08x}", actual_sha1=hashlib.sha1(data).hexdigest())


def main():
    assert ScanStatus.CORRUPTED.color == "#000000"
    assert ScanStatus.UNAVAILABLE.color == "#FF0000"
    assert ScanStatus.FIXABLE.color == "#FFAA00"
    assert ScanStatus.MISSING.color == "#808080"
    with TemporaryDirectory() as td:
        root = Path(td); source = root / "source"; source.mkdir()
        shared = b"shared"; child = b"child"; (source / "parent.zip").unlink(missing_ok=True)
        with zipfile.ZipFile(source / "parent.zip", "w") as z:
            z.writestr("shared.bin", shared)
        with zipfile.ZipFile(source / "clone.zip", "w") as z:
            z.writestr("child.bin", child)
        parent = MachineScanResult("parent", "Parent", roms=[rom("shared.bin", shared, source / "parent.zip")])
        clone = MachineScanResult("clone", "Clone", cloneof="parent", roms=[rom("shared.bin", shared, source / "parent.zip", merge="shared.bin"), rom("child.bin", child, source / "clone.zip")])
        for machine in (parent, clone): machine.update_status()
        result = ScanResult("test", machines=[parent, clone]); result.update_summary()
        for mode in ("split", "non-merged", "merged"):
            destination = root / mode
            ReconstructionService(ReconstructionOptions(destination, mode=mode)).reconstruct(result)
            if mode == "split":
                assert (destination / "parent.zip").exists() and (destination / "clone.zip").exists()
            elif mode == "non-merged":
                assert set(zipfile.ZipFile(destination / "clone.zip").namelist()) == {"shared.bin", "child.bin"}
            else:
                assert set(zipfile.ZipFile(destination / "parent.zip").namelist()) == {"shared.bin", "child.bin"}
    print("status colors and merge modes: OK")


if __name__ == "__main__":
    main()
