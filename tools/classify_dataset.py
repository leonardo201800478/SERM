#!/usr/bin/env python
"""
Script para classificar todas as máquinas do dataset já populado.
Uso: python tools/classify_dataset.py <caminho_do_banco.db>
"""

import sys
import logging
import sqlite3
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mame_set_builder.classification.machine_classifier import MachineClassifier

logging.basicConfig(level=logging.INFO)

def main():
    if len(sys.argv) < 2:
        print("Uso: python tools/classify_dataset.py <caminho_do_banco.db>")
        sys.exit(1)

    db_path = Path(sys.argv[1])
    if not db_path.exists():
        print(f"Erro: arquivo {db_path} não encontrado.")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    classifier = MachineClassifier(conn)
    count = classifier.classify_all()
    print(f"Classificação finalizada. {count} máquinas classificadas.")

    conn.close()

if __name__ == "__main__":
    main()