"""Tests for the LaunchBox audit command-line tool."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import cast

from serm_v2.integrations.launchbox import LaunchBoxIntegration
from serm_v2.integrations.launchbox_audit import LaunchBoxAudit
from serm_v2.integrations.launchbox_provider import LaunchBoxProvider
from serm_v2.tools.audit_launchbox import build_report, main


def _provider(tmp_path: Path) -> LaunchBoxProvider:
    integration = LaunchBoxIntegration()
    integration.CONFIG_PATH = tmp_path / "launchbox.json"
    root = tmp_path / "LaunchBox"
    metadata = root / "Metadata"
    metadata.mkdir(parents=True)
    integration.executable = root / "LaunchBox.exe"
    integration.executable.write_bytes(b"test")
    integration._save()

    database = metadata / "LaunchBox.Metadata.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE Games ("
            "DatabaseID INTEGER PRIMARY KEY, Name TEXT NOT NULL, Platform TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO Games VALUES (1, 'Game A', 'Platform A')")

    (metadata / "Platforms.xml").write_text(
        "<LaunchBox><Platform><Name>Platform A</Name><Emulated>true</Emulated></Platform></LaunchBox>",
        encoding="utf-8",
    )
    return LaunchBoxProvider(integration)


def test_build_report_is_serializable(tmp_path: Path) -> None:
    report = build_report(LaunchBoxAudit(_provider(tmp_path)), 1)

    assert report["platform_count"] == 1
    assert report["emulated_platform_count"] == 1
    game_sample = cast(list[dict[str, object]], report["game_sample"])
    assert game_sample[0]["name"] == "Game A"
    json.dumps(report)


def test_main_writes_requested_output(tmp_path: Path, monkeypatch) -> None:
    provider = _provider(tmp_path)
    monkeypatch.setattr(
        "serm_v2.tools.audit_launchbox.LaunchBoxAudit",
        lambda: LaunchBoxAudit(provider),
    )
    output = tmp_path / "audit.json"

    assert main(["--sample", "1", "--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["game_sample"][0]["name"] == "Game A"
