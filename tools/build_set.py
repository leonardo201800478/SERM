#!/usr/bin/env python
"""
Script para construir um set personalizado via linha de comando.
Uso: python tools/build_set.py <db_path> <source_path> <dest_path> [maquina1 ...]
"""

import sys
import sqlite3
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mame_set_builder.sets.builder import SetBuilder

logging.basicConfig(level=logging.INFO)

def main():
    if len(sys.argv) < 4:
        print("Uso: python tools/build_set.py <db_path> <source_path> <dest_path> [maquina1 ...]")
        sys.exit(1)

    db_path = Path(sys.argv[1])
    source_path = Path(sys.argv[2])
    dest_path = Path(sys.argv[3])
    machines = sys.argv[4:] if len(sys.argv) > 4 else []

    if not db_path.exists():
        print(f"Erro: banco {db_path} não encontrado.")
        sys.exit(1)
    if not source_path.exists():
        print(f"Erro: FULLSET {source_path} não encontrado.")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    builder = SetBuilder(conn)
    manifest = builder.build(
        machines,
        source_path,
        dest_path,
        profile_name="CLI Build"
    )

    print(f"\n=== Construção concluída ===")
    print(f"Máquinas: {len(manifest.selected_machines)}")
    print(f"Arquivos requeridos: {len(manifest.required_files)}")
    print(f"Arquivos faltantes: {len(manifest.missing_files)}")
    if manifest.missing_files:
        print("\nArquivos faltantes:")
        for f in manifest.missing_files[:20]:
            print(f"  {f}")

    conn.close()

if __name__ == "__main__":
    main()