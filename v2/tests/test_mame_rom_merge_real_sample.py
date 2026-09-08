"""Amostra dirigida do catalogo real para validar casos nao triviais de merge.

A selecao e feita diretamente pelos relacionamentos existentes no catalogo,
em vez de depender da ordem alfabetica dos primeiros registros. O teste nao
altera o banco.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().parents[1] / "data" / "database" / "serm.db"
PER_BUCKET = 5


BUCKETS = (
    "SELF",
    "ROMOF",
    "CLONEOF/PARENT",
    "AMBIGUOUS",
    "UNRELATED",
    "UNRESOLVED",
)


def _latest_import(db: sqlite3.Connection) -> int:
    row = db.execute(
        "SELECT id FROM mame_listxml_import "
        "WHERE status='completed' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row is not None, "Nenhuma importacao ListXML concluida."
    return int(row[0])


def _candidate_query(bucket: str) -> str:
    base = """
        SELECT r.machine_id, m.name AS machine_name,
               m.cloneof, m.romof,
               r.name AS rom_name, r.merge AS merge_name,
               r.sha1, r.crc, r.size
        FROM mame_rom r
        JOIN mame_machine m ON m.id = r.machine_id
        WHERE m.import_id = ?
          AND trim(COALESCE(r.merge, '')) <> ''
    """

    target_count = """
        (SELECT COUNT(*)
           FROM mame_rom t
           JOIN mame_machine tm ON tm.id = t.machine_id
          WHERE tm.import_id = m.import_id
            AND lower(t.name) = lower(r.merge))
    """

    if bucket == "SELF":
        return base + """
          AND EXISTS (
              SELECT 1 FROM mame_rom t
              JOIN mame_machine tm ON tm.id = t.machine_id
              WHERE tm.import_id = m.import_id
                AND tm.name = m.name
                AND lower(t.name) = lower(r.merge)
          )
          ORDER BY lower(m.name), lower(r.name)
          LIMIT ?
        """

    if bucket == "ROMOF":
        return base + """
          AND trim(COALESCE(m.romof, '')) <> ''
          AND EXISTS (
              SELECT 1 FROM mame_rom t
              JOIN mame_machine tm ON tm.id = t.machine_id
              WHERE tm.import_id = m.import_id
                AND lower(tm.name) = lower(m.romof)
                AND lower(t.name) = lower(r.merge)
          )
          ORDER BY lower(m.name), lower(r.name)
          LIMIT ?
        """

    if bucket == "CLONEOF/PARENT":
        return base + """
          AND trim(COALESCE(m.cloneof, '')) <> ''
          AND EXISTS (
              SELECT 1 FROM mame_rom t
              JOIN mame_machine tm ON tm.id = t.machine_id
              WHERE tm.import_id = m.import_id
                AND lower(tm.name) = lower(m.cloneof)
                AND lower(t.name) = lower(r.merge)
          )
          ORDER BY lower(m.name), lower(r.name)
          LIMIT ?
        """

    if bucket == "AMBIGUOUS":
        return base + f"""
          AND {target_count} > 1
          AND NOT EXISTS (
              SELECT 1 FROM mame_rom t
              JOIN mame_machine tm ON tm.id = t.machine_id
              WHERE tm.import_id = m.import_id
                AND lower(tm.name) = lower(m.name)
                AND lower(t.name) = lower(r.merge)
          )
          AND NOT EXISTS (
              SELECT 1 FROM mame_rom t
              JOIN mame_machine tm ON tm.id = t.machine_id
              WHERE tm.import_id = m.import_id
                AND lower(tm.name) = lower(m.romof)
                AND lower(t.name) = lower(r.merge)
          )
          AND NOT EXISTS (
              SELECT 1 FROM mame_rom t
              JOIN mame_machine tm ON tm.id = t.machine_id
              WHERE tm.import_id = m.import_id
                AND lower(tm.name) = lower(m.cloneof)
                AND lower(t.name) = lower(r.merge)
          )
          ORDER BY lower(m.name), lower(r.name)
          LIMIT ?
        """

    if bucket == "UNRELATED":
        return base + f"""
          AND {target_count} > 0
          AND NOT EXISTS (
              SELECT 1 FROM mame_rom t
              JOIN mame_machine tm ON tm.id = t.machine_id
              WHERE tm.import_id = m.import_id
                AND lower(tm.name) IN (
                    lower(m.name), lower(m.romof), lower(m.cloneof)
                )
                AND lower(t.name) = lower(r.merge)
          )
          ORDER BY lower(m.name), lower(r.name)
          LIMIT ?
        """

    return base + f"""
          AND {target_count} = 0
          ORDER BY lower(m.name), lower(r.name)
          LIMIT ?
    """


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


def _relation(row: sqlite3.Row, targets: list[sqlite3.Row]) -> tuple[str, sqlite3.Row | None]:
    machine = row["machine_name"].casefold()
    romof = (row["romof"] or "").casefold()
    cloneof = (row["cloneof"] or "").casefold()

    for kind, preferred_machine in (
        ("SELF", machine),
        ("ROMOF", romof),
        ("CLONEOF/PARENT", cloneof),
    ):
        if not preferred_machine:
            continue
        matches = [
            target for target in targets
            if target["machine_name"].casefold() == preferred_machine
        ]
        if len(matches) == 1:
            return kind, matches[0]
        if len(matches) > 1:
            return "AMBIGUOUS", None

    return ("UNRELATED" if targets else "UNRESOLVED"), None


def _identity(row: sqlite3.Row, target: sqlite3.Row | None) -> str:
    if target is None:
        return "UNKNOWN"
    if row["sha1"] and target["sha1"]:
        return "MATCH" if row["sha1"].casefold() == target["sha1"].casefold() else "MISMATCH"
    if row["crc"] and target["crc"] and row["size"] and target["size"]:
        return "MATCH" if (
            row["crc"].casefold() == target["crc"].casefold()
            and row["size"] == target["size"]
        ) else "MISMATCH"
    return "UNKNOWN"


def test_real_merge_sample_covers_nontrivial_categories():
    assert DB_FILE.exists(), f"Banco nao encontrado: {DB_FILE}"

    with sqlite3.connect(DB_FILE) as db:
        import_id = _latest_import(db)
        db.row_factory = sqlite3.Row
        selected: list[tuple[str, sqlite3.Row]] = []

        for bucket in BUCKETS:
            rows = db.execute(_candidate_query(bucket), (import_id, PER_BUCKET)).fetchall()
            print(f"\n[{bucket}] candidatos={len(rows)}")
            for row in rows:
                selected.append((bucket, row))
                targets = _targets(db, import_id, row["merge_name"])
                relation, target = _relation(row, targets)
                identity = _identity(row, target)
                target_name = target["machine_name"] if target else "-"
                print(
                    f"  {row['machine_name']} :: {row['rom_name']} "
                    f"merge={row['merge_name']} -> {relation} "
                    f"target={target_name} identity={identity}"
                )

        assert selected, "Nenhum caso real de merge foi encontrado."

        counts: dict[str, int] = {}
        for bucket, _ in selected:
            counts[bucket] = counts.get(bucket, 0) + 1

        print(f"\nIMPORT ID: {import_id}")
        print(f"TOTAL AMOSTRADO: {len(selected)}")
        print("COBERTURA:")
        for bucket in BUCKETS:
            print(f"  {bucket:<18}: {counts.get(bucket, 0):>3}")
        print("RESULTADO: amostra dirigida; nenhuma alteracao no banco.")
