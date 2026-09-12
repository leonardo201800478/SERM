from pathlib import Path

import pytest

from serm_v2.services.mame_catalog_service import MameCatalogError, MameCatalogService


def test_ingest_inis_preserves_required_and_optional_order(monkeypatch, tmp_path: Path):
    events: list[tuple[str, Path]] = []
    results = {
        "CATLIST": {"entries": 1, "resolved": 1, "unresolved": 0, "source_id": 1},
        "RESOLUTION": {"entries": 2, "resolved": 2, "unresolved": 0, "source_id": 2},
        "VSYNC": {"entries": 3, "resolved": 3, "unresolved": 0, "source_id": 3},
        "FOLDERS": {"files": 4},
        "SOFTWARELISTS": {"files": 5, "software": 6},
    }

    def factory(name):
        class Service:
            def __init__(self, database_path, mame_root):
                assert database_path == MameCatalogService.DB_FILE
                expected_root = tmp_path / "hash" if name == "SOFTWARELISTS" else tmp_path
                assert mame_root == expected_root
                self.root = mame_root

            def ingest(self, logger=None):
                events.append((name, self.root))
                return results[name]

        return Service

    monkeypatch.setattr("serm_v2.services.mame_catalog_service.MameClassificationService", factory("CATLIST"))
    monkeypatch.setattr("serm_v2.services.mame_catalog_service.MameResolutionService", factory("RESOLUTION"))
    monkeypatch.setattr("serm_v2.services.mame_catalog_service.MameVsyncService", factory("VSYNC"))
    monkeypatch.setattr("serm_v2.services.mame_catalog_service.MameFolderFilterService", factory("FOLDERS"))
    monkeypatch.setattr("serm_v2.services.mame_catalog_service.MameSoftwareListService", factory("SOFTWARELISTS"))

    service = MameCatalogService(logger=lambda _: None)
    actual = service._ingest_inis(tmp_path)

    assert [name for name, _ in events] == [
        "CATLIST", "RESOLUTION", "VSYNC", "FOLDERS", "SOFTWARELISTS"
    ]
    assert events[-1][1] == tmp_path / "hash"
    assert [name for name, _ in actual] == [
        "CATLIST", "RESOLUTION", "VSYNC", "FOLDERS", "SOFTWARELISTS"
    ]
    assert actual[-1][1]["software"] == 6


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

    with pytest.raises(RuntimeError, match="resolution failed"):
        service._ingest_inis(tmp_path)

    assert events == ["CATLIST", "RESOLUTION"]


def test_listxml_failure_does_not_start_ini_pipeline(monkeypatch):
    service = MameCatalogService(logger=lambda _: None)
    ini_calls: list[Path] = []

    monkeypatch.setattr(service, "configured_executable", lambda: Path("C:/mame/mame.exe"))
    monkeypatch.setattr(
        service,
        "_run_mame",
        lambda executable, timeout: (_ for _ in ()).throw(MameCatalogError("listxml failed")),
    )
    monkeypatch.setattr(service, "_ingest_inis", lambda root: ini_calls.append(root))

    with pytest.raises(MameCatalogError, match="listxml failed"):
        service.ingest()

    assert ini_calls == []
