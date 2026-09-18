from pathlib import Path

from serm_v2.sources.acquisition.dat_catalog import DatCatalogEntry, PublicDatCatalogProvider


def test_parse_index_keeps_only_no_intro_dat_files() -> None:
    source = """Type,Name,URL,CRC,Size
DIRECTORY,Source Code,,,
FILE,Source Code - NES.dat,https://example.invalid/source.dat,1,10
DIRECTORY,No-Intro,,,
FILE,Nintendo - Nintendo Entertainment System.dat,https://example.invalid/nes.dat,123,42
FILE,Nintendo - Game Boy.dat,https://example.invalid/gb.dat,456,84
DIRECTORY,Non-Redump,,,
FILE,Non-Redump - Nintendo - Wii.dat,https://example.invalid/wii.dat,789,10
"""
    entries = PublicDatCatalogProvider._parse_index(source)
    assert [entry.name for entry in entries] == [
        "Nintendo - Nintendo Entertainment System.dat",
        "Nintendo - Game Boy.dat",
    ]


def test_match_supports_launchbox_aliases(tmp_path: Path) -> None:
    provider = PublicDatCatalogProvider(root=tmp_path)
    entries = (
        DatCatalogEntry(
            "Nintendo - Nintendo Entertainment System.dat", "https://example.invalid/nes.dat", 1, 1
        ),
        DatCatalogEntry(
            "Sega - Mega Drive - Genesis.dat", "https://example.invalid/genesis.dat", 2, 2
        ),
    )
    matches = provider.match(("NES", "Sega Genesis"), entries)
    assert [entry.name for entry in matches] == [
        "Nintendo - Nintendo Entertainment System.dat",
        "Sega - Mega Drive - Genesis.dat",
    ]


def test_status_detects_missing_and_current(tmp_path: Path) -> None:
    provider = PublicDatCatalogProvider(root=tmp_path)
    data = b"test dat"
    import zlib

    entry = DatCatalogEntry(
        "Nintendo - Test.dat",
        "https://example.invalid/test.dat",
        zlib.crc32(data) & 0xFFFFFFFF,
        len(data),
    )
    assert provider.status(entry).state == "missing"
    path = provider.destination(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    assert provider.status(entry).state == "current"
