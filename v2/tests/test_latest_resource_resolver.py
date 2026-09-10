from pathlib import Path

from serm_v2.models.external_resource import ExternalResource, ExternalResourceType, ExtractionMode, ResourceStorage
from serm_v2.services.arcade.download_manager import DownloadManager
from serm_v2.services.arcade.latest_resource_resolver import LatestResourceResolver


def _resource(metadata: dict[str, object]) -> ExternalResource:
    return ExternalResource(
        resource_id="test-resource",
        provider="test",
        platform="mame",
        name="support",
        version="0.288",
        resource_type=ExternalResourceType.METADATA,
        url="https://example.invalid/support_288.zip",
        storage=ResourceStorage.MAME_SOURCE,
        extraction=ExtractionMode.ARCHIVE,
        metadata=metadata,
    )


def test_listing_selects_highest_numeric_version(monkeypatch) -> None:
    resource = _resource(
        {
            "latest_discovery": {
                "strategy": "listing",
                "listing_url": "https://example.invalid/index.html",
                "pattern": r"SupportFiles Pack\s*\((0\.\d+)\)",
                "url_template": "https://example.invalid/pS_SupportFiles_{version_compact}.zip",
            }
        }
    )
    monkeypatch.setattr(
        LatestResourceResolver,
        "_fetch_text",
        staticmethod(lambda _url, _resource: "SupportFiles Pack (0.288) SupportFiles Pack (0.290) SupportFiles Pack (0.289)"),
    )

    resolved = LatestResourceResolver().resolve(resource)

    assert resolved.version == "0.290"
    assert resolved.url.endswith("pS_SupportFiles_0290.zip")


def test_link_listing_uses_published_href_and_highest_version(monkeypatch) -> None:
    resource = _resource(
        {
            "latest_discovery": {
                "strategy": "link",
                "listing_url": "https://example.invalid/samples/",
                "href_pattern": r"MAME_samples_(0\.\d{3})\.zip",
            }
        }
    )
    monkeypatch.setattr(
        LatestResourceResolver,
        "_fetch_text",
        staticmethod(
            lambda _url, _resource: (
                '<a href="packs/MAME_samples_288.zip">FullPack 0.288</a>'
                '<a href="packs/MAME_samples_289.zip">FullPack 0.289</a>'
            )
        ),
    )

    resolved = LatestResourceResolver().resolve(resource)

    assert resolved.version == "0.289"
    assert resolved.url == "https://example.invalid/samples/packs/MAME_samples_289.zip"


def test_link_listing_supports_relative_and_absolute_hrefs(monkeypatch) -> None:
    resource = _resource(
        {
            "latest_discovery": {
                "strategy": "link",
                "listing_url": "https://example.invalid/samples/",
                "href_pattern": r"MAME_samples_(0\.\d{3})\.zip",
            }
        }
    )
    monkeypatch.setattr(
        LatestResourceResolver,
        "_fetch_text",
        staticmethod(
            lambda _url, _resource: (
                '<a href="https://cdn.example/MAME_samples_289.zip">FullPack</a>'
                '<a href="packs/MAME_samples_288.zip">Older</a>'
            )
        ),
    )

    resolved = LatestResourceResolver().resolve(resource)

    assert resolved.version == "0.289"
    assert resolved.url == "https://cdn.example/MAME_samples_289.zip"


def test_probe_can_advance_to_newer_version(monkeypatch) -> None:
    resource = _resource(
        {
            "latest_discovery": {
                "strategy": "probe",
                "start_version": "0.278",
                "max_ahead": 5,
                "stop_after_misses": 2,
                "url_template": "https://example.invalid/nplayers{version_compact}.zip",
            }
        }
    )
    available = {
        "https://example.invalid/nplayers0279.zip",
        "https://example.invalid/nplayers0280.zip",
    }
    monkeypatch.setattr(
        LatestResourceResolver,
        "_url_exists",
        staticmethod(lambda url, _resource: url in available),
    )

    resolved = LatestResourceResolver().resolve(resource)

    assert resolved.version == "0.280"
    assert resolved.url.endswith("nplayers0280.zip")


def test_download_manager_resolves_latest_before_cache(monkeypatch, tmp_path: Path) -> None:
    resource = _resource(
        {
            "latest_discovery": {
                "strategy": "listing",
                "listing_url": "https://example.invalid/index.html",
                "pattern": r"v(0\.\d+)",
                "url_template": "https://example.invalid/archive_{version_compact}.zip",
            }
        }
    )
    manager = DownloadManager(tmp_path)
    monkeypatch.setattr(
        LatestResourceResolver,
        "_fetch_text",
        staticmethod(lambda _url, _resource: "v0.289"),
    )

    resolved = manager._latest_resolver.resolve(resource)

    assert manager.archive_path(resolved) == tmp_path / "test" / "mame" / "support" / "0.289" / "support.zip"
