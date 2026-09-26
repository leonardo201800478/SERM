import hashlib
import zipfile
from pathlib import Path

from serm_v2.services.retrobios_pack_service import (
    RetroBiosPack,
    RetroBiosPackAsset,
    RetroBiosPackError,
    RetroBiosPackService,
)


def test_list_available_groups_multipart_bios_packs(monkeypatch) -> None:
    payload = {
        "tag_name": "v2026.09.04",
        "assets": [
            {
                "name": "RetroArch_Lakka_v1.22.2_BIOS_Pack.zip.002",
                "browser_download_url": "https://github.com/Abdess/retrobios/releases/download/v2026.09.04/RetroArch_Lakka_v1.22.2_BIOS_Pack.zip.002",
                "size": 20,
                "digest": "sha256:" + "b" * 64,
            },
            {
                "name": "RetroArch_Lakka_v1.22.2_BIOS_Pack.zip.001",
                "browser_download_url": "https://github.com/Abdess/retrobios/releases/download/v2026.09.04/RetroArch_Lakka_v1.22.2_BIOS_Pack.zip.001",
                "size": 10,
                "digest": "sha256:" + "a" * 64,
            },
            {
                "name": "SHA256SUMS.txt",
                "browser_download_url": "https://github.com/Abdess/retrobios/releases/download/v2026.09.04/SHA256SUMS.txt",
                "size": 100,
            },
            {
                "name": "not-a-bios-pack.zip",
                "browser_download_url": "https://example.invalid/not-a-bios-pack.zip",
                "size": 10,
            },
        ]
    }
    monkeypatch.setattr(RetroBiosPackService, "_get_json", lambda *_args: payload)

    packs = RetroBiosPackService.list_available()

    assert len(packs) == 1
    assert packs[0].platform == "RetroArch Lakka v1.22.2"
    assert packs[0].multipart
    assert [asset.part for asset in packs[0].assets] == [1, 2]
    assert packs[0].size == 30


def test_extract_safe_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.bin", b"bad")

    destination = tmp_path / "destination"
    destination.mkdir()

    try:
        RetroBiosPackService._extract_safe(archive, destination, cancel_callback=None)
    except RetroBiosPackError as exc:
        assert "Entrada insegura" in str(exc)
    else:
        raise AssertionError("Traversal de ZIP deveria ser rejeitado")


def test_download_and_extract_verifies_asset_and_preserves_existing_file(
    monkeypatch, tmp_path: Path
) -> None:
    source_zip = tmp_path / "pack.zip"
    with zipfile.ZipFile(source_zip, "w") as zf:
        zf.writestr("bios/scph.bin", b"valid bios")

    digest = hashlib.sha256(source_zip.read_bytes()).hexdigest()
    asset = RetroBiosPackAsset(
        name="Test_BIOS_Pack.zip",
        url="https://github.com/Abdess/retrobios/releases/download/test/Test_BIOS_Pack.zip",
        size=source_zip.stat().st_size,
        sha256=digest,
    )
    pack = RetroBiosPack("Test", asset.name, (asset,))

    def fake_download(asset, target, *, progress_callback, cancel_callback):
        target.write_bytes(source_zip.read_bytes())
        if progress_callback:
            progress_callback(asset.size, asset.size)

    monkeypatch.setattr(RetroBiosPackService, "_download", fake_download)

    root = tmp_path / "packs"
    root.mkdir()
    existing = root / "Test" / "bios" / "scph.bin"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"valid bios")

    extracted = RetroBiosPackService.download_and_extract(pack, destination=root)

    assert extracted == (root / "Test").resolve()
    assert existing.read_bytes() == b"valid bios"
    assert (extracted / "bios" / "scph.bin").read_bytes() == b"valid bios"


def test_safe_archive_path_rejects_absolute_and_parent_paths() -> None:
    assert RetroBiosPackService._safe_archive_path("/bios.bin") is None
    assert RetroBiosPackService._safe_archive_path("../bios.bin") is None
    assert RetroBiosPackService._safe_archive_path("bios/../bios.bin") is None
    assert RetroBiosPackService._safe_archive_path("bios/system.bin") == Path("bios/system.bin")
