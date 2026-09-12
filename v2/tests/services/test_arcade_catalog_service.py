"""Testes do adaptador SQLite do catálogo Arcade."""

from __future__ import annotations

import sqlite3

from serm_v2.domain.arcade import MachineKind
from serm_v2.services.arcade_catalog_service import SqliteArcadeCatalog


SCHEMA = """
CREATE TABLE mame_listxml_import (
    id INTEGER PRIMARY KEY, status TEXT NOT NULL
);
CREATE TABLE mame_machine (
    id INTEGER PRIMARY KEY, import_id INTEGER NOT NULL, name TEXT NOT NULL,
    sourcefile TEXT, isbios TEXT, isdevice TEXT, ismechanical TEXT,
    runnable TEXT, cloneof TEXT, romof TEXT, description TEXT, year TEXT,
    manufacturer TEXT
);
CREATE TABLE mame_rom (
    id INTEGER PRIMARY KEY, machine_id INTEGER NOT NULL, name TEXT NOT NULL,
    size INTEGER, crc TEXT, sha1 TEXT, md5 TEXT, merge TEXT, region TEXT,
    status TEXT, optional TEXT
);
CREATE TABLE mame_display (
    id INTEGER PRIMARY KEY, machine_id INTEGER NOT NULL, tag TEXT, type TEXT,
    width INTEGER, height INTEGER, refresh_hz REAL, rotate TEXT
);
"""


def make_db(path):
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    db.execute("INSERT INTO mame_listxml_import VALUES (1, 'completed')")
    db.execute("INSERT INTO mame_listxml_import VALUES (2, 'captured')")
    db.executemany(
        """INSERT INTO mame_machine
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        [
            (1, 1, "parent", "src/parent.cpp", None, None, None, "yes", None, None, "Parent", "1985", "Maker"),
            (2, 1, "clone", "src/parent.cpp", None, None, None, "yes", "parent", "parent", "Clone", "1986", "Maker"),
            (3, 2, "partial", None, None, None, None, "yes", None, None, "Ignored", "2000", "Maker"),
            (4, 1, "bios", None, "yes", None, None, "yes", None, None, "BIOS", None, "Maker"),
            (5, 1, "device", None, None, "yes", None, "yes", None, None, "Device", None, "Maker"),
            (6, 1, "mechanical", None, None, None, "yes", "yes", None, None, "Mechanical", None, "Maker"),
            (7, 1, "nonrun", None, None, None, None, "no", None, None, "Non runnable", None, "Maker"),
        ],
    )
    db.executemany(
        """INSERT INTO mame_rom
        (id,machine_id,name,size,crc,sha1,md5,merge,region,status)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        [
            (1, 1, "parent.rom", 1024, "deadbeef", "sha", None, None, None, "ok"),
            (2, 2, "clone.rom", 2048, "cafebabe", "sha2", None, "parent.rom", None, "ok"),
        ],
    )
    db.execute("INSERT INTO mame_display VALUES (1,1,'screen','raster',320,240,60.0,'0')")
    db.commit()
    db.close()


def test_reads_only_latest_completed_import(tmp_path):
    path = tmp_path / "serm.db"
    make_db(path)
    catalog = SqliteArcadeCatalog(path)
    assert catalog.count() == 6
    assert catalog.get_game("partial") is None


def test_maps_parent_clone_rom_and_display(tmp_path):
    path = tmp_path / "serm.db"
    make_db(path)
    catalog = SqliteArcadeCatalog(path)
    game = catalog.get_game("clone")
    assert game is not None
    assert game.is_clone
    assert game.cloneof == "parent"
    assert game.romof == "parent"
    assert game.roms[0].merge == "parent.rom"
    parent = catalog.get_game("parent")
    assert parent is not None
    assert parent.is_parent
    assert parent.playable
    assert parent.displays[0].width == 320
    assert parent.displays[0].refresh_hz == 60.0


def test_maps_machine_kinds(tmp_path):
    path = tmp_path / "serm.db"
    make_db(path)
    catalog = SqliteArcadeCatalog(path)
    assert catalog.get_game("bios").machine_kind is MachineKind.BIOS
    assert catalog.get_game("device").machine_kind is MachineKind.DEVICE
    assert catalog.get_game("mechanical").machine_kind is MachineKind.MECHANICAL
    assert catalog.get_game("nonrun").machine_kind is MachineKind.NON_RUNNABLE


def test_iter_games_is_stable_and_batched(tmp_path):
    path = tmp_path / "serm.db"
    make_db(path)
    catalog = SqliteArcadeCatalog(path)
    catalog.MACHINE_BATCH_SIZE = 2
    games = list(catalog.iter_games())
    assert [game.name for game in games] == ["bios", "clone", "device", "mechanical", "nonrun", "parent"]
