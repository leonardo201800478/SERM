#!/usr/bin/env python
"""
Teste do construtor de set.
Uso: python tools/build_set.py <caminho_do_banco.db> <máquina1> ... <destino>
"""

import sys
import sqlite3
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mame_set_builder.dependencies.resolver import DependencyResolver
from mame_set_builder.archives.scanner import FullsetScanner
from mame_set_builder.sets.builder import SetBuilder
from mame_set_builder.domain.manifest import SetManifest

logging.basicConfig(level=logging.INFO)

def main():
    if len(sys.argv) < 4:
        print("Uso: python tools/build_set.py <caminho_do_banco.db> <máquina1> [máquina2 ...] <destino>")
        print("Exemplo: python tools/build_set.py data/database/mame_dataset.db pacman sf2 D:/MeuSet")
        sys.exit(1)

    # Último argumento é o diretório de destino
    db_path = Path(sys.argv[1])
    dest_path = Path(sys.argv[-1])
    machine_names = sys.argv[2:-1]

    if not db_path.exists():
        print(f"Erro: arquivo {db_path} não encontrado.")
        sys.exit(1)

    if not dest_path.exists():
        dest_path.mkdir(parents=True, exist_ok=True)

    # Conecta ao banco
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # 1. Resolve dependências
    resolver = DependencyResolver(conn)
    manifest = resolver.resolve(machine_names, profile_name="Teste")
    manifest.source_path = "I:\\ROMS\\MAME"  # FULLSET
    manifest.destination_path = str(dest_path)

    print(f"Manifesto: {len(manifest.selected_machines)} máquinas, {len(manifest.required_files)} arquivos.")

    # 2. Escaneia FULLSET (já deve estar indexado, mas podemos re-escanear se necessário)
    scanner = FullsetScanner(conn)
    # scanner.scan_directory(Path("I:\\ROMS\\MAME"))  # opcional

    # 3. Constrói o set
    builder = SetBuilder(scanner)
    report = builder.build(manifest)

    print(f"\n--- Relatório ---")
    print(f"Total: {report['total']}")
    print(f"Copiados: {report['copied']}")
    print(f"Faltando: {report['missing']}")
    print(f"Falhas: {report['failed']}")

    if report['missing'] > 0:
        print("\nArquivos faltando:")
        for item in report['details']:
            if item['status'] == 'missing':
                print(f"  {item['file']}")

    conn.close()

if __name__ == "__main__":
    main()