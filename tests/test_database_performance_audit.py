"""Auditoria somente leitura de performance do SQLite do SERM V2.

O objetivo e medir o estado atual antes de qualquer otimizacao. Este teste nao
cria indices, nao executa ANALYZE e nao altera PRAGMAs persistentes.

A auditoria registra:
- versao do SQLite e PRAGMAs relevantes;
- tamanho e contagem de paginas;
- estatisticas disponiveis em sqlite_stat1;
- todos os indices por tabela;
- planos EXPLAIN QUERY PLAN para consultas criticas MAME;
- sinais de full scan e de uso de indices.

Uso:
    python -m pytest tests/test_database_performance_audit.py -s -q

O teste e diagnostico: ausencia de indice em uma consulta nao e, por si so,
um erro. O resultado deve ser analisado antes de criar qualquer migration.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().parents[1] / "data" / "database" / "serm.db"


def _scalar(db: sqlite3.Connection, sql: str, params: tuple = ()) -> object:
    row = db.execute(sql, params).fetchone()
    return None if row is None else row[0]


def _explain(db: sqlite3.Connection, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    return db.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()


def _print_plan(label: str, plan: list[sqlite3.Row]) -> None:
    print(f"\n[{label}]")
    for row in plan:
        detail = row[3] if len(row) > 3 else row[-1]
        print(f"  {detail}")


def test_database_performance_audit() -> None:
    if not DB_FILE.is_file():
        raise AssertionError(f"Banco nao encontrado: {DB_FILE}")

    with sqlite3.connect(f"file:{DB_FILE.as_posix()}?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row

        print("DATABASE PERFORMANCE AUDIT")
        print(f"DB: {DB_FILE}")
        print(f"SQLite: {sqlite3.sqlite_version}")
        print(f"SIZE: {DB_FILE.stat().st_size:,} bytes")
        print(f"PAGE_COUNT: {_scalar(db, 'PRAGMA page_count')}")
        print(f"PAGE_SIZE: {_scalar(db, 'PRAGMA page_size')}")

        print("\nPRAGMAS:")
        for pragma in (
            "journal_mode",
            "synchronous",
            "foreign_keys",
            "cache_size",
            "temp_store",
            "mmap_size",
            "auto_vacuum",
        ):
            try:
                value = _scalar(db, f"PRAGMA {pragma}")
            except sqlite3.DatabaseError as exc:
                value = f"ERROR: {exc}"
            print(f"  {pragma:<14}: {value}")

        tables = [
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        print(f"\nTABLES: {len(tables)}")

        print("\nINDEXES:")
        index_count = 0
        for table in tables:
            indexes = db.execute(f'PRAGMA index_list("{table.replace(chr(34), chr(34) * 2)}")').fetchall()
            if not indexes:
                continue
            print(f"  {table}:")
            for idx in indexes:
                index_count += 1
                name = idx[1]
                columns = [
                    row[2]
                    for row in db.execute(
                        f'PRAGMA index_info("{name.replace(chr(34), chr(34) * 2)}")'
                    ).fetchall()
                ]
                print(
                    f"    {name}: columns={columns} unique={idx[2]} origin={idx[3]} partial={idx[4]}"
                )
        print(f"  TOTAL INDEXES: {index_count}")

        stat_exists = _scalar(
            db,
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='sqlite_stat1'",
        )
        print(f"\nSQLITE_STAT1: {'PRESENT' if stat_exists else 'ABSENT'}")
        if stat_exists:
            rows = db.execute("SELECT tbl,idx,stat FROM sqlite_stat1 ORDER BY tbl,idx").fetchall()
            print(f"  ROWS: {len(rows)}")
            for row in rows[:100]:
                print(f"  {row[0]}.{row[1]} = {row[2]}")
            if len(rows) > 100:
                print(f"  ... {len(rows) - 100} additional rows omitted")

        queries = {
            "MAME machine by import": (
                "SELECT id,name FROM mame_machine WHERE import_id = ?",
                (int(_scalar(db, "SELECT COALESCE(MAX(id), 0) FROM mame_listxml_import")),),
            ),
            "MAME ROM by machine": (
                "SELECT machine_id,name,sha1,crc,size FROM mame_rom WHERE machine_id = ?",
                (int(_scalar(db, "SELECT COALESCE(MIN(id), 0) FROM mame_machine")),),
            ),
            "MAME ROM identity SHA1": (
                "SELECT machine_id,name FROM mame_rom WHERE sha1 = ?",
                ("0000000000000000000000000000000000000000",),
            ),
            "MAME merge lookup": (
                "SELECT machine_id,name,sha1,crc,size FROM mame_rom WHERE lower(name) = lower(?)",
                ("__serm_performance_probe__",),
            ),
            "MAME machine lineage": (
                "SELECT id,name,cloneof,romof FROM mame_machine "
                "WHERE cloneof = ? OR romof = ?",
                ("__serm_performance_probe__", "__serm_performance_probe__"),
            ),
        }

        print("\nQUERY PLANS:")
        scan_count = 0
        search_count = 0
        for label, (sql, params) in queries.items():
            plan = _explain(db, sql, params)
            _print_plan(label, plan)
            for row in plan:
                detail = str(row[3] if len(row) > 3 else row[-1]).upper()
                if "SCAN" in detail:
                    scan_count += 1
                if "SEARCH" in detail and "USING" in detail:
                    search_count += 1

        print("\nPLAN SUMMARY:")
        print(f"  SEARCH USING INDEX: {search_count}")
        print(f"  SCAN OPERATIONS   : {scan_count}")
        print("\nRESULTADO: PASS — auditoria somente leitura; nenhuma alteracao foi feita.")
