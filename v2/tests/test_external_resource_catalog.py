from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from zipfile import ZipFile

import pytest

from serm_v2.models.external_resource import (
    ExternalResource,
    ExternalResourceType,
    ExtractionMode,
    ResourceStorage,
)
from serm_v2.services.arcade.download_manager import DestinationAction, DownloadManager
from serm_v2.services.arcade.progetto_snaps_provider import ProgettoSnapsProvider
from serm_v2.services.arcade.resource_catalog import ExternalResourceCatalog


def test_progetto_snaps_catalog_maps_selected_support_packages() -> None:
    resources = ProgettoSnapsProvider().resources()
    by_name = {resource.name: resource for resource in resources}

    assert by_name["catver"].version == "0.289"
    assert by_name["catver"].storage is ResourceStorage.MAME_SOURCE
    assert by_name["bestgames"].version == "0.280"
    assert by_name["command"].version == "0.273"
    assert by_name["gameinit"].version == "0.289"
    assert by_name["samples-fullpack"].storage is ResourceStorage.MAME_SOURCE
    assert by_name["samples-fullpack"].resource_type is ExternalResourceType.SAMPLE
    assert by_name["samples-fullpack"].url.endswith("/samples/packs/MAME_samples_289.zip")

    gameinit_members = by_name["gameinit"].metadata["members"]
    assert gameinit_members["dats/gameinit.dat"] == "mame_dats"
    assert gameinit_members["folders/gameinit.ini"] == "mame_folders"


def test_catalog_deduplicates_by_provider_platform_name_version() -> None:
    resource = ExternalResource(
        resource_id="one",
        provider="provider",
        platform="mame",
        name="x",
        version="1",
        resource_type=ExternalResourceType.METADATA,
        url="https://example.invalid/x",
        storage=ResourceStorage.CACHE_ONLY,
    )
    replacement = replace(resource, resource_id="two")
    catalog = ExternalResourceCatalog((resource, replacement))
    assert len(catalog) == 1
    assert catalog.get("provider", "mame", "x", "1") == replacement


def test_archive_member_rejects_path_traversal() -> None:
    resource = ExternalResource(
        resource_id="x",
        provider="p",
        platform="mame",
        name="x",
        version="1",
        resource_type=ExternalResourceType.METADATA,
        url="https://example.invalid/x",
        storage=ResourceStorage.CACHE_ONLY,
        archive_member="../escape.ini",
    )
    with pytest.raises(ValueError):
        resource.safe_member()


def test_download_manager_extracts_archive_without_escape(tmp_path: Path) -> None:
    archive = tmp_path / "sample.zip"
    with ZipFile(archive, "w") as package:
        package.writestr("safe/file.ini", "ok")

    resource = ExternalResource(
        resource_id="x",
        provider="p",
        platform="mame",
        name="x",
        version="1",
        resource_type=ExternalResourceType.METADATA,
        url="https://example.invalid/x",
        storage=ResourceStorage.CACHE_ONLY,
        extraction=ExtractionMode.ARCHIVE,
        metadata={"members": {"safe/file.ini": "mame_folders"}},
    )
    manager = DownloadManager(tmp_path / "cache")
    extracted = manager.extract(resource, archive)
    assert (extracted / "safe/file.ini").read_text() == "ok"

    destination = tmp_path / "mame"
    installed = manager.install_members(resource, extracted, destination)
    assert installed == (("safe/file.ini", destination / "folders/file.ini", DestinationAction.CREATE),)
    assert (destination / "folders/file.ini").read_text() == "ok"

    installed_again = manager.install_members(resource, extracted, destination)
    assert installed_again[0][2] is DestinationAction.REUSE


def test_download_manager_blocks_different_destination_without_override(tmp_path: Path) -> None:
    archive = tmp_path / "sample.zip"
    with ZipFile(archive, "w") as package:
        package.writestr("folders/test.ini", "new")

    resource = ExternalResource(
        resource_id="x",
        provider="p",
        platform="mame",
        name="x",
        version="1",
        resource_type=ExternalResourceType.METADATA,
        url="https://example.invalid/x",
        storage=ResourceStorage.MAME_SOURCE,
        extraction=ExtractionMode.ARCHIVE,
        metadata={"members": {"folders/test.ini": "mame_folders"}},
    )
    manager = DownloadManager(tmp_path / "cache")
    extracted = manager.extract(resource, archive)
    destination = tmp_path / "mame"
    (destination / "folders").mkdir(parents=True)
    (destination / "folders/test.ini").write_text("old")

    with pytest.raises(FileExistsError):
        manager.install_members(resource, extracted, destination)
