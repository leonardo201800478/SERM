"""Testes da camada de orquestração do Scan ROMs."""
from __future__ import annotations

from pathlib import Path

from app.core.models.scan_result import MachineScanResult, RomScanResult, ScanStatus
from app.core.services.scan_service import ScanService
from app.database.database import Database
from app.database.scan_repository import ScanRepository


class FakeScanEngine:
    """Engine determinístico para testar a orquestração sem filesystem."""

    def __init__(self, rom_paths, **kwargs):
        self.rom_paths = list(rom_paths)
        self.kwargs = kwargs
        self.cancelled = False

    def scan(self, machines, **kwargs):
        """Retorna uma machine válida simulando o scanner físico."""
        result = MachineScanResult(
            machine_name="pacman",
            description="Pac-Man (1980)",
            started=True,
        )
        result.add_result(
            RomScanResult(
                machine_name="pacman",
                rom_name="pacman.6e",
                status=ScanStatus.VALID,
                expected_size=4,
                actual_size=4,
                expected_crc="b63c1d3f",
                actual_crc="b63c1d3f",
                path=Path("roms/pacman.zip"),
                archive_path=Path("roms/pacman.zip"),
                archive_member="pacman.6e",
                message="ROM válida.",
            )
        )
        return [result]


def test_scan_service_persists_engine_result(tmp_path: Path) -> None:
    """O resultado produzido pelo engine deve virar uma sessão persistida."""
    db = Database(tmp_path / "scan.db")
    repository = ScanRepository(db)
    service = ScanService(repository, engine_factory=FakeScanEngine)

    scan_id, result = service.scan(
        machines=[{"name": "pacman"}],
        rom_paths=[tmp_path],
        mame_version="0.289",
        xml_path=tmp_path / "listxml.xml",
    )

    assert scan_id > 0
    assert result.machine_count == 1
    assert result.valid == 1
    assert repository.latest_id() == scan_id

    loaded = service.load(scan_id)
    assert loaded is not None
    assert loaded.get_machine("pacman") is not None
    assert loaded.get_machine("pacman").roms[0].archive_member == "pacman.6e"

    db.close()


def test_scan_service_history_and_delete(tmp_path: Path) -> None:
    """O serviço deve expor histórico e remoção sem acessar SQLite diretamente."""
    db = Database(tmp_path / "scan.db")
    repository = ScanRepository(db)
    service = ScanService(repository, engine_factory=FakeScanEngine)

    first, _ = service.scan([{"name": "pacman"}], [tmp_path])
    second, _ = service.scan([{"name": "pacman"}], [tmp_path])

    history = service.history(limit=10)
    assert [row["id"] for row in history[:2]] == [second, first]
    assert service.latest() is not None
    assert service.delete(first) is True
    assert service.load(first) is None
    assert service.load(second) is not None

    db.close()
