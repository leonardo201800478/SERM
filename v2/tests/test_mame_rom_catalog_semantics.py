from __future__ import annotations

import sqlite3
from pathlib import Path


DB_FILE = Path(__file__).resolve().parents[1] / "data" / "database" / "serm.db"


def _db():
    if not DB_FILE.exists():
        return None
    return sqlite3.connect(DB_FILE)


def test_mame_rom_merge_targets_are_not_unresolved_by_name():
    db = _db()
    if db is None:
        return
    with db:
        latest = db.execute(
            "SELECT id FROM mame_listxml_import WHERE status='completed' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if latest is None:
            return
        import_id = latest[0]
        rows = db.execute(
            """SELECT r.machine_id, r.name, r.merge
               FROM mame_rom r JOIN mame_machine m ON m.id=r.machine_id
               WHERE m.import_id=? AND trim(COALESCE(r.merge,''))<>''""",
            (import_id,),
        ).fetchall()
        for machine_id, _name, merge in rows:
            local = db.execute(
                "SELECT 1 FROM mame_rom WHERE machine_id=? AND name=? LIMIT 1",
                (machine_id, merge),
            ).fetchone()
            if local is not None:
                continue
            cross = db.execute(
                """SELECT 1 FROM mame_machine m
                   JOIN mame_rom r ON r.machine_id=m.id
                   WHERE m.import_id=? AND r.name=? LIMIT 1""",
                (import_id, merge),
            ).fetchone()
            assert cross is not None, f"merge sem alvo catalogado: machine_id={machine_id} merge={merge}"


def test_mame_clone_relationships_have_catalogued_parent():
    db = _db()
    if db is None:
        return
    with db:
        latest = db.execute(
            "SELECT id FROM mame_listxml_import WHERE status='completed' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if latest is None:
            return
        import_id = latest[0]
        missing = db.execute(
            """SELECT m.name, m.cloneof
               FROM mame_machine m
               WHERE m.import_id=? AND trim(COALESCE(m.cloneof,''))<>''
                 AND NOT EXISTS (
                     SELECT 1 FROM mame_machine p
                     WHERE p.import_id=m.import_id AND p.name=m.cloneof
                 )""",
            (import_id,),
        ).fetchall()
        assert not missing, f"cloneof sem parent catalogado: {missing[:10]}"


def test_mame_rom_identity_is_preferred_over_rom_name_for_shared_sha1():
    db = _db()
    if db is None:
        return
    with db:
        latest = db.execute(
            "SELECT id FROM mame_listxml_import WHERE status='completed' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if latest is None:
            return
        import_id = latest[0]
        shared = db.execute(
            """SELECT sha1
               FROM mame_rom r JOIN mame_machine m ON m.id=r.machine_id
               WHERE m.import_id=? AND trim(COALESCE(r.sha1,''))<>''
               GROUP BY sha1 HAVING COUNT(DISTINCT m.id)>1 LIMIT 1""",
            (import_id,),
        ).fetchone()
        assert shared is not None
        sha1 = shared[0]
        rows = db.execute(
            """SELECT DISTINCT r.name
               FROM mame_rom r JOIN mame_machine m ON m.id=r.machine_id
               WHERE m.import_id=? AND r.sha1=?""",
            (import_id, sha1),
        ).fetchall()
        assert rows
