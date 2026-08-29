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


def test_catalog_uses_direct_redump_urls(tmp_path: Path) -> None:
    """Redump entries use Redump datfile endpoints, not the GitHub mirror."""
    provider = RedumpProvider(root=tmp_path)
    entry = next(item for item in provider.fetch_catalog() if item.name == "Sony PlayStation 2.dat")
    assert entry.url == "http://redump.org/datfile/ps2/"
    assert "raw.githubusercontent.com" not in entry.url
    assert "/datfile/" in entry.url


def test_direct_url_for_sega_cd() -> None:
    """Sega CD uses Redump's mcd endpoint."""
    assert RedumpProvider.direct_url_for_name("Sega Mega CD & Sega CD.dat") == (
        "http://redump.org/datfile/mcd/"
    )


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
