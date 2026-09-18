"""Teste de integridade da ingestão Vsync.ini do catálogo MAME."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / "data" / "database" / "serm.db"


def main() -> int:
    print("=" * 72)
    print("SERM | MAME VSYNC.INI INTEGRITY TEST")
    print("=" * 72)
    print(f"BANCO: {DB}\n")
    if not DB.is_file():
        print("RESULTADO: FAIL | banco inexistente")
        return 1
    con = sqlite3.connect(DB)
    try:
        print("[1/5] ESTRUTURA")
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ("mame_machine", "mame_source_document", "mame_vsync"):
            ok = table in tables
            print(f"{table:<24} {'PASS' if ok else 'FAIL'}")
            if not ok:
                return 1

        print("\n[2/5] FONTE")
        source = con.execute(
            "SELECT id, source_name, status, source_hash, byte_length FROM mame_source_document WHERE source_type='vsync_ini' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not source:
            print("Vsync.ini              FAIL | nenhuma fonte encontrada")
            return 1
        print(f"source_id              {source[0]}")
        print(f"arquivo                {source[1]}")
        print(f"status                 {source[2]}")
        print(f"hash                   {'PASS' if source[3] else 'FAIL'}")
        print(f"tamanho                {source[4]:,} bytes")

        print("\n[3/5] CARDINALIDADE")
        total_machines = con.execute("SELECT COUNT(*) FROM mame_machine").fetchone()[0]
        entries, resolved, unresolved, distinct_machines = con.execute(
            "SELECT COUNT(*), SUM(resolved_status='resolved'), SUM(resolved_status='unresolved'), COUNT(DISTINCT machine_name) FROM mame_vsync WHERE source_document_id=?",
            (source[0],),
        ).fetchone()
        print(f"mame_machine           {total_machines:,}")
        print(f"entradas               {entries or 0:,}")
        print(f"resolvidas             {resolved or 0:,}")
        print(f"não resolvidas         {unresolved or 0:,}")
        print(f"máquinas distintas     {distinct_machines or 0:,}")

        print("\n[4/5] INTEGRIDADE")
        orphan = con.execute(
            "SELECT COUNT(*) FROM mame_vsync v LEFT JOIN mame_machine m ON m.id=v.machine_id WHERE v.machine_id IS NOT NULL AND m.id IS NULL AND v.source_document_id=?",
            (source[0],),
        ).fetchone()[0]
        mismatch = con.execute(
            "SELECT COUNT(*) FROM mame_vsync v JOIN mame_machine m ON m.id=v.machine_id WHERE v.machine_name<>m.name AND v.source_document_id=?",
            (source[0],),
        ).fetchone()[0]
        duplicate = con.execute(
            "SELECT COUNT(*) FROM (SELECT machine_name FROM mame_vsync WHERE source_document_id=? GROUP BY machine_name HAVING COUNT(*)>1)",
            (source[0],),
        ).fetchone()[0]
        invalid_value = con.execute(
            "SELECT COUNT(*) FROM mame_vsync WHERE source_document_id=? AND vsync_enabled NOT IN (0,1)",
            (source[0],),
        ).fetchone()[0]
        print(f"FK órfã                {'PASS' if orphan == 0 else 'FAIL'} | {orphan}")
        print(f"nome x machine.id      {'PASS' if mismatch == 0 else 'FAIL'} | {mismatch}")
        print(f"máquina duplicada      {'PASS' if duplicate == 0 else 'FAIL'} | {duplicate}")
        print(
            f"valor inválido         {'PASS' if invalid_value == 0 else 'FAIL'} | {invalid_value}"
        )

        print("\n[5/5] COBERTURA")
        coverage = (resolved or 0) * 100 / total_machines if total_machines else 0
        print(f"cobertura do catálogo  {coverage:.2f}%")
        print(f"máquinas sem Vsync     {total_machines - (distinct_machines or 0):,}")
        ok = source[2] == "completed" and orphan == mismatch == duplicate == invalid_value == 0
        print("\n" + "=" * 72)
        print(f"RESULTADO: {'PASS' if ok else 'FAIL'}")
        print("=" * 72)
        return 0 if ok else 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
