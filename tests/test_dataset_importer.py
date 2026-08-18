from pathlib import Path
import tempfile
import sqlite3

from app.database.database import Database
from app.database.dataset_schema import ensure_dataset_schema
from app.mame.dataset_importer import DatasetImporter


def test_dataset_importer_populates_core_entities(tmp_path):
    db=Database(tmp_path/"test.db");db.connect();ensure_dataset_schema(db)
    db.execute("INSERT INTO mame_installation(version,executable_path,executable_hash) VALUES('0.289','mame.exe','test')")
    run=db.execute("INSERT INTO dataset_run(mame_installation_id,mame_version,xml_path,status) VALUES(1,'0.289','test.xml','running')").lastrowid
    xml=tmp_path/"list.xml"
    xml.write_text('''<?xml version="1.0"?><mame><machine name="testgame" sourcefile="test.cpp"><description>Test Game</description><year>1985</year><manufacturer>Test</manufacturer><rom name="a.bin" size="4" crc="12345678" sha1="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"/><disk name="disk" sha1="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"/><biosset name="default" description="Default" default="yes"/><chip type="cpu" tag="maincpu" name="Z80" clock="4000000"/><display tag="screen" type="raster" width="320" height="240" refresh="60"/><input players="2"><control type="joy" player="1" buttons="2"/></input><feature type="sound" status="imperfect"/><softwarelist tag="cart" name="test" status="original"/><slot name="slot"><slotoption name="default" devname="dev" default="yes"/></slot></machine></mame>''',encoding='utf-8')
    stats=DatasetImporter(db).import_xml(xml,run)
    assert stats["machines"]==1
    assert stats["roms"]==1
    assert stats["disks"]==1
    assert db.fetchone("SELECT description FROM machine WHERE name='testgame'")[0]=="Test Game"
    assert db.fetchone("SELECT name FROM rom WHERE machine_id=1")[0]=="a.bin"
    assert db.fetchone("SELECT name FROM disk WHERE machine_id=1")[0]=="disk"
    assert db.fetchone("SELECT name FROM bios WHERE machine_id=1")[0]=="default"
    assert db.fetchone("SELECT COUNT(*) FROM chip WHERE machine_id=1")[0]==1
    assert db.fetchone("SELECT COUNT(*) FROM control")[0]==1
    assert db.fetchone("SELECT COUNT(*) FROM slot_option")[0]==1
    db.close()
