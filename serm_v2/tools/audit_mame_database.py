"""Auditoria estrutural e amostral do catálogo MAME persistido no SQLite.

O relatório é deliberadamente orientado ao banco real: enumera todas as tabelas
``mame_*``, informa colunas, quantidade de registros e amostras de dados.
Nenhum dado é alterado. O objetivo é servir de documentação viva para futuras
funções do SERM V2.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from ..runtime.paths import database_path

SAMPLE_SIZE = 3


def _tables(db: sqlite3.Connection) -> list[str]:
    """Retorna todas as tabelas MAME do banco em ordem alfabética."""
    rows = db.execute(
        """SELECT name FROM sqlite_master
           WHERE type='table' AND name LIKE 'mame_%'
           ORDER BY name"""
    ).fetchall()
    return [str(row[0]) for row in rows]


def _columns(db: sqlite3.Connection, table: str) -> list[str]:
    """Retorna os nomes das colunas de uma tabela MAME."""
    return [str(row[1]) for row in db.execute(f'PRAGMA table_info("{table}")').fetchall()]


def _sample(db: sqlite3.Connection, table: str) -> list[tuple]:
    """Obtém uma pequena amostra determinística sem modificar o banco."""
    return db.execute(f'SELECT * FROM "{table}" LIMIT {SAMPLE_SIZE}').fetchall()


def _format_value(value: object) -> str:
    """Converte valores para Markdown sem expor quebras de linha no relatório."""
    if value is None:
        return "NULL"
    text = str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    return text[:500]


def build_report(db_path: Path) -> str:
    """Gera a documentação amostral completa do banco MAME informado."""
    if not db_path.is_file():
        raise FileNotFoundError(f"Banco não encontrado: {db_path}")

    lines = [
        "# Auditoria do banco MAME — SERM V2",
        "",
        f"**Banco:** `{db_path}`",
        "",
        "Este documento é gerado a partir do banco real. Ele descreve o que foi "
        "efetivamente persistido, sem inferir campos que não estejam presentes.",
        "",
    ]

    with sqlite3.connect(db_path) as db:
        db.execute("PRAGMA query_only=ON")
        tables = _tables(db)
        lines.extend([f"**Tabelas MAME encontradas:** {len(tables)}", ""])

        for table in tables:
            columns = _columns(db, table)
            count = int(db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            rows = _sample(db, table)
            lines.extend([f"## `{table}`", "", f"**Registros:** {count:,}", ""])
            lines.append("**Colunas:** " + ", ".join(f"`{column}`" for column in columns))
            lines.append("")
            if not rows:
                lines.extend(["_Tabela sem registros._", ""])
                continue
            lines.append("### Amostra")
            lines.append("")
            lines.append("| " + " | ".join(columns) + " |")
            lines.append("| " + " | ".join("---" for _ in columns) + " |")
            for row in rows:
                lines.append("| " + " | ".join(_format_value(value) for value in row) + " |")
            lines.append("")

    return "\n".join(lines)


def main() -> int:
    """Executa a auditoria e grava o relatório Markdown solicitado."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=database_path(), help="Caminho do SQLite")
    parser.add_argument(
        "--output", type=Path, default=Path("mame_database_audit.md"), help="Relatório Markdown"
    )
    args = parser.parse_args()

    report = build_report(args.database)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Relatório gerado: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
