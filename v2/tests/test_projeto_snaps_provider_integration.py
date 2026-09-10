from __future__ import annotations

import os
from pathlib import Path
from zipfile import ZipFile

import pytest

from serm_v2.services.arcade.download_manager import DestinationAction, DownloadManager
from serm_v2.services.arcade.projeto_snaps_provider import ProgettoSnapsProvider


pytestmark = pytest.mark.skipif(
    os.getenv("SERM_RUN_NETWORK_TESTS") != "1",
    reason="teste de integracao com a rede desabilitado; use SERM_RUN_NETWORK_TESTS=1",
)


def test_projeto_snaps_support_download_extract_and_install(tmp_path: Path) -> None:
    provider = ProgettoSnapsProvider()
    resource = next(item for item in provider.resources() if item.name == "support-files")
    manager = DownloadManager(tmp_path / "cache")

    archive = manager.download(resource)
    assert archive.is_file()
    assert archive.suffix == ".zip"

    extracted = manager.extract(resource, archive)
    destination = tmp_path / "mame"
    result = manager.install_members(resource, extracted, destination)
    assert len(result) == len(resource.metadata["members"])
    assert all(item[2] is DestinationAction.CREATE for item in result)
    assert (destination / "dats/command.dat").is_file()
    assert (destination / "dats/gameinit.dat").is_file()
    assert (destination / "dats/unoffsysinfo.dat").is_file()
    assert (destination / "folders/catlist.ini").is_file()
    assert (destination / "folders/genre.ini").is_file()
    assert (destination / "folders/bestgames.ini").is_file()
    assert (destination / "folders/series.ini").is_file()
    assert (destination / "folders/languages.ini").is_file()

    result_again = manager.install_members(resource, extracted, destination)
    assert all(item[2] is DestinationAction.REUSE for item in result_again)


def test_projeto_snaps_support_archive_contains_expected_member_names(tmp_path: Path) -> None:
    provider = ProgettoSnapsProvider()
    resource = next(item for item in provider.resources() if item.name == "support-files")
    manager = DownloadManager(tmp_path / "cache")

    archive = manager.download(resource)
    with ZipFile(archive) as package:
        names = {Path(name).name.casefold() for name in package.namelist() if not name.endswith("/")}

    expected = {Path(name).name.casefold() for name in resource.metadata["members"]}
    assert expected.issubset(names)
