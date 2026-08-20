from pathlib import Path

from app.core.models.scan_result import MachineScanResult, RomScanResult, ScanItemType, ScanResult, ScanStatus
from app.core.services.chd_reconstruction_service import ChdReconstructionOptions, ChdReconstructionService


def _disk(tmp_path: Path, *, machine: str = "game", name: str = "disk") -> RomScanResult:
    source = tmp_path / "source.chd"
    source.write_bytes(b"dummy")
    return RomScanResult(
        machine_name=machine,
        rom_name=name,
        status=ScanStatus.VALID,
        expected_sha1="a" * 40,
        actual_sha1="a" * 40,
        path=source,
        item_type=ScanItemType.DISK,
    )


def test_collects_only_disks(tmp_path: Path) -> None:
    disk = _disk(tmp_path)
    rom = RomScanResult(machine_name="game", rom_name="game.bin", status=ScanStatus.VALID)
    result = ScanResult(machines=[MachineScanResult(machine_name="game", roms=[rom, disk])])

    items = ChdReconstructionService._collect_requirements(result)

    assert items == [disk]


def test_invalid_hash_is_not_copied(monkeypatch, tmp_path: Path) -> None:
    disk = _disk(tmp_path)
    result = ScanResult(machines=[MachineScanResult(machine_name="game", roms=[disk])])

    monkeypatch.setattr(
        "app.core.services.chd_reconstruction_service.chdman_info",
        lambda *args, **kwargs: {"sha1": "b" * 40},
    )
    monkeypatch.setattr(
        "app.core.services.chd_reconstruction_service.chdman_verify",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("verify não deve ocorrer")),
    )

    output = tmp_path / "out"
    records = ChdReconstructionService(ChdReconstructionOptions(output)).reconstruct(result)

    assert records[0].action == "ignore"
    assert records[0].status == "missing"
    assert records[0].blocking is True
    assert not (output / "game" / "disk.chd").exists()


def test_valid_hash_is_verified_and_copied(monkeypatch, tmp_path: Path) -> None:
    disk = _disk(tmp_path)
    result = ScanResult(machines=[MachineScanResult(machine_name="game", roms=[disk])])

    monkeypatch.setattr(
        "app.core.services.chd_reconstruction_service.chdman_info",
        lambda *args, **kwargs: {"sha1": "a" * 40},
    )
    monkeypatch.setattr(
        "app.core.services.chd_reconstruction_service.chdman_verify",
        lambda *args, **kwargs: {"verified": True},
    )

    output = tmp_path / "out"
    records = ChdReconstructionService(ChdReconstructionOptions(output)).reconstruct(result)

    assert records[0].action == "copy"
    assert records[0].status == "valid"
    assert records[0].verified is True
    assert (output / "game" / "disk.chd").read_bytes() == b"dummy"
