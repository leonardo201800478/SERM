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


def test_projeto_snaps_gameinit_download_extract_and_install(tmp_path: Path) -> None:
    provider = ProgettoSnapsProvider()
    resource = next(item for item in provider.resources() if item.name == "gameinit")
    manager = DownloadManager(tmp_path / "cache")

    archive = manager.download(resource)
    assert archive.is_file()
    assert archive.suffix == ".zip"

    extracted = manager.extract(resource, archive)
    assert (extracted / "dats/gameinit.dat").is_file()
    assert (extracted / "folders/gameinit.ini").is_file()

    destination = tmp_path / "mame"
    result = manager.install_members(resource, extracted, destination)

    assert {item[0] for item in result} == {
        "dats/gameinit.dat",
        "folders/gameinit.ini",
    }
    assert all(item[2] is DestinationAction.CREATE for item in result)
    assert (destination / "dats/gameinit.dat").is_file()
    assert (destination / "folders/gameinit.ini").is_file()

    result_again = manager.install_members(resource, extracted, destination)
    assert all(item[2] is DestinationAction.REUSE for item in result_again)


def test_projeto_snaps_gameinit_archive_is_a_valid_zip(tmp_path: Path) -> None:
    provider = ProgettoSnapsProvider()
    resource = next(item for item in provider.resources() if item.name == "gameinit")
    manager = DownloadManager(tmp_path / "cache")

    archive = manager.download(resource)
    with ZipFile(archive) as package:
        names = set(package.namelist())

    assert "dats/gameinit.dat" in names
    assert "folders/gameinit.ini" in names
