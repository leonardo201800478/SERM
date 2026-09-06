from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATION = (
    Path(__file__).parents[1]
    / "serm_v2"
    / "database"
    / "migrations"
    / "009_mame_xml_node_remove_path_unique.sql"
)


def test_mame_xml_node_migration_removes_path_unique_and_preserves_fks(tmp_path: Path) -> None:
    """The migration must allow duplicate paths while preserving node IDs and FKs."""
    db_path = tmp_path / "test.db"
    with sqlite3.connect(db_path) as db:
        db.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE schema_migrations(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL);
            CREATE TABLE mame_listxml_import(id INTEGER PRIMARY KEY AUTOINCREMENT);
            CREATE TABLE mame_xml_node(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                import_id INTEGER NOT NULL REFERENCES mame_listxml_import(id) ON DELETE CASCADE,
                parent_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE CASCADE,
                machine_id INTEGER,
                element_name TEXT NOT NULL,
                ordinal INTEGER NOT NULL DEFAULT 0,
                xml_path TEXT NOT NULL,
                text_value TEXT,
                attributes_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(import_id, xml_path)
            );
            CREATE INDEX ix_mame_xml_node_machine ON mame_xml_node(import_id, machine_id);
            CREATE INDEX ix_mame_xml_node_element ON mame_xml_node(import_id, element_name);
            CREATE TABLE mame_machine(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                xml_node_id INTEGER REFERENCES mame_xml_node(id) ON DELETE SET NULL
            );
            INSERT INTO mame_listxml_import DEFAULT VALUES;
            INSERT INTO mame_xml_node(import_id,element_name,xml_path,attributes_json)
                VALUES(1,'machine','/mame/machine[0]','{}');
            INSERT INTO mame_machine(xml_node_id) VALUES(1);
        """
        )
        db.executescript(MIGRATION.read_text(encoding="utf-8"))
        db.commit()

    with sqlite3.connect(db_path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute(
            "INSERT INTO mame_xml_node(import_id,element_name,xml_path,attributes_json) VALUES(1,'machine','/mame/machine[0]','{}')"
        )
        rows = db.execute(
            "SELECT id,xml_path FROM mame_xml_node WHERE import_id=1 ORDER BY id"
        ).fetchall()
        assert rows == [(1, "/mame/machine[0]"), (2, "/mame/machine[0]")]
        assert db.execute("SELECT xml_node_id FROM mame_machine WHERE id=1").fetchone() == (1,)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
