"""Teste de contrato e auditoria do banco MAME real.

Para executar contra o banco local:
    SERM_MAME_DB=".../serm.db" pytest -q tests/test_mame_database_inventory.py -s

O teste é opcional em ambientes sem o banco real e não modifica dados.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from serm_v2.tools.audit_mame_database import build_report


@pytest.fixture
def live_database() -> Path:
    """Obtém o banco real informado pelo ambiente ou pula o teste."""
    value = os.getenv("SERM_MAME_DB")
    if not value:
        pytest.skip("SERM_MAME_DB não definido; auditoria live não executada")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        pytest.fail(f"SERM_MAME_DB aponta para banco inexistente: {path}")
    return path


def test_every_mame_table_is_queryable_and_has_sample_data(live_database: Path, capsys) -> None:
    """Consulta todas as tabelas MAME e imprime contagem/amostra para documentação."""
    with sqlite3.connect(live_database) as db:
        tables = [
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'mame_%' ORDER BY name"
            )
        ]
        assert tables, "O banco não possui tabelas mame_*"
        for table in tables:
            count = db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            columns = db.execute(f'PRAGMA table_info("{table}")').fetchall()
            assert columns, f"Tabela sem metadados de colunas: {table}"
            rows = db.execute(f'SELECT * FROM "{table}" LIMIT 3').fetchall()
            print(f"{table}: rows={count:,} columns={len(columns)} sample={len(rows)}")
            if count:
                assert rows, f"Tabela {table} informa registros mas não retornou amostra"

    output = capsys.readouterr().out
    assert "mame_machine:" in output
    assert "mame_rom:" in output


def test_live_report_describes_the_persisted_catalog(live_database: Path) -> None:
    """Garante que a documentação gerada cobre todas as tabelas MAME reais."""
    report = build_report(live_database)
    with sqlite3.connect(live_database) as db:
        tables = [
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'mame_%' ORDER BY name"
            )
        ]
    for table in tables:
        assert f"## `{table}`" in report
        assert "**Colunas:**" in report
