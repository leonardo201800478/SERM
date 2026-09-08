"""Amostra dirigida do catalogo real para validar casos nao triviais de merge.

A selecao usa uma leitura linear do catalogo e resolve as relacoes em memoria.
O teste nao altera o banco.
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


def _norm(value: object) -> str:
    return str(value or "").strip().casefold()


def _load_catalog(
    db: sqlite3.Connection, import_id: int
) -> tuple[list[sqlite3.Row], dict[int, tuple[str, str, str]]]:
    """Carrega ROMs e maquinas uma vez, sem subconsultas correlacionadas."""
    db.row_factory = sqlite3.Row
    machines = {
        int(row["id"]): (
            row["name"],
            _norm(row["cloneof"]),
            _norm(row["romof"]),
        )
        for row in db.execute(
            """
            SELECT id, name, cloneof, romof
            FROM mame_machine
            WHERE import_id = ?
            """,
            (import_id,),
        )
    }
    roms = db.execute(
        """
        SELECT r.machine_id, r.name AS rom_name, r.merge AS merge_name,
               r.sha1, r.crc, r.size, r.status
        FROM mame_rom r
        JOIN mame_machine m ON m.id = r.machine_id
        WHERE m.import_id = ?
          AND trim(COALESCE(r.merge, '')) <> ''
        ORDER BY r.machine_id, lower(r.name)
        """,
        (import_id,),
    ).fetchall()
    return roms, machines


def _load_targets(
    db: sqlite3.Connection, import_id: int
) -> dict[str, list[sqlite3.Row]]:
    """Indexa todas as ROMs do import por nome normalizado."""
    db.row_factory = sqlite3.Row
    index: dict[str, list[sqlite3.Row]] = {}
    rows = db.execute(
        """
        SELECT r.machine_id, m.name AS machine_name,
               r.name AS rom_name, r.sha1, r.crc, r.size, r.status
        FROM mame_rom r
        JOIN mame_machine m ON m.id = r.machine_id
        WHERE m.import_id = ?
        """,
        (import_id,),
    )
    for row in rows:
        index.setdefault(_norm(row["rom_name"]), []).append(row)
    return index


def _classify(
    row: sqlite3.Row,
    machines: dict[int, tuple[str, str, str]],
    targets: dict[str, list[sqlite3.Row]],
) -> tuple[str, sqlite3.Row | None]:
    machine_name, cloneof, romof = machines[int(row["machine_id"])]
    machine = _norm(machine_name)
    candidates = targets.get(_norm(row["merge_name"]), [])

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
            for target in candidates
            if _norm(target["machine_name"]) == preferred_machine
        ]
        if len(matches) == 1:
            return kind, matches[0]
        if len(matches) > 1:
            return "AMBIGUOUS", None

    if len(candidates) > 1:
        return "AMBIGUOUS", None
    if candidates:
        return "UNRELATED", candidates[0]
    return "UNRESOLVED", None


def _identity(row: sqlite3.Row, target: sqlite3.Row | None) -> str:
    if target is None:
        return "UNKNOWN"
    if row["sha1"] and target["sha1"]:
        return "MATCH" if _norm(row["sha1"]) == _norm(target["sha1"]) else "MISMATCH"
    if row["crc"] and target["crc"] and row["size"] and target["size"]:
        return (
            "MATCH"
            if _norm(row["crc"]) == _norm(target["crc"])
            and row["size"] == target["size"]
            else "MISMATCH"
        )
    return "UNKNOWN"


def test_real_merge_sample_covers_nontrivial_categories():
    assert DB_FILE.exists(), f"Banco nao encontrado: {DB_FILE}"

    with sqlite3.connect(DB_FILE) as db:
        import_id = _latest_import(db)
        roms, machines = _load_catalog(db, import_id)
        targets = _load_targets(db, import_id)

        selected: list[tuple[str, sqlite3.Row, sqlite3.Row | None]] = []
        seen: set[tuple[int, str, str]] = set()
        counts: dict[str, int] = {}

        for row in roms:
            bucket, target = _classify(row, machines, targets)
            if counts.get(bucket, 0) >= PER_BUCKET:
                continue

            key = (int(row["machine_id"]), _norm(row["rom_name"]), _norm(row["merge_name"]))
            if key in seen:
                continue
            seen.add(key)
            selected.append((bucket, row, target))
            counts[bucket] = counts.get(bucket, 0) + 1

            machine_name = machines[int(row["machine_id"])][0]
            target_name = target["machine_name"] if target else "-"
            print(
                f"  {machine_name} :: {row['rom_name']} "
                f"merge={row['merge_name']} -> {bucket} "
                f"target={target_name} identity={_identity(row, target)}"
            )

            if all(counts.get(bucket, 0) >= PER_BUCKET for bucket in BUCKETS):
                break

        print(f"\nIMPORT ID: {import_id}")
        print(f"TOTAL AMOSTRADO: {len(selected)}")
        print("COBERTURA:")
        for bucket in BUCKETS:
            print(f"  {bucket:<18}: {counts.get(bucket, 0):>3}")
        print("RESULTADO: amostra dirigida; nenhuma alteracao no banco.")

        assert selected, "Nenhum caso real de merge foi encontrado."
