from pathlib import Path

import pytest
from serm_v2.sources.no_intro.errors import NoIntroParseError
from serm_v2.sources.no_intro.parser import NoIntroParser

DAT = '''<?xml version="1.0"?>
<datafile>
  <header>
    <name>No-Intro Test</name>
    <version>20260829</version>
    <date>2026-08-29</date>
  </header>
  <game name="Super Mario Bros. (World)">
    <description>Super Mario Bros. (World)</description>
    <rom name="Super Mario Bros. (World).nes" size="40976" crc="1234abcd" md5="00112233445566778899aabbccddeeff" sha1="0123456789abcdef0123456789abcdef01234567"/>
  </game>
</datafile>
'''


def test_parser_preserves_source_identity_and_hashes(tmp_path: Path) -> None:
    path = tmp_path / "test.dat"
    path.write_text(DAT, encoding="utf-8")

    info, sets = NoIntroParser().parse(path)

    assert info.name == "No-Intro Test"
    assert info.version == "20260829"
    assert len(sets) == 1
    assert sets[0].name == "Super Mario Bros. (World)"
    assert sets[0].provenance.source == "No-Intro"
    assert sets[0].roms[0].filename == "Super Mario Bros. (World).nes"
    assert sets[0].roms[0].size == 40976
    assert {item.algorithm for item in sets[0].roms[0].hashes} == {"crc", "md5", "sha1"}


def test_parser_rejects_malformed_xml(tmp_path: Path) -> None:
    path = tmp_path / "broken.dat"
    path.write_text("<datafile>", encoding="utf-8")

    with pytest.raises(NoIntroParseError):
        NoIntroParser().parse(path)
