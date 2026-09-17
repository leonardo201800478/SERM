"""Teste de integridade da Etapa 2: CATLIST -> catálogo MAME.

Uso, a partir de v2:
    python tests/mame/test_catlist_integrity.py

O teste faz somente consultas agregadas e uma amostra pequena, sem despejar
37 mil registros no terminal.
"""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "database" / "serm.db"


def table_exists(db: sqlite3.Connection, table: str) -> bool:
    """Retorna se a tabela informada existe."""
    return (
        db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        is not None
    )


def count(db: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    """Executa uma contagem escalar sem carregar registros para memória."""
    return int(db.execute(sql, params).fetchone()[0])


def main() -> int:
    """Valida estrutura, cardinalidade, FK e duplicidade da importação CATLIST."""
    started = time.perf_counter()
    print("=" * 72)
    print("SERM | MAME CATLIST INTEGRITY TEST")
    print("=" * 72)
    print(f"BANCO: {DB_PATH}")

    if not DB_PATH.is_file():
        print("FAIL | banco não encontrado")
        return 2

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys=ON")
    try:
        required = ("mame_machine", "mame_source_document", "mame_classification")
        print("\n[1/6] ESTRUTURA")
        for table in required:
            ok = table_exists(db, table)
            print(f"{table:<24} {'PASS' if ok else 'FAIL'}")
            if not ok:
                return 1

        print("\n[2/6] FONTE")
        source = db.execute(
            """SELECT id, source_name, source_path, source_hash, byte_length, status
               FROM mame_source_document
               WHERE source_type='catlist'
               ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        if source is None:
            print("CATLIST source          FAIL | nenhuma fonte encontrada")
            return 1
        source_id, name, path, source_hash, byte_length, status = source
        source_ok = bool(source_hash) and byte_length > 0 and status == "completed"
        print(f"source_id               {source_id}")
        print(f"arquivo                 {name}")
        print(f"status                  {status}")
        print(f"hash                    {'PASS' if bool(source_hash) else 'FAIL'}")
        print(f"tamanho                 {byte_length:,} bytes")

        print("\n[3/6] CARDINALIDADE")
        machines = count(db, "SELECT COUNT(*) FROM mame_machine")
        classifications = count(
            db,
            "SELECT COUNT(*) FROM mame_classification WHERE source_document_id=?",
            (source_id,),
        )
        resolved = count(
            db,
            "SELECT COUNT(*) FROM mame_classification WHERE source_document_id=? AND resolved_status='resolved'",
            (source_id,),
        )
        unresolved = count(
            db,
            "SELECT COUNT(*) FROM mame_classification WHERE source_document_id=? AND resolved_status='unresolved'",
            (source_id,),
        )
        print(f"mame_machine            {machines:,}")
        print(f"classificações CATLIST  {classifications:,}")
        print(f"resolvidas              {resolved:,}")
        print(f"não resolvidas          {unresolved:,}")

        print("\n[4/6] INTEGRIDADE REFERENCIAL")
        orphan_fk = count(
            db,
            """SELECT COUNT(*) FROM mame_classification c
               LEFT JOIN mame_machine m ON m.id=c.machine_id
               WHERE c.source_document_id=? AND c.resolved_status='resolved' AND m.id IS NULL""",
            (source_id,),
        )
        name_mismatch = count(
            db,
            """SELECT COUNT(*) FROM mame_classification c
               JOIN mame_machine m ON m.id=c.machine_id
               WHERE c.source_document_id=? AND c.resolved_status='resolved'
                 AND c.machine_name <> m.name""",
            (source_id,),
        )
        print(f"FK órfã                 {'PASS' if orphan_fk == 0 else 'FAIL'} | {orphan_fk}")
        print(
            f"nome x machine.id       {'PASS' if name_mismatch == 0 else 'FAIL'} | {name_mismatch}"
        )

        print("\n[5/6] DUPLICIDADE / METADADOS")
        duplicates = count(
            db,
            """SELECT COUNT(*) FROM (
                 SELECT machine_name, section_raw, COUNT(*) n
                 FROM mame_classification
                 WHERE source_document_id=?
                 GROUP BY machine_name, section_raw
                 HAVING n > 1
               )""",
            (source_id,),
        )
        folder_settings = count(
            db,
            """SELECT COUNT(*) FROM mame_classification
               WHERE source_document_id=? AND UPPER(section_raw)='FOLDER_SETTINGS'""",
            (source_id,),
        )
        null_machine_resolved = count(
            db,
            """SELECT COUNT(*) FROM mame_classification
               WHERE source_document_id=? AND resolved_status='resolved' AND machine_id IS NULL""",
            (source_id,),
        )
        print(f"duplicidades             {'PASS' if duplicates == 0 else 'FAIL'} | {duplicates}")
        print(
            f"FOLDER_SETTINGS         {'PASS' if folder_settings == 0 else 'FAIL'} | {folder_settings}"
        )
        print(
            f"resolved sem machine_id {'PASS' if null_machine_resolved == 0 else 'FAIL'} | {null_machine_resolved}"
        )

        print("\n[6/6] COBERTURA DO CATÁLOGO")
        classified_distinct = count(
            db,
            "SELECT COUNT(DISTINCT machine_id) FROM mame_classification WHERE source_document_id=? AND resolved_status='resolved'",
            (source_id,),
        )
        print(f"máquinas classificadas  {classified_distinct:,}")
        print(f"máquinas sem CATLIST    {machines - classified_distinct:,}")
        print(
            "Nota: ausência de CATLIST não é erro; unresolved significa somente entrada declarada pelo CATLIST sem correspondência."
        )

        passed = (
            source_ok
            and classifications == resolved + unresolved
            and orphan_fk == 0
            and name_mismatch == 0
            and duplicates == 0
            and folder_settings == 0
            and null_machine_resolved == 0
            and unresolved == 0
        )
        elapsed = time.perf_counter() - started
        print("\n" + "=" * 72)
        print(f"RESULTADO: {'PASS' if passed else 'FAIL'} | tempo={elapsed:.2f}s")
        print("=" * 72)
        return 0 if passed else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
