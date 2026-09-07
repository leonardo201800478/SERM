from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "database" / "serm.db"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "database" / "serm_database_audit.xml"


def qident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def add(parent: ET.Element, tag: str, text: object | None = None, **attrs: object) -> ET.Element:
    element = ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items() if v is not None})
    if text is not None:
        element.text = str(text)
    return element


def scalar(db: sqlite3.Connection, sql: str, params: Iterable[object] = ()) -> object:
    return db.execute(sql, tuple(params)).fetchone()[0]


def table_names(db: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def table_schema(db: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    return db.execute(f"PRAGMA table_info({qident(table)})").fetchall()


def indexes(db: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    return db.execute(f"PRAGMA index_list({qident(table)})").fetchall()


def index_columns(db: sqlite3.Connection, index_name: str) -> list[sqlite3.Row]:
    return db.execute(f"PRAGMA index_info({qident(index_name)})").fetchall()


def foreign_keys(db: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    return db.execute(f"PRAGMA foreign_key_list({qident(table)})").fetchall()


def normalized_type(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "INTEGER"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    if isinstance(value, bytes):
        return "BLOB"
    return "TEXT"


def column_stats(db: sqlite3.Connection, table: str, column: str) -> dict[str, object]:
    ident = qident(column)
    tbl = qident(table)
    total = int(scalar(db, f"SELECT COUNT(*) FROM {tbl}"))
    nulls = int(scalar(db, f"SELECT COUNT(*) FROM {tbl} WHERE {ident} IS NULL"))
    non_null = total - nulls
    distinct = int(scalar(db, f"SELECT COUNT(DISTINCT {ident}) FROM {tbl}"))

    stats: dict[str, object] = {
        "rows": total,
        "null": nulls,
        "non_null": non_null,
        "distinct": distinct,
    }

    if non_null:
        stats["empty"] = int(
            scalar(
                db,
                f"SELECT COUNT(*) FROM {tbl} WHERE {ident} IS NOT NULL AND CAST({ident} AS TEXT) = ''",
            )
        )
        stats["min_length"] = int(
            scalar(db, f"SELECT MIN(LENGTH(CAST({ident} AS TEXT))) FROM {tbl} WHERE {ident} IS NOT NULL")
        )
        stats["max_length"] = int(
            scalar(db, f"SELECT MAX(LENGTH(CAST({ident} AS TEXT))) FROM {tbl} WHERE {ident} IS NOT NULL")
        )

        # These are diagnostics, not assumptions about the declared SQLite type.
        types = db.execute(
            f"SELECT typeof({ident}), COUNT(*) FROM {tbl} "
            f"WHERE {ident} IS NOT NULL GROUP BY typeof({ident}) ORDER BY typeof({ident})"
        ).fetchall()
        stats["types"] = {str(row[0]): int(row[1]) for row in types}

        sample = db.execute(
            f"SELECT CAST({ident} AS TEXT) FROM {tbl} WHERE {ident} IS NOT NULL "
            f"ORDER BY rowid LIMIT 1"
        ).fetchone()
        if sample is not None:
            value = sample[0]
            digest = hashlib.sha256(str(value).encode("utf-8", "replace")).hexdigest()
            stats["sample_sha256"] = digest
            stats["sample_length"] = len(str(value))

    return stats


def validate_constraints(db: sqlite3.Connection, root: ET.Element) -> int:
    errors = 0
    validation = add(root, "validation")

    integrity = db.execute("PRAGMA integrity_check").fetchall()
    integrity_ok = len(integrity) == 1 and integrity[0][0] == "ok"
    add(validation, "integrity_check", status="PASS" if integrity_ok else "FAIL", result="; ".join(map(str, [r[0] for r in integrity])))
    if not integrity_ok:
        errors += 1

    fk = db.execute("PRAGMA foreign_key_check").fetchall()
    add(validation, "foreign_key_check", status="PASS" if not fk else "FAIL", violations=len(fk))
    if fk:
        errors += len(fk)
        violations = ET.SubElement(validation, "foreign_key_violations")
        for row in fk:
            add(violations, "violation", table=row[0], rowid=row[1], parent=row[2], fk_index=row[3])

    user_version = int(scalar(db, "PRAGMA user_version"))
    add(validation, "pragma", user_version=user_version, foreign_keys=int(scalar(db, "PRAGMA foreign_keys")))

    return errors


def build_report(db: sqlite3.Connection, db_path: Path) -> tuple[ET.ElementTree, int]:
    db.row_factory = sqlite3.Row
    tables = table_names(db)
    root = ET.Element(
        "serm_database_audit",
        {
            "version": "1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database": str(db_path.resolve()),
            "sqlite": sqlite3.sqlite_version,
        },
    )

    meta = ET.SubElement(root, "summary")
    add(meta, "database_size_bytes", db_path.stat().st_size)
    add(meta, "tables", len(tables))
    add(meta, "total_rows", int(sum(int(scalar(db, f"SELECT COUNT(*) FROM {qident(t)}")) for t in tables)))

    errors = validate_constraints(db, root)
    tables_node = ET.SubElement(root, "tables")

    for table in tables:
        columns = table_schema(db, table)
        row_count = int(scalar(db, f"SELECT COUNT(*) FROM {qident(table)}"))
        table_node = ET.SubElement(tables_node, "table", {"name": table, "rows": str(row_count), "columns": str(len(columns))})

        cols_node = ET.SubElement(table_node, "columns")
        for col in columns:
            cid, name, declared_type, notnull, default_value, pk = col
            col_node = ET.SubElement(
                cols_node,
                "column",
                {
                    "cid": str(cid),
                    "name": str(name),
                    "type": str(declared_type or ""),
                    "notnull": str(notnull),
                    "primary_key_position": str(pk),
                    "default": "" if default_value is None else str(default_value),
                },
            )
            stats = column_stats(db, table, name)
            stats_node = ET.SubElement(col_node, "stats")
            for key in ("rows", "null", "non_null", "distinct", "empty", "min_length", "max_length", "sample_length"):
                if key in stats:
                    add(stats_node, key, stats[key])
            if "types" in stats:
                type_node = ET.SubElement(stats_node, "storage_types")
                for storage_type, count in stats["types"].items():
                    add(type_node, "type", count, name=storage_type)
            if "sample_sha256" in stats:
                add(stats_node, "first_non_null_sha256", stats["sample_sha256"])

            if notnull and stats["null"]:
                add(col_node, "validation", status="FAIL", rule="NOT NULL", violations=stats["null"])
                errors += int(stats["null"])

        indexes_node = ET.SubElement(table_node, "indexes")
        for idx in indexes(db, table):
            # index_list columns: seq, name, unique, origin, partial
            idx_seq, idx_name, unique, origin, partial = idx[:5]
            idx_node = ET.SubElement(
                indexes_node,
                "index",
                {
                    "seq": str(idx_seq),
                    "name": str(idx_name),
                    "unique": str(unique),
                    "origin": str(origin),
                    "partial": str(partial),
                },
            )
            for pos in index_columns(db, idx_name):
                # index_info: seqno, cid, name
                add(idx_node, "column", pos[2], seqno=pos[0], cid=pos[1])

        fk_node = ET.SubElement(table_node, "foreign_keys")
        for fk in foreign_keys(db, table):
            # id, seq, table, from, to, on_update, on_delete, match
            add(
                fk_node,
                "foreign_key",
                from_column=fk[3],
                parent_table=fk[2],
                parent_column=fk[4],
                on_update=fk[5],
                on_delete=fk[6],
                match=fk[7],
            )

        # Exact row fingerprint for deterministic validation of a database state.
        # It hashes every scalar field in primary-key order when a PK exists;
        # otherwise SQLite rowid order is used. No row contents are written to XML.
        names = [str(c[1]) for c in columns]
        order = next((qident(str(c[1])) for c in columns if int(c[5]) == 1), "rowid")
        digest = hashlib.sha256()
        cursor = db.execute(
            f"SELECT {', '.join(qident(n) for n in names)} FROM {qident(table)} ORDER BY {order}"
        )
        row_hash_rows = 0
        for row in cursor:
            parts = []
            for value in row:
                if value is None:
                    parts.append("N:")
                elif isinstance(value, bytes):
                    parts.append("B:" + value.hex())
                else:
                    parts.append(normalized_type(value) + ":" + str(value))
            digest.update(("|".join(parts) + "\n").encode("utf-8", "replace"))
            row_hash_rows += 1
        add(table_node, "row_fingerprint", digest.hexdigest(), rows=row_hash_rows, order=order)

    add(root, "result", status="PASS" if errors == 0 else "FAIL", errors=errors)
    return ET.ElementTree(root), errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditoria exaustiva e compacta do banco SQLite do SERM em XML.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="caminho do serm.db")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="XML de saída")
    args = parser.parse_args()

    db_path = args.db.resolve()
    output = args.output.resolve()
    if not db_path.is_file():
        print(f"ERRO: banco não encontrado: {db_path}", file=sys.stderr)
        return 2

    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as db:
            tree, errors = build_report(db, db_path)
    except sqlite3.Error as exc:
        print(f"ERRO SQLite: {exc}", file=sys.stderr)
        return 3

    ET.indent(tree, space="  ")
    tree.write(output, encoding="utf-8", xml_declaration=True, short_empty_elements=True)

    root = tree.getroot()
    summary = root.find("summary")
    result = root.find("result")
    print(f"XML: {output}")
    print(f"TABELAS: {summary.findtext('tables') if summary is not None else '?'}")
    print(f"TOTAL ROWS: {summary.findtext('total_rows') if summary is not None else '?'}")
    print(f"RESULTADO: {result.get('status') if result is not None else 'UNKNOWN'}")
    print(f"ERROS: {result.get('errors') if result is not None else '?'}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
