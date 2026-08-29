from pathlib import Path

from serm_v2.sources.no_intro.downloader import NoIntroDownloader


def test_discover_downloads_extracts_dat_links() -> None:
    html = '<a href="dat/nintendo.nes.dat">NES</a><a href="dat/game.xml">XML</a>'

    result = NoIntroDownloader().discover_downloads(html, base_url="https://datomatic.no-intro.org/")

    assert result == (
        "https://datomatic.no-intro.org/dat/nintendo.nes.dat",
        "https://datomatic.no-intro.org/dat/game.xml",
    )


def test_download_url_writes_bytes_and_hash(monkeypatch, tmp_path: Path) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self) -> bytes:
            return b"test dat"

    monkeypatch.setattr("serm_v2.sources.no_intro.downloader.urlopen", lambda request, timeout: Response())

    result = NoIntroDownloader().download_url(
        "https://example.invalid/test.dat",
        tmp_path / "test.dat",
        system="Nintendo Entertainment System",
    )

    assert result.path.read_bytes() == b"test dat"
    assert result.sha256 == "78ad0a5d968aec1f884e88aeb37cd8afb5506fb3aee8cf9723b3df0185e834c8"
