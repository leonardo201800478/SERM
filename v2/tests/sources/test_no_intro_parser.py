from pathlib import Path

import pytest
from serm_v2.sources.no_intro.errors import NoIntroParseError
from serm_v2.sources.no_intro.naming import parse_name
from serm_v2.sources.no_intro.parser import NoIntroParser

DAT = '''<?xml version="1.0"?>
<datafile>
  <header>
    <name>No-Intro Test</name>
    <version>20260829</version>
    <date>2026-08-29</date>
  </header>
  <game name="Super Mario Bros. (World)" cloneof="Super Mario Bros. (USA)">
    <description>Super Mario Bros. (World)</description>
    <release name="Super Mario Bros. (World)" region="USA"/>
    <rom name="Super Mario Bros. (World).nes" size="40976" crc="1234ABCD" md5="00112233445566778899AABBCCDDEEFF" sha1="0123456789ABCDEF0123456789ABCDEF01234567" serial="NES-SM-USA"/>
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
    assert sets[0].clone_of == "Super Mario Bros. (USA)"
    assert sets[0].region == "USA"
    assert sets[0].provenance.source == "No-Intro"
    assert sets[0].roms[0].filename == "Super Mario Bros. (World).nes"
    assert sets[0].roms[0].size == 40976
    assert sets[0].roms[0].serial == "NES-SM-USA"
    assert {item.algorithm for item in sets[0].roms[0].hashes} == {"crc", "md5", "sha1"}
    assert sets[0].roms[0].hashes[0].value == "1234abcd"


def test_parser_rejects_malformed_xml(tmp_path: Path) -> None:
    path = tmp_path / "broken.dat"
    path.write_text("<datafile>", encoding="utf-8")

    with pytest.raises(NoIntroParseError):
        NoIntroParser().parse(path)


def test_filename_parser_preserves_convention_tokens() -> None:
    info = parse_name("Game Title (USA, Europe) (En,Ja) (Rev 1) (Aftermarket) (Unl).nes")

    assert info.title == "Game Title"
    assert info.region == "USA, Europe"
    assert info.languages == ("En", "Ja")
    assert info.version == "Rev 1"
    assert info.additional == ("Aftermarket", "Unl")
