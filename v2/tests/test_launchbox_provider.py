"""Tests for the read-only LaunchBox provider."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from serm_v2.integrations.launchbox import LaunchBoxIntegration
from serm_v2.integrations.launchbox_provider import LaunchBoxProvider


def _integration(tmp_path: Path, database: Path, platforms: Path) -> LaunchBoxIntegration:
    integration = LaunchBoxIntegration()
    integration.CONFIG_PATH = tmp_path / "launchbox.json"
    integration.executable = tmp_path / "LaunchBox.exe"
    integration.executable.write_bytes(b"test")
    integration._save()

    metadata = tmp_path / "Metadata"
    metadata.mkdir()
    database.rename(metadata / "LaunchBox.Metadata.db")
    platforms.rename(metadata / "Platforms.xml")
    return integration


def test_provider_reads_database_and_xml_without_writing(tmp_path: Path) -> None:
    database = tmp_path / "LaunchBox.Metadata.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE Games ("
            "DatabaseID INTEGER PRIMARY KEY, Name TEXT NOT NULL, Platform TEXT NOT NULL, "
            "ReleaseDate TEXT, ReleaseYear INTEGER, Overview TEXT, Developer TEXT, "
            "Publisher TEXT, Genres TEXT)"
        )
        connection.execute(
            "INSERT INTO Games VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, "Sonic the Hedgehog", "Sega Genesis", "1991-06-23", 1991, "Overview", "SEGA", "SEGA", "Platformer"),
        )

    platforms = tmp_path / "Platforms.xml"
    platforms.write_text(
        "<LaunchBox><Platform><Name>Sega Genesis</Name><Emulated>true</Emulated>"
        "<Category>Console</Category></Platform></LaunchBox>",
        encoding="utf-8",
    )

    integration = _integration(tmp_path, database, platforms)
    provider = LaunchBoxProvider(integration)

    assert provider.database_tables() == ("Games",)
    assert provider.table_columns("Games")[:3] == ("DatabaseID", "Name", "Platform")
    assert list(provider.iter_games()) == [
        provider_game
        for provider_game in provider.iter_games()
    ]
    games = list(provider.iter_games())
    assert games[0].name == "Sonic the Hedgehog"
    assert games[0].platform == "Sega Genesis"

    launchbox_platforms = list(provider.iter_platforms())
    assert launchbox_platforms[0].name == "Sega Genesis"
    assert launchbox_platforms[0].emulated is True
    assert launchbox_platforms[0].category == "Console"


def test_provider_rejects_invalid_table_name(tmp_path: Path) -> None:
    database = tmp_path / "LaunchBox.Metadata.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE Games (DatabaseID INTEGER)")
    platforms = tmp_path / "Platforms.xml"
    platforms.write_text("<LaunchBox />", encoding="utf-8")

    integration = _integration(tmp_path, database, platforms)
    provider = LaunchBoxProvider(integration)

    try:
        provider.table_columns("Games; DROP TABLE Games")
    except ValueError:
        pass
    else:
        raise AssertionError("A entrada SQL inválida deveria ser rejeitada.")
