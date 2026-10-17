from pathlib import Path

from serm_v2.models.external_resource import (
    ExternalResource,
    ExternalResourceType,
    ExtractionMode,
    ResourceStorage,
)
from serm_v2.services.arcade.download_manager import DownloadManager
from serm_v2.services.arcade.latest_resource_resolver import LatestResourceResolver
from serm_v2.services.arcade.projeto_snaps_provider import ProgettoSnapsProvider


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
    resource = _resource({
        "latest_discovery": {
            "strategy": "listing", "listing_url": "https://example.invalid/index.html",
            "pattern": r"SupportFiles Pack\s*\((0\.\d+)\)",
            "url_template": "https://example.invalid/pS_SupportFiles_{version_compact}.zip",
        }
    })
    monkeypatch.setattr(LatestResourceResolver, "_fetch_text", staticmethod(
        lambda _url, _resource: "SupportFiles Pack (0.288) SupportFiles Pack (0.290) SupportFiles Pack (0.289)"
    ))
    resolved = LatestResourceResolver().resolve(resource)
    assert resolved.version == "0.290"
    assert resolved.url.endswith("pS_SupportFiles_0290.zip")


def test_link_listing_accepts_compact_versions_in_hrefs(monkeypatch) -> None:
    resource = _resource({
        "latest_discovery": {
            "strategy": "link", "listing_url": "https://example.invalid/samples/",
            "href_pattern": r"MAME_samples_(\d{3})\.zip",
        }
    })
    monkeypatch.setattr(LatestResourceResolver, "_fetch_text", staticmethod(
        lambda _url, _resource: (
            '<a href="packs/MAME_samples_288.zip">FullPack 0.288</a>'
            '<a href="packs/MAME_samples_289.zip">FullPack 0.289</a>'
        )
    ))
    resolved = LatestResourceResolver().resolve(resource)
    assert resolved.version == "0.289"
    assert resolved.url == "https://example.invalid/samples/packs/MAME_samples_289.zip"


def test_link_listing_supports_relative_and_absolute_hrefs(monkeypatch) -> None:
    resource = _resource({
        "latest_discovery": {
            "strategy": "link", "listing_url": "https://example.invalid/samples/",
            "href_pattern": r"MAME_samples_(\d{3})\.zip",
        }
    })
    monkeypatch.setattr(LatestResourceResolver, "_fetch_text", staticmethod(
        lambda _url, _resource: (
            '<a href="https://cdn.example/MAME_samples_289.zip">FullPack</a>'
            '<a href="packs/MAME_samples_288.zip">Older</a>'
        )
    ))
    resolved = LatestResourceResolver().resolve(resource)
    assert resolved.version == "0.289"
    assert resolved.url == "https://cdn.example/MAME_samples_289.zip"


def test_support_pack_uses_latest_link_from_support_page(monkeypatch) -> None:
    resource = next(
        item for item in ProgettoSnapsProvider().resources() if item.name == "support-files"
    )
    monkeypatch.setattr(
        LatestResourceResolver,
        "_fetch_text",
        staticmethod(
            lambda _url, _resource: (
                '<a href="/download/?tipo=support_pack&amp;'
                'file=/support/packs/pS_SupportFiles_288.zip">'
                "SupportFiles Pack (0.288)</a>"
            )
        ),
    )

    resolved = LatestResourceResolver().resolve(resource)

    assert resolved.version == "0.288"
    assert resolved.url == (
        "https://www.progettosnaps.net/download/?tipo=support_pack&"
        "file=/support/packs/pS_SupportFiles_288.zip"
    )


def test_folder_package_uses_latest_link_from_its_own_page(monkeypatch) -> None:
    resource = next(item for item in ProgettoSnapsProvider().resources() if item.name == "catver")
    monkeypatch.setattr(
        LatestResourceResolver,
        "_fetch_text",
        staticmethod(
            lambda _url, _resource: (
                '<a href="/download/?tipo=catver&amp;file=pS_CatVer_290.zip">'
                "download CatList CatVer &amp; Genre 0.290</a>"
            )
        ),
    )

    resolved = LatestResourceResolver().resolve(resource)

    assert resolved.version == "0.290"
    assert resolved.url == (
        "https://www.progettosnaps.net/download/"
        "?tipo=catver&file=pS_CatVer_290.zip"
    )


def test_category_and_version_manifests_resolve_published_links(monkeypatch) -> None:
    resources = {
        item.name: item
        for item in ProgettoSnapsProvider().resources()
        if item.name in {"category", "version"}
    }
    page = (
        '<a href="/download/?tipo=category&amp;'
        'file=/support/packs/pS_category_290.zip">category.ini (0.290)</a>'
        '<a href="/download/?tipo=version&amp;'
        'file=/support/packs/pS_version_290.zip">version.ini (0.290)</a>'
    )
    monkeypatch.setattr(
        LatestResourceResolver,
        "_fetch_text",
        staticmethod(lambda _url, _resource: page),
    )

    category = LatestResourceResolver().resolve(resources["category"])
    version = LatestResourceResolver().resolve(resources["version"])

    assert category.version == "0.290"
    assert category.url == (
        "https://www.progettosnaps.net/download/"
        "?tipo=category&file=/support/packs/pS_category_290.zip"
    )
    assert version.version == "0.290"
    assert version.url == (
        "https://www.progettosnaps.net/download/"
        "?tipo=version&file=/support/packs/pS_version_290.zip"
    )


def test_probe_can_advance_to_newer_version(monkeypatch) -> None:
    resource = _resource({
        "latest_discovery": {
            "strategy": "probe", "start_version": "0.278", "max_ahead": 5,
            "stop_after_misses": 2, "url_template": "https://example.invalid/nplayers{version_compact}.zip",
        }
    })
    available = {"https://example.invalid/nplayers0279.zip", "https://example.invalid/nplayers0280.zip"}
    monkeypatch.setattr(LatestResourceResolver, "_url_exists", staticmethod(lambda url, _resource: url in available))
    resolved = LatestResourceResolver().resolve(resource)
    assert resolved.version == "0.280"
    assert resolved.url.endswith("nplayers0280.zip")


def test_nplayers_provider_discovery_uses_probe_strategy(monkeypatch) -> None:
    resource = next(
        item for item in ProgettoSnapsProvider().resources() if item.name == "nplayers"
    )
    available = {
        "https://nplayers.arcadebelgium.be/files/nplayers0279.zip",
        "https://nplayers.arcadebelgium.be/files/nplayers0280.zip",
    }
    monkeypatch.setattr(
        LatestResourceResolver,
        "_url_exists",
        staticmethod(lambda url, _resource: url in available),
    )

    resolved = LatestResourceResolver().resolve(resource)

    assert resolved.version == "0.280"
    assert resolved.url == "https://nplayers.arcadebelgium.be/files/nplayers0280.zip"


def test_download_manager_resolves_latest_before_cache(monkeypatch, tmp_path: Path) -> None:
    resource = _resource({
        "latest_discovery": {
            "strategy": "listing", "listing_url": "https://example.invalid/index.html",
            "pattern": r"v(0\.\d+)", "url_template": "https://example.invalid/archive_{version_compact}.zip",
        }
    })
    manager = DownloadManager(tmp_path)
    monkeypatch.setattr(LatestResourceResolver, "_fetch_text", staticmethod(lambda _url, _resource: "v0.289"))
    resolved = manager._latest_resolver.resolve(resource)
    assert manager.archive_path(resolved) == tmp_path / "test" / "mame" / "support" / "0.289" / "support.zip"
