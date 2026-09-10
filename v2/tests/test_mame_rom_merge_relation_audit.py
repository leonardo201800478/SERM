"""Auditoria relacional dos destinos de ``merge`` no ListXML MAME.

Nao modifica o banco. Classifica cada merge pela relacao entre a maquina
que declara a ROM e a maquina que efetivamente contem a ROM alvo.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().parents[1] / "data" / "database" / "serm.db"


def main() -> int:
    if not DB_FILE.exists():
        raise SystemExit(f"Banco nao encontrado: {DB_FILE}")

    with sqlite3.connect(DB_FILE) as db:
        latest = db.execute(
            "SELECT id,mame_build,source_hash FROM mame_listxml_import "
            "WHERE status='completed' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if latest is None:
            raise SystemExit("Nenhuma importacao ListXML MAME concluida.")
        import_id, build, source_hash = latest
        print(f"IMPORT: id={import_id} build={build} hash={source_hash}")

        query = """
        WITH merge_rows AS (
            SELECT r.machine_id, m.name AS machine_name,
                   m.cloneof, m.romof,
                   r.name AS rom_name, r.merge AS merge_name,
                   r.sha1 AS source_sha1, r.crc AS source_crc,
                   r.size AS source_size
            FROM mame_rom r
            JOIN mame_machine m ON m.id = r.machine_id
            WHERE m.import_id = ?
              AND trim(COALESCE(r.merge, '')) <> ''
        ),
        targets AS (
            SELECT mr.*, t.machine_id AS target_machine_id,
                   tm.name AS target_machine_name,
                   t.name AS target_rom_name,
                   t.sha1 AS target_sha1, t.crc AS target_crc,
                   t.size AS target_size
            FROM merge_rows mr
            LEFT JOIN mame_rom t
              ON lower(t.name) = lower(mr.merge_name)
            LEFT JOIN mame_machine tm
              ON tm.id = t.machine_id AND tm.import_id = ?
        )
        SELECT machine_id, machine_name, cloneof, romof,
               rom_name, merge_name,
               source_sha1, source_crc, source_size,
               target_machine_id, target_machine_name,
               target_rom_name, target_sha1, target_crc, target_size
        FROM targets
        """
        rows = db.execute(query, (import_id, import_id)).fetchall()

        categories = {
            "SELF": 0,
            "ROMOF": 0,
            "CLONEOF/PARENT": 0,
            "OTHER": 0,
            "UNRESOLVED": 0,
            "AMBIGUOUS": 0,
        }
        identity = {"MATCH": 0, "MISMATCH": 0, "UNKNOWN": 0}
        examples: dict[str, list[tuple]] = {key: [] for key in categories}

        grouped: dict[tuple[int, str], list[tuple]] = {}
        for row in rows:
            grouped.setdefault((row[0], row[5].casefold()), []).append(row)

        for candidates in grouped.values():
            row0 = candidates[0]
            machine_id, machine_name, cloneof, romof = row0[:4]
            if not candidates or candidates[0][9] is None:
                kind = "UNRESOLVED"
            elif len(candidates) > 1:
                # Multiple catalogued machines contain the same merge name.
                # Relation is therefore ambiguous until identity is compared.
                kind = "AMBIGUOUS"
            else:
                target_machine_name = candidates[0][10]
                if target_machine_name.casefold() == machine_name.casefold():
                    kind = "SELF"
                elif romof and target_machine_name.casefold() == romof.casefold():
                    kind = "ROMOF"
                elif cloneof and target_machine_name.casefold() == cloneof.casefold():
                    kind = "CLONEOF/PARENT"
                else:
                    kind = "OTHER"

            categories[kind] += len(candidates)
            if len(examples[kind]) < 10:
                examples[kind].append(row0)

            for row in candidates:
                source_sha1, source_crc, source_size = row[6:9]
                target_sha1, target_crc, target_size = row[11:14]
                if target_sha1 and source_sha1:
                    identity["MATCH" if target_sha1.casefold() == source_sha1.casefold() else "MISMATCH"] += 1
                elif target_crc and source_crc and target_size and source_size:
                    identity["MATCH" if (target_crc.casefold() == source_crc.casefold() and target_size == source_size) else "MISMATCH"] += 1
                else:
                    identity["UNKNOWN"] += 1

        print("\nCATEGORIAS DE RELACAO:")
        for key, value in categories.items():
            print(f"  {key:<16}: {value:>8,}")

        print("\nIDENTIDADE DO ALVO:")
        for key, value in identity.items():
            print(f"  {key:<16}: {value:>8,}")

        print("\nAMOSTRAS:")
        for key, values in examples.items():
            if not values:
                continue
            print(f"\n[{key}]")
            for row in values:
                print("  ", row)

        print("\nRESULTADO: auditoria somente leitura; nenhuma alteracao foi feita no banco.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
