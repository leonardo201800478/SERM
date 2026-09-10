"""Auditoria semântica dos dados relacionais usados pelos filtros MAME.

O objetivo desta ferramenta é detectar máquinas para as quais uma agregação
achatada (MAX/GROUP_CONCAT após múltiplos JOINs 1:N) pode produzir uma
interpretação incorreta. Ela não altera o banco nem os filtros.

Execute a partir de ``v2`` com:
    python tests/test_mame_filter_semantic_audit.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "database" / "serm.db"


def _count_rows(db: sqlite3.Connection, query: str) -> int:
    row = db.execute(query).fetchone()
    return int(row[0] or 0) if row else 0


def main() -> int:
    print("=" * 80)
    print("AUDITORIA SEMÂNTICA DOS FILTROS MAME")
    print("=" * 80)
    print(f"DB: {DB}")

    if not DB.is_file():
        print("ERRO: banco SERM não encontrado.")
        return 2

    with sqlite3.connect(DB, timeout=60.0) as db:
        db.execute("PRAGMA foreign_keys=ON")

        latest = db.execute(
            """SELECT id, mame_build, source_hash
               FROM mame_listxml_import
               WHERE status='completed'
               ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        if latest is None:
            print("ERRO: nenhuma importação ListXML MAME concluída.")
            return 2

        import_id, build, source_hash = latest
        print(f"IMPORT: id={import_id} build={build} hash={source_hash}")

        machines = _count_rows(
            db, "SELECT COUNT(*) FROM mame_machine WHERE import_id=?"
        ) if False else int(
            db.execute(
                "SELECT COUNT(*) FROM mame_machine WHERE import_id=?", (import_id,)
            ).fetchone()[0]
        )
        print(f"MACHINES: {machines:,}")

        # Cada bloco abaixo representa uma relação 1:N que não deve ser
        # reduzida por MAX() sem uma regra semântica explícita.
        checks = [
            (
                "driver",
                """SELECT COUNT(*) FROM (
                       SELECT machine_id FROM mame_driver
                       GROUP BY machine_id HAVING COUNT(*) > 1
                   )""",
            ),
            (
                "display",
                """SELECT COUNT(*) FROM (
                       SELECT machine_id FROM mame_display
                       GROUP BY machine_id HAVING COUNT(*) > 1
                   )""",
            ),
            (
                "input",
                """SELECT COUNT(*) FROM (
                       SELECT machine_id FROM mame_input
                       GROUP BY machine_id HAVING COUNT(*) > 1
                   )""",
            ),
            (
                "control",
                """SELECT COUNT(*) FROM (
                       SELECT i.machine_id
                       FROM mame_control c
                       JOIN mame_input i ON i.id=c.input_id
                       GROUP BY i.machine_id HAVING COUNT(*) > 1
                   )""",
            ),
            (
                "chip",
                """SELECT COUNT(*) FROM (
                       SELECT machine_id FROM mame_chip
                       GROUP BY machine_id HAVING COUNT(*) > 1
                   )""",
            ),
            (
                "rom",
                """SELECT COUNT(*) FROM (
                       SELECT machine_id FROM mame_rom
                       GROUP BY machine_id HAVING COUNT(*) > 1
                   )""",
            ),
            (
                "disk",
                """SELECT COUNT(*) FROM (
                       SELECT machine_id FROM mame_disk
                       GROUP BY machine_id HAVING COUNT(*) > 1
                   )""",
            ),
            (
                "sample",
                """SELECT COUNT(*) FROM (
                       SELECT machine_id FROM mame_sample
                       GROUP BY machine_id HAVING COUNT(*) > 1
                   )""",
            ),
            (
                "biosset",
                """SELECT COUNT(*) FROM (
                       SELECT machine_id FROM mame_biosset
                       GROUP BY machine_id HAVING COUNT(*) > 1
                   )""",
            ),
            (
                "device",
                """SELECT COUNT(*) FROM (
                       SELECT machine_id FROM mame_device
                       GROUP BY machine_id HAVING COUNT(*) > 1
                   )""",
            ),
        ]

        print("\nMÁQUINAS COM CARDINALIDADE 1:N:")
        ambiguous_total = 0
        for name, query in checks:
            count = _count_rows(db, query)
            ambiguous_total += count
            print(f"  {name:10s}: {count:8,}")

        # Este é o problema mais crítico para a classificação: CATLIST deve
        # ser isolado pela origem, nunca por toda a tabela genérica.
        classification_all = _count_rows(
            db,
            """SELECT COUNT(DISTINCT machine_id) FROM mame_classification
               WHERE resolved_status='resolved'""",
        )
        classification_catlist = _count_rows(
            db,
            """SELECT COUNT(DISTINCT c.machine_id)
               FROM mame_classification c
               JOIN mame_source_document s ON s.id=c.source_document_id
               WHERE c.resolved_status='resolved'
                 AND s.source_type='catlist'""",
        )
        print("\nCLASSIFICAÇÃO:")
        print(f"  qualquer fonte: {classification_all:,}")
        print(f"  somente CATLIST: {classification_catlist:,}")

        # Detecta também machines que possuem múltiplas classificações CATLIST.
        multi_catlist = _count_rows(
            db,
            """SELECT COUNT(*) FROM (
                   SELECT c.machine_id
                   FROM mame_classification c
                   JOIN mame_source_document s ON s.id=c.source_document_id
                   WHERE c.resolved_status='resolved'
                     AND s.source_type='catlist'
                   GROUP BY c.machine_id
                   HAVING COUNT(*) > 1
               )""",
        )
        print(f"  CATLIST com múltiplas entradas: {multi_catlist:,}")

        # Evidência de conflito Working/Not Working. Não resolvemos aqui:
        # o filtro deve preservar o conflito como estado explícito.
        conflict = _count_rows(
            db,
            """SELECT COUNT(*) FROM (
                   SELECT w.machine_name
                   FROM mame_folder_filter_entry w
                   JOIN mame_folder_filter_source ws ON ws.id=w.source_id
                   JOIN mame_folder_filter_entry n ON n.machine_name=w.machine_name
                   JOIN mame_folder_filter_source ns ON ns.id=n.source_id
                   WHERE lower(ws.file_name) IN ('working arcade.ini','working arcade clean.ini')
                     AND lower(ns.file_name) IN ('not working arcade.ini','not_working_arcade.ini')
                   GROUP BY w.machine_name
               )""",
        )
        print(f"  Working E Not Working: {conflict:,}")

        print("\nRESULTADO:")
        print(f"  relações 1:N potencialmente ambíguas: {ambiguous_total:,}")
        print("  A auditoria NÃO modifica dados.")
        print("  Os números acima determinam a próxima correção do loader relacional.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
