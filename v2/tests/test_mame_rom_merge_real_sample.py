"""Amostra pequena do catalogo real para validar semantica de merge.

Diferente da auditoria completa, este teste consulta somente uma quantidade
limitada de casos reais da ultima importacao ListXML concluida. Ele nao altera
o banco e foi desenhado para execucao frequente durante o desenvolvimento.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().parents[1] / "data" / "database" / "serm.db"
SAMPLE_SIZE = 30


def _latest_import(db: sqlite3.Connection) -> int:
    row = db.execute(
        "SELECT id FROM mame_listxml_import "
        "WHERE status='completed' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row is not None, "Nenhuma importacao ListXML concluida."
    return int(row[0])


def _sample_merge_rows(db: sqlite3.Connection, import_id: int) -> list[sqlite3.Row]:
    db.row_factory = sqlite3.Row
    query = """
        SELECT r.machine_id, m.name AS machine_name,
               m.cloneof, m.romof,
               r.name AS rom_name, r.merge AS merge_name,
               r.sha1, r.crc, r.size
        FROM mame_rom r
        JOIN mame_machine m ON m.id = r.machine_id
        WHERE m.import_id = ?
          AND trim(COALESCE(r.merge, '')) <> ''
        ORDER BY r.machine_id, lower(r.name)
        LIMIT ?
    """
    return db.execute(query, (import_id, SAMPLE_SIZE)).fetchall()


def _targets(
    db: sqlite3.Connection,
    import_id: int,
    merge_name: str,
) -> list[sqlite3.Row]:
    db.row_factory = sqlite3.Row
    return db.execute(
        """
        SELECT t.machine_id, m.name AS machine_name,
               t.name AS rom_name, t.sha1, t.crc, t.size
        FROM mame_rom t
        JOIN mame_machine m ON m.id = t.machine_id
        WHERE m.import_id = ?
          AND lower(t.name) = lower(?)
        ORDER BY t.machine_id
        """,
        (import_id, merge_name),
    ).fetchall()


def _relation(row: sqlite3.Row, targets: list[sqlite3.Row]) -> str:
    machine = row["machine_name"]
    romof = (row["romof"] or "").casefold()
    cloneof = (row["cloneof"] or "").casefold()

    preferred = []
    for target in targets:
        target_machine = target["machine_name"]
        target_key = target_machine.casefold()
        if target_key == machine.casefold():
            preferred.append(("SELF", target))
        elif romof and target_key == romof:
            preferred.append(("ROMOF", target))
        elif cloneof and target_key == cloneof:
            preferred.append(("CLONEOF/PARENT", target))

    if not preferred:
        return "UNRELATED/UNRESOLVED"

    kinds = {kind for kind, _ in preferred}
    if len(preferred) > 1 or len(kinds) > 1:
        return "AMBIGUOUS"
    return preferred[0][0]


def _identity(row: sqlite3.Row, target: sqlite3.Row) -> str:
    if row["sha1"] and target["sha1"]:
        return "MATCH" if row["sha1"].casefold() == target["sha1"].casefold() else "MISMATCH"
    if row["crc"] and target["crc"] and row["size"] and target["size"]:
        return "MATCH" if (
            row["crc"].casefold() == target["crc"].casefold()
            and row["size"] == target["size"]
        ) else "MISMATCH"
    return "UNKNOWN"


def test_real_merge_sample_is_bounded_and_inspectable():
    assert DB_FILE.exists(), f"Banco nao encontrado: {DB_FILE}"

    with sqlite3.connect(DB_FILE) as db:
        import_id = _latest_import(db)
        rows = _sample_merge_rows(db, import_id)

        assert 0 < len(rows) <= SAMPLE_SIZE

        relation_counts: dict[str, int] = {}
        identity_counts: dict[str, int] = {}
        inspected = 0

        for row in rows:
            targets = _targets(db, import_id, row["merge_name"])
            relation = _relation(row, targets)
            relation_counts[relation] = relation_counts.get(relation, 0) + 1

            related_targets = [
                target
                for target in targets
                if target["machine_name"].casefold()
                in {
                    row["machine_name"].casefold(),
                    (row["romof"] or "").casefold(),
                    (row["cloneof"] or "").casefold(),
                }
            ]
            if len(related_targets) == 1:
                identity = _identity(row, related_targets[0])
                identity_counts[identity] = identity_counts.get(identity, 0) + 1
            else:
                identity_counts["UNKNOWN"] = identity_counts.get("UNKNOWN", 0) + 1

            inspected += 1

        print(f"IMPORT ID: {import_id}")
        print(f"AMOSTRA: {inspected}/{SAMPLE_SIZE}")
        print("RELACOES:")
        for key, value in sorted(relation_counts.items()):
            print(f"  {key:<22}: {value:>3}")
        print("IDENTIDADE:")
        for key, value in sorted(identity_counts.items()):
            print(f"  {key:<22}: {value:>3}")
        print("RESULTADO: amostra limitada; nenhuma alteracao no banco.")
