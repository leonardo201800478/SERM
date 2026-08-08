#!/usr/bin/env python
"""
Teste do scanner do FULLSET.
Uso: python tools/test_scanner.py <caminho_do_banco.db> <caminho_do_fullset>
"""

import sys
import sqlite3
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mame_set_builder.archives.scanner import FullsetScanner

logging.basicConfig(level=logging.INFO)

def main():
    if len(sys.argv) < 3:
        print("Uso: python tools/test_scanner.py <caminho_do_banco.db> <caminho_do_fullset>")
        sys.exit(1)

    db_path = Path(sys.argv[1])
    fullset_path = Path(sys.argv[2])

    if not db_path.exists():
        print(f"Erro: arquivo {db_path} não encontrado.")
        sys.exit(1)
    if not fullset_path.is_dir():
        print(f"Erro: {fullset_path} não é um diretório.")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    scanner = FullsetScanner(conn)
    count = scanner.scan_directory(fullset_path)

    print(f"\nEscaneamento concluído: {count} arquivos indexados.")
    conn.close()

if __name__ == "__main__":
    main()