"""Teste de integridade da Etapa 3: resolution.ini -> catálogo MAME."""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "database" / "serm.db"


def main() -> int:
    """Valida cardinalidade, dimensões e relacionamentos sem carregar o catálogo inteiro."""
    started = time.perf_counter()
    print("=" * 72)
    print("SERM | MAME RESOLUTION.INI INTEGRITY TEST")
    print("=" * 72)
    print(f"BANCO: {DB_PATH}")
    if not DB_PATH.is_file():
        print("FAIL | banco não encontrado")
        return 2

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys=ON")
    try:
        print("\n[1/5] ESTRUTURA")
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='mame_resolution'").fetchone()
        print(f"mame_resolution         {'PASS' if exists else 'FAIL'}")
        if not exists:
            return 1

        print("\n[2/5] FONTE")
        source = db.execute("""SELECT id, source_name, source_hash, byte_length, status
                              FROM mame_source_document
                              WHERE source_type='resolution_ini'
                              ORDER BY id DESC LIMIT 1""").fetchone()
        if not source:
            print("resolution.ini         FAIL | nenhuma fonte encontrada")
            return 1
        source_id, name, source_hash, byte_length, status = source
        print(f"source_id              {source_id}")
        print(f"arquivo                {name}")
        print(f"status                 {status}")
        print(f"hash                   {'PASS' if source_hash else 'FAIL'}")
        print(f"tamanho                {byte_length:,} bytes")

        print("\n[3/5] CARDINALIDADE")
        total = db.execute("SELECT COUNT(*) FROM mame_resolution WHERE source_document_id=?", (source_id,)).fetchone()[0]
        resolved = db.execute("SELECT COUNT(*) FROM mame_resolution WHERE source_document_id=? AND resolved_status='resolved'", (source_id,)).fetchone()[0]
        unresolved = db.execute("SELECT COUNT(*) FROM mame_resolution WHERE source_document_id=? AND resolved_status='unresolved'", (source_id,)).fetchone()[0]
        machines = db.execute("SELECT COUNT(*) FROM mame_machine").fetchone()[0]
        distinct = db.execute("SELECT COUNT(DISTINCT machine_id) FROM mame_resolution WHERE source_document_id=? AND resolved_status='resolved'", (source_id,)).fetchone()[0]
        print(f"mame_machine           {machines:,}")
        print(f"entradas               {total:,}")
        print(f"resolvidas             {resolved:,}")
        print(f"não resolvidas         {unresolved:,}")
        print(f"máquinas distintas     {distinct:,}")

        print("\n[4/5] INTEGRIDADE")
        orphan = db.execute("""SELECT COUNT(*) FROM mame_resolution r
                              LEFT JOIN mame_machine m ON m.id=r.machine_id
                              WHERE r.source_document_id=? AND r.resolved_status='resolved' AND m.id IS NULL""", (source_id,)).fetchone()[0]
        mismatch = db.execute("""SELECT COUNT(*) FROM mame_resolution r JOIN mame_machine m ON m.id=r.machine_id
                                WHERE r.source_document_id=? AND r.resolved_status='resolved' AND r.machine_name<>m.name""", (source_id,)).fetchone()[0]
        invalid = db.execute("SELECT COUNT(*) FROM mame_resolution WHERE source_document_id=? AND (width<=0 OR height<=0)", (source_id,)).fetchone()[0]
        duplicate = db.execute("""SELECT COUNT(*) FROM (SELECT machine_name, COUNT(*) n FROM mame_resolution
                                  WHERE source_document_id=? GROUP BY machine_name HAVING n>1)""", (source_id,)).fetchone()[0]
        print(f"FK órfã                {'PASS' if orphan == 0 else 'FAIL'} | {orphan}")
        print(f"nome x machine.id      {'PASS' if mismatch == 0 else 'FAIL'} | {mismatch}")
        print(f"dimensões inválidas    {'PASS' if invalid == 0 else 'FAIL'} | {invalid}")
        print(f"máquina duplicada      {'PASS' if duplicate == 0 else 'FAIL'} | {duplicate}")

        print("\n[5/5] DISTRIBUIÇÃO")
        groups = db.execute("""SELECT width, height, COUNT(*) n FROM mame_resolution
                              WHERE source_document_id=? GROUP BY width, height ORDER BY n DESC LIMIT 10""", (source_id,)).fetchall()
        print("Top 10 resoluções:")
        for width, height, amount in groups:
            print(f"  {width:4}x{height:<4} | {amount:,}")

        passed = status == "completed" and bool(source_hash) and total == resolved + unresolved and orphan == 0 and mismatch == 0 and invalid == 0 and duplicate == 0
        elapsed = time.perf_counter() - started
        print("\n" + "=" * 72)
        print(f"RESULTADO: {'PASS' if passed else 'FAIL'} | tempo={elapsed:.2f}s")
        print("=" * 72)
        return 0 if passed else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
