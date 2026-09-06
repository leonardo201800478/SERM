"""Tests for the read-only LaunchBox provider."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from serm_v2.integrations.launchbox import LaunchBoxIntegration
from serm_v2.integrations.launchbox_provider import LaunchBoxGame, LaunchBoxProvider


def _integration(tmp_path: Path) -> LaunchBoxIntegration:
    """Create a fake LaunchBox installation rooted inside the pytest temp path."""
    integration = LaunchBoxIntegration()
    integration.CONFIG_PATH = tmp_path / "launchbox.json"
    root = tmp_path / "LaunchBox"
    metadata = root / "Metadata"
    metadata.mkdir(parents=True)

    integration.executable = root / "LaunchBox.exe"
    integration.executable.write_bytes(b"test")
    integration._save()
    return integration


def test_provider_reads_database_and_xml_without_writing(tmp_path: Path) -> None:
    integration = _integration(tmp_path)
    metadata = integration.executable.parent / "Metadata"
    database = metadata / "LaunchBox.Metadata.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE Games ("
            "DatabaseID INTEGER PRIMARY KEY, Name TEXT NOT NULL, Platform TEXT NOT NULL, "
            "ReleaseDate TEXT, ReleaseYear INTEGER, Overview TEXT, Developer TEXT, "
            "Publisher TEXT, Genres TEXT)"
        )
        connection.execute(
            "INSERT INTO Games VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                1,
                "Sonic the Hedgehog",
                "Sega Genesis",
                "1991-06-23",
                1991,
                "Overview",
                "SEGA",
                "SEGA",
                "Platformer",
            ),
        )

    platforms = metadata / "Platforms.xml"
    platforms.write_text(
        "<LaunchBox><Platform><Name>Sega Genesis</Name><Emulated>true</Emulated>"
        "<Category>Console</Category></Platform></LaunchBox>",
        encoding="utf-8",
    )

    provider = LaunchBoxProvider(integration)

    assert provider.database_tables() == ("Games",)
    assert provider.table_columns("Games")[:3] == ("DatabaseID", "Name", "Platform")

    games = list(provider.iter_games())
    assert games == [
        LaunchBoxGame(
            database_id=1,
            name="Sonic the Hedgehog",
            platform="Sega Genesis",
            release_date="1991-06-23",
            release_year=1991,
            overview="Overview",
            developer="SEGA",
            publisher="SEGA",
            genres="Platformer",
        )
    ]

    launchbox_platforms = list(provider.iter_platforms())
    assert launchbox_platforms[0].name == "Sega Genesis"
    assert launchbox_platforms[0].emulated is True
    assert launchbox_platforms[0].category == "Console"


def test_provider_rejects_invalid_table_name(tmp_path: Path) -> None:
    integration = _integration(tmp_path)
    database = integration.executable.parent / "Metadata" / "LaunchBox.Metadata.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE Games (DatabaseID INTEGER)")
    platforms = integration.executable.parent / "Metadata" / "Platforms.xml"
    platforms.write_text("<LaunchBox />", encoding="utf-8")

    provider = LaunchBoxProvider(integration)

    try:
        provider.table_columns("Games; DROP TABLE Games")
    except ValueError:
        pass
    else:
        raise AssertionError("A entrada SQL inválida deveria ser rejeitada.")

    assert provider.database_tables() == ("Games",)
