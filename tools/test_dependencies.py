#!/usr/bin/env python
"""
Teste do resolvedor de dependências.
Uso: python tools/test_dependencies.py <caminho_do_banco.db> <máquina1> <máquina2> ...
"""

import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mame_set_builder.dependencies.resolver import DependencyResolver
from mame_set_builder.domain.manifest import SetManifest

def main():
    if len(sys.argv) < 3:
        print("Uso: python tools/test_dependencies.py <caminho_do_banco.db> <máquina1> [máquina2 ...]")
        sys.exit(1)

    db_path = Path(sys.argv[1])
    if not db_path.exists():
        print(f"Erro: arquivo {db_path} não encontrado.")
        sys.exit(1)

    machine_names = sys.argv[2:]
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    resolver = DependencyResolver(conn)
    manifest = resolver.resolve(machine_names, profile_name="Teste")

    print(f"\n=== Manifesto para {len(manifest.selected_machines)} máquinas ===")
    print(f"Máquinas: {', '.join(manifest.selected_machines)}")
    print(f"Arquivos necessários: {len(manifest.required_files)}")

    # Agrupar por tipo
    from collections import Counter
    tipos = Counter(f.file_type.value for f in manifest.required_files)
    print("Distribuição:")
    for tipo, qtd in tipos.items():
        print(f"  {tipo}: {qtd}")

    # Exibir alguns arquivos
    print("\nPrimeiros 20 arquivos:")
    for f in manifest.required_files[:20]:
        print(f"  {f.file_type.value}: {f.file_name} (de {f.source_machine})")

    conn.close()

if __name__ == "__main__":
    main()