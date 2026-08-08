#!/usr/bin/env python
"""
Script para testar o motor de filtros com diferentes perfis.
Uso: python tools/test_filter.py <caminho_do_banco.db>
"""

import sys
import logging
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mame_set_builder.filtering.engine import FilterEngine
from mame_set_builder.filtering.profiles import arcade_only, all_systems, consoles_only, computers_only, mechanical_only

logging.basicConfig(level=logging.INFO)

def main():
    if len(sys.argv) < 2:
        print("Uso: python tools/test_filter.py <caminho_do_banco.db>")
        sys.exit(1)

    db_path = Path(sys.argv[1])
    if not db_path.exists():
        print(f"Erro: arquivo {db_path} não encontrado.")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    engine = FilterEngine(conn)

    profiles = {
        "Arcade Only": arcade_only(),
        "All Systems": all_systems(),
        "Consoles & Portables": consoles_only(),
        "Computers Only": computers_only(),
        "Mechanical": mechanical_only(),
    }

    print("\n=== Teste de Filtros ===\n")
    for name, profile in profiles.items():
        count = engine.count(profile)
        print(f"{name:30} : {count:5} máquinas")

    conn.close()

if __name__ == "__main__":
    main()