import io
import zipfile
from pathlib import Path

from serm_v2.sources.acquisition.no_intro_archive import (
    NoIntroArchiveEntry,
    NoIntroArchiveProvider,
)


def _archive(*names: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, 'clrmamepro (\n name "test"\n)\n')
    return buffer.getvalue()


def test_accept_excludes_non_official_categories(tmp_path: Path) -> None:
    provider = NoIntroArchiveProvider(root=tmp_path)
    assert provider._accept("Nintendo - Game Boy (Parent-Clone) (20260707-013717).dat")
    assert not provider._accept("Non-Redump - Sega - Dreamcast (Parent-Clone).dat")
    assert not provider._accept("Source Code - Nintendo - NES (Parent-Clone).dat")
    assert not provider._accept("Unofficial - Sony - PSP (Parent-Clone).dat")


def test_extract_archive_materializes_all_official_dats(tmp_path: Path) -> None:
    provider = NoIntroArchiveProvider(root=tmp_path)
    provider.archive_path.write_bytes(
        _archive(
            "Nintendo - Game Boy (Parent-Clone) (20260707-013717).dat",
            "Sega - Mega Drive - Genesis (Parent-Clone) (20260629-112427).dat",
            "Non-Redump - Sega - Dreamcast (Parent-Clone) (20260411-182542).dat",
        )
    )

    entries = provider._extract_archive(provider.archive_path)

    assert [entry.name for entry in entries] == [
        "Nintendo - Game Boy (Parent-Clone) (20260707-013717).dat",
        "Sega - Mega Drive - Genesis (Parent-Clone) (20260629-112427).dat",
    ]
    assert all(entry.path.is_file() for entry in entries)


def test_match_supports_launchbox_aliases(tmp_path: Path) -> None:
    provider = NoIntroArchiveProvider(root=tmp_path)
    entries = (
        NoIntroArchiveEntry(
            "Nintendo - Nintendo Entertainment System (Headered) (20260704-141639).dat",
            provider.dat_root / "Nintendo - Nintendo Entertainment System (Headered) (20260704-141639).dat",
        ),
        NoIntroArchiveEntry(
            "Sega - Mega Drive - Genesis (Parent-Clone) (20260629-112427).dat",
            provider.dat_root / "Sega - Mega Drive - Genesis (Parent-Clone) (20260629-112427).dat",
        ),
    )

    matches = provider.match(("NES", "Sega Genesis"), entries)

    assert [entry.name for entry in matches] == [entries[0].name, entries[1].name]


def test_destination_is_stable(tmp_path: Path) -> None:
    provider = NoIntroArchiveProvider(root=tmp_path)
    entry = NoIntroArchiveEntry(
        "Nintendo - Game Boy (Parent-Clone) (20260707-013717).dat",
        provider.dat_root / "Nintendo - Game Boy (Parent-Clone) (20260707-013717).dat",
    )
    assert provider.destination(entry) == provider.dat_root / entry.name
