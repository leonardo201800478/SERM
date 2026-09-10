from __future__ import annotations

import json
from pathlib import Path

from serm_v2.models.arcade import RomStatus
from serm_v2.services.arcade.scan_comparison import ArcadeScanComparisonService


def test_compares_expected_listxml_against_scan(tmp_path: Path) -> None:
    xml = """<mame><machine name='game'><description>Game</description><year>1991</year><manufacturer>Maker</manufacturer><rom name='ok.bin' size='4' crc='9a7b2c31' sha1='1111'/><rom name='missing.bin' size='4' crc='22222222' sha1='2222'/></machine></mame>"""
    scan = tmp_path / "scan.json"
    scan.write_text(json.dumps({
        "format": "SERM-SCAN-V2",
        "scan_id": "scan-1",
        "catalog_label": "MAME 0.289",
        "evidence": [
            {"machine_name": "game", "rom_name": "ok.bin", "status": "CURRENT", "actual_size": 4, "actual_crc": "9a7b2c31", "actual_sha1": "1111", "path": "R:/game.zip!ok.bin"}
        ],
    }), encoding="utf-8")

    result = ArcadeScanComparisonService().compare(xml, scan)

    assert result.machine_count == 1
    machine = result.machines[0]
    assert machine.machine_name == "game"
    assert machine.status is RomStatus.MISSING
    assert machine.components[0].status is RomStatus.OK
    assert machine.components[0].physical_path == "R:/game.zip!ok.bin"
    assert machine.components[1].status is RomStatus.MISSING


def test_marks_physical_evidence_not_present_in_listxml_as_orphan(tmp_path: Path) -> None:
    xml = "<mame><machine name='game'><rom name='ok.bin' size='1' crc='1' sha1='1'/></machine></mame>"
    scan = tmp_path / "scan.json"
    scan.write_text(json.dumps({
        "format": "SERM-SCAN-V2",
        "evidence": [
            {"machine_name": "game", "rom_name": "ok.bin", "status": "CURRENT"},
            {"machine_name": "game", "rom_name": "extra.bin", "status": "CURRENT"},
        ],
    }), encoding="utf-8")

    result = ArcadeScanComparisonService().compare(xml, scan)

    assert result.orphan_items == 1
