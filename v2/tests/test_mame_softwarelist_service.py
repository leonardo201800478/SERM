from pathlib import Path

from serm_v2.services.mame_softwarelist_service import MameSoftwareListService


def test_ingest_software_list(tmp_path: Path) -> None:
    database = tmp_path / "serm.db"
    hash_path = tmp_path / "hash"
    hash_path.mkdir()
    (hash_path / "test.xml").write_text(
        '''<?xml version="1.0"?>
<softwarelist name="test" description="Test list">
  <software name="game1" supported="yes">
    <description>Test Game</description>
    <year>1985</year>
    <publisher>Publisher</publisher>
    <info name="alt_title" value="Alternative" />
    <part name="cart" interface="cart">
      <feature name="slot" value="0" />
      <dataarea name="rom" size="16">
        <rom name="game.bin" size="16" crc="12345678" sha1="abcdef" />
      </dataarea>
      <diskarea name="disk">
        <disk name="game" md5="1234" sha1="5678" />
      </diskarea>
    </part>
  </software>
</softwarelist>
''',
        encoding="utf-8",
    )

    result = MameSoftwareListService(database, hash_path).ingest()
    assert result["files"] == 1
    assert result["imported"] == 1
    assert result["software"] == 1
    assert result["roms"] == 1
    assert result["disks"] == 1

    import sqlite3

    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM mame_softwarelist_source").fetchone()[0] == 1
        assert db.execute("SELECT name,year,publisher FROM mame_software").fetchone() == ("game1", "1985", "Publisher")
        assert db.execute("SELECT name,sha1 FROM mame_software_rom").fetchone() == ("game.bin", "abcdef")
        assert db.execute("SELECT name,sha1 FROM mame_software_disk").fetchone() == ("game", "5678")
        assert db.execute("SELECT name,value FROM mame_software_info").fetchone() == ("alt_title", "Alternative")


def test_unchanged_software_list_is_skipped(tmp_path: Path) -> None:
    database = tmp_path / "serm.db"
    hash_path = tmp_path / "hash"
    hash_path.mkdir()
    (hash_path / "test.xml").write_text(
        '<softwarelist name="test"><software name="one"><description>One</description></software></softwarelist>',
        encoding="utf-8",
    )

    service = MameSoftwareListService(database, hash_path)
    first = service.ingest()
    second = service.ingest()
    assert first["imported"] == 1
    assert second["imported"] == 0
    assert second["skipped"] == 1
