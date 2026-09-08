"""Amostra pequena e estratificada do catalogo real para validar merge.

A amostra nao usa os primeiros registros do banco, pois isso tende a produzir
apenas self-merge. Em vez disso, coleta candidatos limitados e distribui os
casos entre self, romof, parent e destinos externos/nao resolvidos. O teste nao
altera o banco.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().parents[1] / "data" / "database" / "serm.db"
SAMPLE_SIZE = 30
CANDIDATE_LIMIT = 1000


def _latest_import(db: sqlite3.Connection) -> int:
    row = db.execute(
        "SELECT id FROM mame_listxml_import "
        "WHERE status='completed' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row is not None, "Nenhuma importacao ListXML concluida."
    return int(row[0])


def _candidate_rows(db: sqlite3.Connection, import_id: int) -> list[sqlite3.Row]:
    db.row_factory = sqlite3.Row
    return db.execute(
        """
        SELECT r.machine_id, m.name AS machine_name,
               m.cloneof, m.romof,
               r.name AS rom_name, r.merge AS merge_name,
               r.sha1, r.crc, r.size
        FROM mame_rom r
        JOIN mame_machine m ON m.id = r.machine_id
        WHERE m.import_id = ?
          AND trim(COALESCE(r.merge, '')) <> ''
        ORDER BY lower(m.name), lower(r.name)
        LIMIT ?
        """,
        (import_id, CANDIDATE_LIMIT),
    ).fetchall()


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

    # Keep the same semantic priority as the production planner: self, romof,
    # then parent. An unrelated global name match is never accepted.
    preferred = (
        ("SELF", machine),
        ("ROMOF", romof),
        ("CLONEOF/PARENT", cloneof),
    )
    for kind, preferred_machine in preferred:
        if not preferred_machine:
            continue
        matches = [
            target
            for target in targets
            if target["machine_name"].casefold() == preferred_machine
        ]
        if len(matches) == 1:
            return kind, matches[0]
        if len(matches) > 1:
            return "AMBIGUOUS", None

    if targets:
        return "UNRELATED", None
    return "UNRESOLVED", None


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


def _select_stratified(
    db: sqlite3.Connection,
    import_id: int,
) -> list[tuple[sqlite3.Row, str, sqlite3.Row | None]]:
    selected: list[tuple[sqlite3.Row, str, sqlite3.Row | None]] = []
    seen: set[tuple[int, str]] = set()
    buckets = {"SELF": 0, "ROMOF": 0, "CLONEOF/PARENT": 0, "AMBIGUOUS": 0, "UNRELATED": 0, "UNRESOLVED": 0}
    target_per_bucket = 5

    for row in _candidate_rows(db, import_id):
        key = (int(row["machine_id"]), row["rom_name"].casefold())
        if key in seen:
            continue
        kind, target = _relation(row, _targets(db, import_id, row["merge_name"]))
        if buckets.get(kind, 0) >= target_per_bucket:
            continue
        buckets[kind] = buckets.get(kind, 0) + 1
        seen.add(key)
        selected.append((row, kind, target))
        if len(selected) >= SAMPLE_SIZE:
            break

    return selected


def test_real_merge_sample_is_bounded_and_stratified():
    assert DB_FILE.exists(), f"Banco nao encontrado: {DB_FILE}"

    with sqlite3.connect(DB_FILE) as db:
        import_id = _latest_import(db)
        selected = _select_stratified(db, import_id)
        assert 0 < len(selected) <= SAMPLE_SIZE

        relation_counts: dict[str, int] = {}
        identity_counts: dict[str, int] = {}

        for row, relation, target in selected:
            relation_counts[relation] = relation_counts.get(relation, 0) + 1
            identity = _identity(row, target)
            identity_counts[identity] = identity_counts.get(identity, 0) + 1
            target_name = target["machine_name"] if target else "-"
            print(
                f"  {row['machine_name']} :: {row['rom_name']} "
                f"merge={row['merge_name']} -> {relation} "
                f"target={target_name} identity={identity}"
            )

        print(f"IMPORT ID: {import_id}")
        print(f"AMOSTRA: {len(selected)}/{SAMPLE_SIZE} (candidatos limitados a {CANDIDATE_LIMIT})")
        print("RELACOES:")
        for key, value in sorted(relation_counts.items()):
            print(f"  {key:<22}: {value:>3}")
        print("IDENTIDADE:")
        for key, value in sorted(identity_counts.items()):
            print(f"  {key:<22}: {value:>3}")
        print("RESULTADO: amostra limitada e estratificada; nenhuma alteracao no banco.")
