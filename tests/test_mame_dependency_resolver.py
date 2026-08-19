from __future__ import annotations

from pathlib import Path

from app.core.services.mame_archive_layout import MameArchiveLayoutPlanner
from app.core.services.mame_dependency_resolver import MameDependencyResolver


def _write_xml(path: Path) -> None:
    path.write_text(
        '''<?xml version="1.0"?>
<mame>
  <machine name="parent" sourcefile="test.cpp">
    <description>Parent</description>
    <rom name="parent.bin" size="10" crc="aaaaaaaa" sha1="1111111111111111111111111111111111111111"/>
  </machine>
  <machine name="clone" cloneof="parent" romof="parent" sourcefile="test.cpp">
    <description>Clone</description>
    <rom name="parent.bin" size="10" crc="aaaaaaaa" sha1="1111111111111111111111111111111111111111" merge="parent"/>
    <rom name="clone.bin" size="20" crc="bbbbbbbb" sha1="2222222222222222222222222222222222222222"/>
    <rom name="bios.bin" size="30" crc="cccccccc" sha1="3333333333333333333333333333333333333333" bios="bios1"/>
    <sample name="clone"/>
    <device_ref name="sounddev"/>
  </machine>
  <machine name="biossys" isbios="yes">
    <description>BIOS</description>
    <biosset name="bios1" description="BIOS 1"/>
    <rom name="bios.bin" size="30" crc="cccccccc" sha1="3333333333333333333333333333333333333333"/>
  </machine>
  <machine name="sounddev" isdevice="yes">
    <description>Sound Device</description>
    <rom name="sound.bin" size="40" crc="dddddddd" sha1="4444444444444444444444444444444444444444"/>
  </machine>
</mame>
''',
        encoding="utf-8",
    )


def test_resolves_parent_bios_device_and_sample(tmp_path: Path) -> None:
    xml = tmp_path / "listxml.xml"
    _write_xml(xml)

    plan = MameDependencyResolver(xml).resolve(["clone"], mode="split")

    assert plan.runtime_ready
    clone = plan.machines["clone"]
    assert clone.parent == "parent"
    assert clone.bios_machines == ["biossys"]
    assert clone.device_machines == ["sounddev"]
    assert "clone" in plan.samples
    assert any(edge.kind.value == "parent" for edge in clone.dependencies)
    assert any(edge.kind.value == "bios" for edge in clone.dependencies)
    assert any(edge.kind.value == "device" for edge in clone.dependencies)


def test_split_keeps_parent_rom_in_parent_archive(tmp_path: Path) -> None:
    xml = tmp_path / "listxml.xml"
    _write_xml(xml)
    plan = MameDependencyResolver(xml).resolve(["clone"], mode="split")
    archives = MameArchiveLayoutPlanner().build(plan, "split")

    assert "clone" in archives.archives
    assert "parent" in archives.archives
    assert [item.rom.name for item in archives.archives["clone"]] == ["clone.bin", "bios.bin"]
    assert [item.rom.name for item in archives.archives["parent"]] == ["parent.bin"]


def test_nonmerged_contains_parent_data_but_not_device_archive(tmp_path: Path) -> None:
    xml = tmp_path / "listxml.xml"
    _write_xml(xml)
    plan = MameDependencyResolver(xml).resolve(["clone"], mode="non-merged")
    archives = MameArchiveLayoutPlanner().build(plan, "non-merged")

    assert "clone" in archives.archives
    names = {item.rom.name for item in archives.archives["clone"]}
    assert names == {"parent.bin", "clone.bin", "bios.bin"}
    assert "sound.bin" not in names


def test_merged_uses_parent_as_archive_owner(tmp_path: Path) -> None:
    xml = tmp_path / "listxml.xml"
    _write_xml(xml)
    plan = MameDependencyResolver(xml).resolve(["clone"], mode="merged")
    archives = MameArchiveLayoutPlanner().build(plan, "merged")

    assert "parent" in archives.archives
    assert "clone" not in archives.archives
    names = {item.rom.name for item in archives.archives["parent"]}
    assert names == {"parent.bin", "clone.bin", "bios.bin"}
    assert "sound.bin" not in names
