from pathlib import Path

from serm_v2.sources.acquisition.redump import RedumpProvider


def test_catalog_contains_redump_systems() -> None:
    """The provider exposes the complete public Redump DAT catalog."""
    entries = RedumpProvider().fetch_catalog()
    assert len(entries) >= 50
    names = {entry.name for entry in entries}
    assert "Sony PlayStation.dat" in names
    assert "Nintendo GameCube.dat" in names
    assert "Nintendo Wii.dat" in names
    assert "Sega Dreamcast.dat" in names


def test_catalog_uses_public_direct_raw_urls(tmp_path: Path) -> None:
    """Redump entries use catalog-published raw DAT URLs, not datfile pages."""
    provider = RedumpProvider(root=tmp_path)
    entry = next(item for item in provider.fetch_catalog() if item.name == "Sony PlayStation 2.dat")
    assert entry.url.startswith("https://raw.githubusercontent.com/")
    assert entry.url.endswith("/Sony%20PlayStation%202.dat")
    assert "/datfile/" not in entry.url


def test_match_supports_launchbox_aliases(tmp_path: Path) -> None:
    """Common LaunchBox names resolve to the corresponding Redump DATs."""
    provider = RedumpProvider(root=tmp_path)
    entries = provider.fetch_catalog()
    matches = provider.match(("PlayStation", "GameCube", "Sega Saturn"), entries)
    names = {entry.name for entry in matches}
    assert "Sony PlayStation.dat" in names
    assert "Nintendo GameCube.dat" in names
    assert "Sega Saturn.dat" in names


def test_destination_is_stable(tmp_path: Path) -> None:
    """Explicit provider roots remain stable and independent of the source URL."""
    provider = RedumpProvider(root=tmp_path)
    entry = next(item for item in provider.fetch_catalog() if item.name == "Sony PlayStation.dat")
    assert provider.destination(entry) == tmp_path / "Sony PlayStation.dat"
