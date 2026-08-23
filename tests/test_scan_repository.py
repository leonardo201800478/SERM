"""Testes da persistência dos resultados do Scan ROMs."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.core.models.scan_result import (
    MachineScanResult,
    RomScanResult,
    ScanItemType,
    ScanResult,
    ScanStatus,
)
from app.database.database import Database
from app.database.scan_repository import ScanRepository


def _build_result() -> ScanResult:
    """Cria um resultado pequeno, mas representativo, para os testes."""
    machine = MachineScanResult(
        machine_name="pacman",
        description="Pac-Man (1980)",
        cloneof=None,
        started=True,
    )
    machine.add_result(
        RomScanResult(
            machine_name="pacman",
            rom_name="pacman.6e",
            status=ScanStatus.VALID,
            expected_size=4096,
            actual_size=4096,
            expected_crc="c1e6ab10",
            actual_crc="c1e6ab10",
            expected_sha1="" * 0,
            actual_sha1="" * 0,
            path=Path("roms/pacman.zip"),
            archive_path=Path("roms/pacman.zip"),
            archive_member="pacman.6e",
            item_type=ScanItemType.ROM,
            merge=None,
            optional=False,
        )
    )
    machine.add_result(
        RomScanResult(
            machine_name="pacman",
            rom_name="pacman.chd",
            status=ScanStatus.MISSING,
            item_type=ScanItemType.DISK,
            expected_size=8192,
            message="CHD ausente",
        )
    )
    return ScanResult(
        machines=[machine],
        xml_path=Path("data/listxml.xml"),
        started_at=datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 8, 23, 12, 1, tzinfo=timezone.utc),
    )


def test_scan_repository_round_trip(tmp_path: Path) -> None:
    """Persistência deve reconstruir a estrutura sem perda de dados."""
    db = Database(tmp_path / "scan.db")
    repository = ScanRepository(db)
    original = _build_result()

    scan_id = repository.save(original)
    loaded = repository.load(scan_id)

    assert loaded is not None
    assert loaded.xml_path == original.xml_path
    assert loaded.started_at == original.started_at
    assert loaded.finished_at == original.finished_at
    assert loaded.machine_count == 1
    assert loaded.total == 2
    assert loaded.valid == 1
    assert loaded.missing == 1

    machine = loaded.get_machine("pacman")
    assert machine is not None
    assert machine.description == "Pac-Man (1980)"
    assert machine.total == 2
    assert machine.valid == 1
    assert machine.missing == 1
    assert machine.roms[0].archive_member == "pacman.6e"
    assert machine.roms[1].item_type is ScanItemType.DISK

    db.close()


def test_scan_repository_latest_and_list(tmp_path: Path) -> None:
    """Sessões recentes devem ser consultáveis sem carregar seus itens."""
    db = Database(tmp_path / "scan.db")
    repository = ScanRepository(db)
    first = repository.save(_build_result())
    second = repository.save(_build_result())

    assert repository.latest_id() == second
    sessions = repository.list_sessions(limit=10)
    assert [item["id"] for item in sessions[:2]] == [second, first]

    db.close()


def test_scan_repository_delete_cascades_items(tmp_path: Path) -> None:
    """Excluir uma sessão deve excluir máquinas e itens vinculados."""
    db = Database(tmp_path / "scan.db")
    repository = ScanRepository(db)
    scan_id = repository.save(_build_result())

    assert repository.delete(scan_id) is True
    assert repository.load(scan_id) is None
    assert db.fetch_value("SELECT COUNT(*) FROM scan_machine") == 0
    assert db.fetch_value("SELECT COUNT(*) FROM scan_item") == 0

    db.close()
