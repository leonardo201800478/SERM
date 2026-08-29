"""Tests for the read-only LaunchBox structural audit."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from serm_v2.integrations.launchbox import LaunchBoxIntegration
from serm_v2.integrations.launchbox_audit import LaunchBoxAudit
from serm_v2.integrations.launchbox_provider import LaunchBoxProvider


def _integration(tmp_path: Path) -> LaunchBoxIntegration:
    integration = LaunchBoxIntegration()
    integration.CONFIG_PATH = tmp_path / "launchbox.json"
    integration.executable = tmp_path / "LaunchBox.exe"
    integration.executable.write_bytes(b"test")
    metadata = tmp_path / "Metadata"
    metadata.mkdir()
    database = metadata / "LaunchBox.Metadata.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE Games ("
            "DatabaseID INTEGER PRIMARY KEY, Name TEXT NOT NULL, Platform TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO Games VALUES (?, ?, ?)",
            (1, "Sonic the Hedgehog", "Sega Genesis"),
        )
    platforms = metadata / "Platforms.xml"
    platforms.write_text(
        "<LaunchBox>"
        "<Platform><Name>Sega Genesis</Name><Emulated>true</Emulated></Platform>"
        "<Platform><Name>Nintendo Entertainment System</Name><Emulated>false</Emulated></Platform>"
        "</LaunchBox>",
        encoding="utf-8",
    )
    integration._save()
    return integration


def test_audit_reports_tables_and_counts(tmp_path: Path) -> None:
    audit = LaunchBoxAudit(LaunchBoxProvider(_integration(tmp_path)))

    tables = audit.tables()

    assert tables[0].name == "Games"
    assert tables[0].row_count == 1
    assert [column.name for column in tables[0].columns] == ["DatabaseID", "Name", "Platform"]
    assert audit.platform_count() == 2
    assert audit.emulated_platform_count() == 1
    assert audit.game_sample(1)[0].name == "Sonic the Hedgehog"
