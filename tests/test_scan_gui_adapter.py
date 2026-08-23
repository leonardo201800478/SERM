"""Testes do adapter usado pela GUI durante a migração do scanner."""
from pathlib import Path

from app.core.services.scan_gui_adapter import ScanGuiAdapter


class FakeSession:
    """Sessão falsa para verificar a interface pública do adapter."""

    def run(self, *args, **kwargs):
        return 42, {"status": "completed"}

    def latest(self):
        return {"id": 42}

    def history(self, limit=20):
        return [{"id": 42, "limit": limit}]

    def load(self, scan_id):
        return {"id": scan_id}

    def delete(self, scan_id):
        return scan_id == 42


def test_adapter_delegates_pipeline() -> None:
    """A GUI deve receber o ID persistido e o resultado do scan."""
    adapter = ScanGuiAdapter(FakeSession())  # type: ignore[arg-type]
    result = adapter.start(
        [{"name": "pacman", "roms": []}],
        [Path("roms")],
        xml_path=Path("listxml.xml"),
        mame_version="0.289",
        max_workers=2,
        manifest_directory=Path("scan"),
    )
    assert result == (42, {"status": "completed"})
    assert adapter.latest() == {"id": 42}
    assert adapter.history(3) == [{"id": 42, "limit": 3}]
    assert adapter.load(42) == {"id": 42}
    assert adapter.delete(42) is True
