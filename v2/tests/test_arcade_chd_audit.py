import sqlite3

from serm_v2.services.arcade.chd_audit import ArcadeChdAuditService
from serm_v2.services.chd_header import ChdFormatError, ChdHeader


class FakeReader:
    def __init__(self, headers: dict[str, ChdHeader]) -> None:
        self.headers = headers

    def read(self, path):
        if path.name == "bad.chd":
            raise ChdFormatError("invalid test CHD")
        return self.headers[str(path)]


def make_database(path, sha1: str) -> None:
    with sqlite3.connect(path) as db:
        db.executescript(
            """
            CREATE TABLE mame_listxml_import (
                id INTEGER PRIMARY KEY,
                status TEXT NOT NULL
            );
            CREATE TABLE mame_machine (
                id INTEGER PRIMARY KEY,
                import_id INTEGER NOT NULL,
                name TEXT NOT NULL
            );
            CREATE TABLE mame_disk (
                id INTEGER PRIMARY KEY,
                machine_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                sha1 TEXT,
                md5 TEXT
            );
            INSERT INTO mame_listxml_import VALUES (1, 'completed');
            INSERT INTO mame_machine VALUES (1, 1, 'game');
            INSERT INTO mame_disk VALUES (1, 1, 'disc', ?, NULL);
            """,
            (sha1,),
        )


def test_audit_matches_raw_sha1_and_reports_orphan(tmp_path) -> None:
    database = tmp_path / "serm.db"
    source = tmp_path / "chds"
    source.mkdir()
    good = source / "disc.chd"
    orphan = source / "orphan.chd"
    good.write_bytes(b"x")
    orphan.write_bytes(b"y")
    sha1 = "11" * 20
    orphan_sha1 = "22" * 20
    make_database(database, sha1)
    reader = FakeReader(
        {
            str(good): ChdHeader(5, 100, 4096, sha1, "33" * 20, None, "00" * 20, 1),
            str(orphan): ChdHeader(5, 200, 4096, orphan_sha1, "44" * 20, None, "00" * 20, 1),
        }
    )

    result = ArcadeChdAuditService(reader).audit(source=source, database=database)

    assert result.files_scanned == 2
    assert result.valid_files == 2
    assert result.matched_files == 1
    assert result.missing_disks == 0
    assert result.orphan_files == 1
    assert {record.status for record in result.records} == {"OK", "ORPHAN"}


def test_audit_reports_missing_and_invalid(tmp_path) -> None:
    database = tmp_path / "serm.db"
    source = tmp_path / "chds"
    source.mkdir()
    (source / "bad.chd").write_bytes(b"bad")
    make_database(database, "aa" * 20)
    result = ArcadeChdAuditService(FakeReader({})).audit(source=source, database=database)

    assert result.files_scanned == 1
    assert result.invalid_files == 1
    assert result.missing_disks == 1
    assert [record.status for record in result.records] == ["MISSING", "INVALID"]
