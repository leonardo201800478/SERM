from pathlib import Path

from serm_v2.sources.acquisition.redump import RedumpProvider


def test_catalog_contains_all_direct_redump_systems() -> None:
    entries = RedumpProvider().fetch_catalog()
    assert len(entries) >= 50
    assert any(entry.code == "psx" for entry in entries)
    assert any(entry.code == "gc" for entry in entries)
    assert any(entry.code == "wii" for entry in entries)
    assert any(entry.code == "dc" for entry in entries)


def test_direct_url_uses_system_code(tmp_path: Path) -> None:
    provider = RedumpProvider(root=tmp_path)
    entry = next(item for item in provider.fetch_catalog() if item.code == "ps2")
    assert entry.url.endswith("/datfile/ps2/")


def test_match_supports_launchbox_aliases(tmp_path: Path) -> None:
    provider = RedumpProvider(root=tmp_path)
    entries = provider.fetch_catalog()
    matches = provider.match(("PlayStation", "GameCube", "Sega Saturn"), entries)
    names = {entry.name for entry in matches}
    assert "Sony - PlayStation" in names
    assert "Nintendo - GameCube" in names
    assert "Sega - Saturn" in names


def test_destination_is_stable(tmp_path: Path) -> None:
    provider = RedumpProvider(root=tmp_path)
    entry = next(item for item in provider.fetch_catalog() if item.code == "psx")
    assert provider.destination(entry).name == "Sony - PlayStation.dat"
