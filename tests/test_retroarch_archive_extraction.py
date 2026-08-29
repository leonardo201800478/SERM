"""Testes da extração local do pacote RetroArch."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from app.core.services.retroarch_download_service import RetroArchDownloadService


def test_extract_7z_uses_py7zr_when_system_7zip_is_missing(tmp_path: Path, monkeypatch) -> None:
    """Sem 7-Zip no PATH, o serviço deve usar py7zr em vez de abortar."""
    archive = tmp_path / "RetroArch.7z"
    destination = tmp_path / "out"
    archive.write_bytes(b"fixture")
    calls: list[tuple[str, Path]] = []

    class FakeArchive:
        def __init__(self, path, mode):
            assert Path(path) == archive
            assert mode == "r"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extractall(self, path):
            calls.append(("extractall", Path(path)))
            root = Path(path) / "RetroArch-Win64"
            root.mkdir(parents=True)
            (root / "retroarch.exe").write_bytes(b"exe")

    fake_py7zr = SimpleNamespace(SevenZipFile=FakeArchive)
    monkeypatch.setattr("shutil.which", lambda _name: None)
    monkeypatch.setitem(sys.modules, "py7zr", fake_py7zr)

    RetroArchDownloadService._extract_7z(archive, destination)

    assert calls == [("extractall", destination)]
    assert (destination / "RetroArch-Win64" / "retroarch.exe").is_file()
