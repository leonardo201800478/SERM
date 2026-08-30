from pathlib import Path

from serm_v2.services.mame_catalog_service import MameCatalogService


class _FakeService:
    def __init__(self, name: str, events: list[str], result: dict[str, object]):
        self.name = name
        self.events = events
        self.result = result

    def ingest(self, *, logger=None):
        self.events.append(self.name)
        if logger:
            logger(f"fake:{self.name}")
        return self.result


def test_ingest_inis_preserves_required_order(monkeypatch, tmp_path: Path):
    events: list[str] = []
    results = {
        "CATLIST": {"entries": 1, "resolved": 1, "unresolved": 0, "source_id": 1},
        "RESOLUTION": {"entries": 2, "resolved": 2, "unresolved": 0, "source_id": 2},
        "VSYNC": {"entries": 3, "resolved": 3, "unresolved": 0, "source_id": 3},
    }

    def factory(name):
        class Service:
            def __init__(self, database_path, mame_root):
                assert database_path == MameCatalogService.DB_FILE
                assert mame_root == tmp_path

            def ingest(self, logger=None):
                events.append(name)
                return results[name]

        return Service

    monkeypatch.setattr(
        "serm_v2.services.mame_catalog_service.MameClassificationService",
        factory("CATLIST"),
    )
    monkeypatch.setattr(
        "serm_v2.services.mame_catalog_service.MameResolutionService",
        factory("RESOLUTION"),
    )
    monkeypatch.setattr(
        "serm_v2.services.mame_catalog_service.MameVsyncService",
        factory("VSYNC"),
    )

    service = MameCatalogService(logger=lambda _: None)
    actual = service._ingest_inis(tmp_path)

    assert events == ["CATLIST", "RESOLUTION", "VSYNC"]
    assert [name for name, _ in actual] == ["CATLIST", "RESOLUTION", "VSYNC"]
    assert actual[2][1]["source_id"] == 3


def test_ingest_inis_propagates_failure_and_stops_following_stages(monkeypatch, tmp_path: Path):
    events: list[str] = []

    class Catlist:
        def __init__(self, database_path, mame_root):
            pass

        def ingest(self, logger=None):
            events.append("CATLIST")
            return {"entries": 1}

    class Resolution:
        def __init__(self, database_path, mame_root):
            pass

        def ingest(self, logger=None):
            events.append("RESOLUTION")
            raise RuntimeError("resolution failed")

    class Vsync:
        def __init__(self, database_path, mame_root):
            pass

        def ingest(self, logger=None):
            events.append("VSYNC")
            return {"entries": 1}

    monkeypatch.setattr("serm_v2.services.mame_catalog_service.MameClassificationService", Catlist)
    monkeypatch.setattr("serm_v2.services.mame_catalog_service.MameResolutionService", Resolution)
    monkeypatch.setattr("serm_v2.services.mame_catalog_service.MameVsyncService", Vsync)

    service = MameCatalogService(logger=lambda _: None)

    try:
        service._ingest_inis(tmp_path)
    except RuntimeError as exc:
        assert str(exc) == "resolution failed"
    else:
        raise AssertionError("A falha de uma etapa deveria interromper a fila")

    assert events == ["CATLIST", "RESOLUTION"]
