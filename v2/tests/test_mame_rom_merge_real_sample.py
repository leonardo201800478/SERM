"""Amostra dirigida do catalogo real para validar casos nao triviais de merge.

A selecao e feita em memoria a partir de duas leituras lineares do catalogo:
uma para os registros com ``merge`` e outra para as ROMs que podem ser alvos.
Isso evita subconsultas correlacionadas e N+1 queries, que tornam a auditoria
muito lenta em catalogos MAME reais.

O teste e somente leitura e nao altera o banco.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
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


def _load_rows(
    db: sqlite3.Connection,
    import_id: int,
) -> tuple[list[sqlite3.Row], dict[str, list[sqlite3.Row]]]:
    """Carrega o catalogo relevante em duas passagens lineares.

    ``target_index`` e indexado pelo nome da ROM, permitindo resolver todos os
    candidatos sem executar uma consulta para cada linha.
    """
    db.row_factory = sqlite3.Row

    merge_rows = db.execute(
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
        """,
        (import_id,),
    ).fetchall()

    target_index: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in db.execute(
        """
        SELECT r.machine_id, m.name AS machine_name,
               r.name AS rom_name, r.sha1, r.crc, r.size
        FROM mame_rom r
        JOIN mame_machine m ON m.id = r.machine_id
        WHERE m.import_id = ?
        """,
        (import_id,),
    ):
        name = str(row["rom_name"] or "").strip().casefold()
        if name:
            target_index[name].append(row)

    return list(merge_rows), dict(target_index)


def _relation(
    row: sqlite3.Row,
    targets: list[sqlite3.Row],
) -> tuple[str, sqlite3.Row | None]:
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
            target
            for target in targets
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
        return (
            "MATCH"
            if row["sha1"].casefold() == target["sha1"].casefold()
            else "MISMATCH"
        )
    if row["crc"] and target["crc"] and row["size"] and target["size"]:
        return (
            "MATCH"
            if row["crc"].casefold() == target["crc"].casefold()
            and row["size"] == target["size"]
            else "MISMATCH"
        )
    return "UNKNOWN"


def _bucket_for_row(
    row: sqlite3.Row,
    target_index: dict[str, list[sqlite3.Row]],
) -> tuple[str, sqlite3.Row | None]:
    merge_name = str(row["merge_name"] or "").strip().casefold()
    return _relation(row, target_index.get(merge_name, []))


def test_real_merge_sample_covers_nontrivial_categories():
    assert DB_FILE.exists(), f"Banco nao encontrado: {DB_FILE}"

    with sqlite3.connect(DB_FILE) as db:
        import_id = _latest_import(db)
        merge_rows, target_index = _load_rows(db, import_id)

        selected: dict[str, list[sqlite3.Row]] = {bucket: [] for bucket in BUCKETS}

        for row in merge_rows:
            bucket, _ = _bucket_for_row(row, target_index)
            if bucket in selected and len(selected[bucket]) < PER_BUCKET:
                selected[bucket].append(row)

            if all(len(selected[item]) >= PER_BUCKET for item in BUCKETS):
                break

        total = sum(len(rows) for rows in selected.values())
        assert total, "Nenhum caso real de merge foi encontrado."

        for bucket in BUCKETS:
            rows = selected[bucket]
            print(f"\n[{bucket}] candidatos={len(rows)}")
            for row in rows:
                targets = target_index.get(
                    str(row["merge_name"] or "").strip().casefold(), []
                )
                relation, target = _relation(row, targets)
                identity = _identity(row, target)
                target_name = target["machine_name"] if target else "-"
                print(
                    f"  {row['machine_name']} :: {row['rom_name']} "
                    f"merge={row['merge_name']} -> {relation} "
                    f"target={target_name} identity={identity}"
                )

        print(f"\nIMPORT ID: {import_id}")
        print(f"TOTAL AMOSTRADO: {total}")
        print("COBERTURA:")
        for bucket in BUCKETS:
            print(f"  {bucket:<18}: {len(selected[bucket]):>3}")
        print("RESULTADO: amostra dirigida; nenhuma alteracao no banco.")
