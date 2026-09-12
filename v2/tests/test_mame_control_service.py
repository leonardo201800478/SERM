from pathlib import Path

from serm_v2.services.mame_control_service import MameControlService


LISTXML = """
<mame build="0.289">
  <machine name="racer" sourcefile="src/racer.cpp">
    <input players="2" coins="1" service="yes">
      <control type="paddle" player="1" buttons="2" minimum="0" maximum="255" sensitivity="70" keydelta="5" />
      <control type="pedal" player="1" buttons="2" minimum="0" maximum="255" />
    </input>
  </machine>
  <machine name="fighter">
    <input players="2" coins="1">
      <control type="joy" player="1" buttons="6" ways="8" />
    </input>
  </machine>
</mame>
""".strip()


def test_reads_mame_control_attributes(tmp_path: Path) -> None:
    path = tmp_path / "listxml.xml"
    path.write_text(LISTXML, encoding="utf-8")

    result = MameControlService().read_machine(path, "racer")

    assert result is not None
    assert result.players == 2
    assert result.coins == 1
    assert result.service is True
    assert len(result.controls) == 2
    assert result.controls[0].control_type == "paddle"
    assert result.controls[0].buttons == 2
    assert result.controls[0].maximum == 255
    assert result.controls[1].control_type == "pedal"


def test_streams_large_listxml_by_machine(tmp_path: Path) -> None:
    path = tmp_path / "listxml.xml"
    path.write_text(LISTXML, encoding="utf-8")

    results = tuple(MameControlService().iter_machines(path))

    assert [item.machine_name for item in results] == ["racer", "fighter"]
    assert results[1].controls[0].buttons == 6
    assert results[1].controls[0].ways == 8
