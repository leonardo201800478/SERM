from __future__ import annotations

from pathlib import Path

from app.core.services.mame_build_planner import MameBuildPlanner


def test_external_bios_and_device_are_separate_sets(tmp_path: Path) -> None:
    xml = tmp_path / "listxml.xml"
    xml.write_text(
        '''<mame>
  <machine name="game">
    <description>Game</description>
    <rom name="game.bin" size="1" crc="aaaaaaaa" sha1="1111111111111111111111111111111111111111"/>
    <device_ref name="device1"/>
  </machine>
  <machine name="biossys" isbios="yes">
    <description>BIOS</description>
    <biosset name="bios1" description="BIOS"/>
    <rom name="bios.bin" size="1" crc="bbbbbbbb" sha1="2222222222222222222222222222222222222222"/>
  </machine>
  <machine name="device1" isdevice="yes">
    <description>Device</description>
    <rom name="device.bin" size="1" crc="cccccccc" sha1="3333333333333333333333333333333333333333"/>
  </machine>
</mame>\n''',
        encoding="utf-8",
    )

    plan = MameBuildPlanner(xml).plan(["game"], mode="split")

    assert plan.runtime_ready
    assert plan.archives.archives["game"][0].rom.name == "game.bin"
    assert plan.external_archives == {"device1": "device1.zip"}
