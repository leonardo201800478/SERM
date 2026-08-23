"""Testes da fachada usada pela GUI para sessões de Scan ROMs."""
from __future__ import annotations

from pathlib import Path

from app.core.services.scan_session_service import ScanSessionService


class FakeScanService:
    """Serviço falso para verificar que a fachada apenas delega."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def scan(self, *args, **kwargs):
        self.calls.append(("scan", (args, kwargs)))
        return 17, {"status": "completed"}

    def latest(self):
        self.calls.append(("latest", None))
        return {"id": 17}

    def history(self, limit=20):
        self.calls.append(("history", limit))
        return [{"id": 17}]

    def load(self, scan_id):
        self.calls.append(("load", scan_id))
        return {"id": scan_id}

    def delete(self, scan_id):
        self.calls.append(("delete", scan_id))
        return True


def test_run_delegates_all_scan_options() -> None:
    """A fachada não deve alterar as opções recebidas pela GUI."""
    fake = FakeScanService()
    facade = ScanSessionService(fake)  # type: ignore[arg-type]
    callback = lambda *_args: None

    result = facade.run(
        [{"name": "pacman"}],
        [Path("roms")],
        mame_version="0.289",
        xml_path=Path("listxml.xml"),
        max_workers=4,
        enable_alternate_search=False,
        include_chds=True,
        manifest_directory=Path("scan"),
        progress_callback=callback,
    )

    assert result == (17, {"status": "completed"})
    name, payload = fake.calls[0]
    assert name == "scan"
    args, kwargs = payload
    assert args[0] == [{"name": "pacman"}]
    assert args[1] == [Path("roms")]
    assert kwargs["mame_version"] == "0.289"
    assert kwargs["max_workers"] == 4
    assert kwargs["enable_alternate_search"] is False
    assert kwargs["include_chds"] is True
    assert kwargs["progress_callback"] is callback


def test_session_queries_delegate() -> None:
    """Consultas e remoção devem permanecer centralizadas no serviço."""
    fake = FakeScanService()
    facade = ScanSessionService(fake)  # type: ignore[arg-type]

    assert facade.latest() == {"id": 17}
    assert facade.history(5) == [{"id": 17}]
    assert facade.load(8) == {"id": 8}
    assert facade.delete(8) is True
    assert fake.calls == [
        ("latest", None),
        ("history", 5),
        ("load", 8),
        ("delete", 8),
    ]
