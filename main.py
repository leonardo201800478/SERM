# main.py
from pathlib import Path
from config import LISTXML, DATABASE, FOLDERS, OUTPUT_DAT
from parsers.xml_parser import XMLParser
from parsers.ini_parser import INIParser
from core.database import Database
from core.migrations import run_migrations
from repositories.machine_repository import MachineRepository
from filters.filters import (
    working_filter, no_clones_filter, no_mechanical_filter,
    category_contains, CompositeFilter, working_arcade_filter,
    year_range, BooleanFilter, ContainsFilter
)
from exporters.dat_exporter import DATExporter


def main():
    print("=" * 60)
    print("MAME Set Builder")
    print("=" * 60)

    # 1. Conectar ao banco de dados e aplicar migrações (se necessário)
    db = Database(DATABASE)
    run_migrations(db)          # Adiciona colunas extras, se ainda não existirem
    repo = MachineRepository(db)

    # 2. Importar o XML se o banco estiver vazio
    if repo.count() == 0:
        print("Importando listxml.xml...")
        parser = XMLParser(LISTXML, DATABASE)
        total = parser.parse()
        print(f"Total importado: {total:,}")
    else:
        print(f"Banco já possui {repo.count():,} máquinas.")

    # 3. Ler os arquivos .ini da pasta folders
    print("Lendo arquivos .ini da pasta folders...")
    ini_parser = INIParser(FOLDERS, db)
    ini_parser.parse_all()

    # 4. Carregar todas as máquinas do banco (com todas as colunas)
    machines = repo.get_all()
    print(f"Total de máquinas carregadas: {len(machines):,}")

    # 5. Diagnóstico: quantas máquinas sobrevivem a cada filtro isolado?
    print("\n--- Diagnóstico de filtros individuais ---")
    total = len(machines)
    print(f"Total: {total}")

    # Filtros básicos (sempre disponíveis)
    wf = working_filter().apply(machines)
    ncf = no_clones_filter().apply(machines)
    nmf = no_mechanical_filter().apply(machines)
    print(f"Working (XML): {len(wf)}")
    print(f"No clones: {len(ncf)}")
    print(f"No mechanical: {len(nmf)}")

    # Filtros baseados em colunas extras (se houver dados)
    # Verifica se existe alguma máquina com category preenchida
    if any(m.category for m in machines):
        print(f"Category contains 'Arcade': {len(category_contains('Arcade').apply(machines))}")
        print(f"Category contains 'Shooter': {len(category_contains('Shooter').apply(machines))}")

    if any(m.working_arcade is not None for m in machines):
        print(f"Working_arcade (INI): {len(working_arcade_filter().apply(machines))}")

    if any(m.genre for m in machines):
        print(f"Genre contains 'Action': {len(ContainsFilter('genre', 'Action').apply(machines))}")
        print(f"Genre contains 'Fighter': {len(ContainsFilter('genre', 'Fighter').apply(machines))}")

    # 6. Definir o filtro composto (AND) – personalize conforme seus dados
    print("\n--- Aplicando filtro composto ---")
    filtros = CompositeFilter([
        working_filter(),                # apenas funcionando
        no_clones_filter(),              # apenas pais (não clones)
        no_mechanical_filter(),          # não mecânicas
        # category_contains("Arcade"),   # DESCOMENTE quando tiver categorias preenchidas
        # working_arcade_filter(),       # DESCOMENTE se quiser usar o working_arcade.ini
        # year_range("1980", "1990"),    # DESCOMENTE para filtrar por década
        # ContainsFilter("genre", "Action"),  # DESCOMENTE para filtrar por gênero
    ], mode="AND")

    filtered = filtros.apply(machines)
    print(f"Máquinas após filtros: {len(filtered):,}")

    if len(filtered) == 0:
        print("\n⚠️ Nenhuma máquina passou pelos filtros. Verifique os dados das colunas.")
        print("  - Certifique-se de que as colunas extras foram preenchidas pelos .ini")
        print("  - Ajuste os filtros no main.py (comente/descomente linhas no filtro composto)")

    # 7. Exportar para DAT
    print("\n--- Exportando DAT ---")
    OUTPUT_DAT.mkdir(parents=True, exist_ok=True)   # garante que a pasta exista
    dat_file = OUTPUT_DAT / "filtrado.dat"
    exporter = DATExporter(filtered, dat_file, dat_name="MAME Filtrado")
    exporter.export()

    print("=" * 60)
    print("Concluído!")


if __name__ == "__main__":
    main()