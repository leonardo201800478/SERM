"""Read-only audit of MAME ROM identity distribution.

The audit establishes whether SHA1/CRC/size lookups are selective enough for
future in-memory indexes or database indexes. It does not modify the DB.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().parents[1] / "data" / "database" / "serm.db"


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

        print(f"MAME IMPORT: {import_id}")

        queries = {
            "ROM rows": """
                SELECT COUNT(*) FROM mame_rom r
                JOIN mame_machine m ON m.id=r.machine_id
                WHERE m.import_id=?
            """,
            "SHA1 populated": """
                SELECT COUNT(*) FROM mame_rom r
                JOIN mame_machine m ON m.id=r.machine_id
                WHERE m.import_id=? AND trim(COALESCE(r.sha1,''))<>''
            """,
            "distinct SHA1": """
                SELECT COUNT(DISTINCT r.sha1) FROM mame_rom r
                JOIN mame_machine m ON m.id=r.machine_id
                WHERE m.import_id=? AND trim(COALESCE(r.sha1,''))<>''
            """,
            "distinct CRC+size": """
                SELECT COUNT(*) FROM (
                    SELECT r.crc, r.size
                    FROM mame_rom r JOIN mame_machine m ON m.id=r.machine_id
                    WHERE m.import_id=? AND trim(COALESCE(r.crc,''))<>''
                    GROUP BY r.crc, r.size
                )
            """,
            "SHA1 collisions": """
                SELECT COUNT(*) FROM (
                    SELECT r.sha1
                    FROM mame_rom r JOIN mame_machine m ON m.id=r.machine_id
                    WHERE m.import_id=? AND trim(COALESCE(r.sha1,''))<>''
                    GROUP BY r.sha1 HAVING COUNT(*)>1
                )
            """,
            "CRC+size collisions": """
                SELECT COUNT(*) FROM (
                    SELECT r.crc, r.size
                    FROM mame_rom r JOIN mame_machine m ON m.id=r.machine_id
                    WHERE m.import_id=? AND trim(COALESCE(r.crc,''))<>''
                    GROUP BY r.crc, r.size HAVING COUNT(*)>1
                )
            """,
        }

        for label, sql in queries.items():
            value = db.execute(sql, (import_id,)).fetchone()[0]
            print(f"{label}: {int(value):,}")

        print("\nRESULTADO: auditoria somente leitura; nenhuma alteracao foi feita.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
