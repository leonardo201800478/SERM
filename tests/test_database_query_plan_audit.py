"""Read-only SQLite query-plan audit for the SERM database.

This test does not change schema, indexes, PRAGMAs, or data. It records the
query plans of representative MAME access patterns so performance changes can
be compared before and after future optimizations.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().parents[1] / "data" / "database" / "serm.db"

QUERIES = {
    "machines_by_import": """
        SELECT id, name, cloneof, romof
        FROM mame_machine
        WHERE import_id = ?
    """,
    "roms_by_machine": """
        SELECT name, sha1, crc, size, merge
        FROM mame_rom
        WHERE machine_id = ?
    """,
    "rom_identity": """
        SELECT machine_id, name
        FROM mame_rom
        WHERE sha1 = ?
    """,
    "merge_target": """
        SELECT t.machine_id, t.name, t.sha1, t.crc, t.size
        FROM mame_rom t
        JOIN mame_machine m ON m.id = t.machine_id
        WHERE m.import_id = ? AND lower(t.name) = lower(?)
    """,
    "machine_relations": """
        SELECT name, cloneof, romof, sampleof
        FROM mame_machine
        WHERE import_id = ? AND (cloneof IS NOT NULL OR romof IS NOT NULL)
    """,
}


def explain(db: sqlite3.Connection, sql: str, params: tuple[object, ...]) -> list[str]:
    rows = db.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
    return [str(row[3]) for row in rows]


def main() -> int:
    if not DB_FILE.is_file():
        raise SystemExit(f"Banco nao encontrado: {DB_FILE}")

    with sqlite3.connect(f"file:{DB_FILE.as_posix()}?mode=ro", uri=True) as db:
        latest = db.execute(
            "SELECT id FROM mame_listxml_import "
            "WHERE status='completed' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if latest is None:
            raise SystemExit("Nenhuma importacao ListXML MAME concluida.")
        import_id = int(latest[0])

        print(f"DB: {DB_FILE}")
        print(f"MAME IMPORT: {import_id}")
        print(f"SQLite: {sqlite3.sqlite_version}")

        params = {
            "machines_by_import": (import_id,),
            "roms_by_machine": (1,),
            "rom_identity": ("",),
            "merge_target": (import_id, ""),
            "machine_relations": (import_id,),
        }

        for name, sql in QUERIES.items():
            print(f"\n[{name}]")
            for detail in explain(db, sql, params[name]):
                print(f"  {detail}")

        print("\nRESULTADO: auditoria somente leitura; nenhuma alteracao foi feita.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
