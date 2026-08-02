import subprocess
import time
from pathlib import Path
from config import (
    LISTXML, DATABASE, FOLDERS, OUTPUT_DAT, MAME_EXE,
    FILTER_WORKING, FILTER_ARCADE, FILTER_CLONES,
    FILTER_CONTROL, FILTER_PLAYERS, FILTER_CATEGORY,
    REMOVE_MECHANICAL, REMOVE_BIOS, REMOVE_DEVICES, REMOVE_JUNK, KEEP_SOFTWARE_BIOS
)
from parsers.xml_parser import XMLParser
from parsers.ini_parser import INIParser
from core.database import Database
from core.migrations import run_migrations
from repositories.machine_repository import MachineRepository
from filters.filters import (
    working_filter, no_clones_filter, no_mechanical_filter,
    category_contains, CompositeFilter, ContainsFilter,
    BooleanFilter
)
from exporters.dat_exporter import DATExporter


# ===================================================================
# 1. GERAÇÃO AUTOMÁTICA DO LISTXML
# ===================================================================
def ensure_listxml():
    """Gera o arquivo listxml.xml a partir do executável do MAME, se não existir."""
    if LISTXML.exists():
        print(f"Arquivo listxml já existe: {LISTXML}")
        return

    print("Gerando listxml.xml a partir do MAME...")
    if not MAME_EXE.exists():
        raise FileNotFoundError(f"Executável do MAME não encontrado: {MAME_EXE}")

    try:
        # Cria o diretório pai se não existir
        LISTXML.parent.mkdir(parents=True, exist_ok=True)

        with open(LISTXML, 'w', encoding='utf-8', errors='ignore') as f:
            # Executa o MAME com -listxml e redireciona a saída
            subprocess.run([str(MAME_EXE), "-listxml"], stdout=f, check=True, text=True, encoding='utf-8', errors='ignore')
        print(f"listxml.xml gerado com sucesso em {LISTXML}")
    except subprocess.CalledProcessError as e:
        print(f"Erro ao executar MAME: {e}")
        raise
    except Exception as e:
        print(f"Erro inesperado: {e}")
        raise


# ===================================================================
# 2. FUNÇÃO AUXILIAR PARA CONEXÃO COM O BANCO
# ===================================================================
def get_connection(db):
    """Obtém a conexão do objeto Database, independente do nome do atributo."""
    for attr in ['conn', 'connection', '_connection', '_conn', 'db']:
        if hasattr(db, attr):
            conn = getattr(db, attr)
            if conn is not None:
                return conn
    if hasattr(db, 'connect'):
        return db.connect()
    raise AttributeError(
        "Não foi possível encontrar a conexão no objeto Database. "
        "Verifique o nome do atributo em core/database.py"
    )


# ===================================================================
# 3. MAIN
# ===================================================================
def main():
    print("=" * 60)
    print("MAME Set Builder")
    print("=" * 60)

    # --- Garantir que o listxml existe ---
    ensure_listxml()

    # --- Conectar ao banco e aplicar migrações ---
    db = Database(DATABASE)
    conn = get_connection(db)

    # Otimizações de desempenho
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_machine_name ON machine(name);")
    conn.commit()

    run_migrations(db)
    repo = MachineRepository(db)

    # --- Importar XML se o banco estiver vazio ---
    if repo.count() == 0:
        print("Importando listxml.xml...")
        parser = XMLParser(LISTXML, DATABASE)
        total = parser.parse()
        print(f"Total importado: {total:,}")
    else:
        print(f"Banco já possui {repo.count():,} máquinas.")

    # --- Ler arquivos .ini (catver, controls, players, etc.) ---
    print("Lendo arquivos .ini da pasta folders...")
    ini_parser = INIParser(FOLDERS, db)
    ini_parser.parse_all()

    # --- Carregar todas as máquinas ---
    machines = repo.get_all()
    print(f"Total de máquinas carregadas: {len(machines):,}")

    # ==============================================================
    # 4. APLICAÇÃO DOS FILTROS (em ordem)
    # ==============================================================

    # ---- 4.1 Filtros Básicos (GUI Aba 1) ----
    print("\n--- Aplicando filtros básicos ---")
    if FILTER_WORKING:
        machines = working_filter().apply(machines)
        print(f"  Após working_filter: {len(machines)}")

    if FILTER_ARCADE:
        machines = category_contains("Arcade").apply(machines)
        print(f"  Após category_contains('Arcade'): {len(machines)}")

    if FILTER_CLONES is False:  # False = excluir clones
        machines = no_clones_filter().apply(machines)
        print(f"  Após no_clones_filter: {len(machines)}")

    if FILTER_CONTROL:
        machines = ContainsFilter("controls", FILTER_CONTROL).apply(machines)
        print(f"  Após controls='{FILTER_CONTROL}': {len(machines)}")

    if FILTER_PLAYERS:
        machines = ContainsFilter("players", FILTER_PLAYERS).apply(machines)
        print(f"  Após players='{FILTER_PLAYERS}': {len(machines)}")

    if FILTER_CATEGORY:
        machines = ContainsFilter("category", FILTER_CATEGORY).apply(machines)
        print(f"  Após category='{FILTER_CATEGORY}': {len(machines)}")

    # ---- 4.2 Filtros Avançados (Limpeza - GUI Aba 2) ----
    print("\n--- Aplicando filtros avançados (limpeza) ---")

    # Remover Mecânicas
    if REMOVE_MECHANICAL:
        machines = [m for m in machines if m.ismechanical == 0]
        print(f"  Removidas mecânicas: {len(machines)}")

    # Remover Devices
    if REMOVE_DEVICES:
        machines = [m for m in machines if m.isdevice == 0]
        print(f"  Removidos devices: {len(machines)}")

    # Remover Junk (Bootlegs, Mahjong, Gambling, Quiz, Pachinko)
    if REMOVE_JUNK:
        junk_keywords = ['bootleg', 'mahjong', 'gambling', 'casino', 'quiz', 'pachinko']
        before = len(machines)
        machines = [
            m for m in machines
            if not any(
                k in (m.category or '').lower() or
                k in (m.genre or '').lower()
                for k in junk_keywords
            )
        ]
        print(f"  Removidos junk (Bootlegs/Mahjong/etc): {len(machines)} (antes: {before})")

    # Remover BIOS (com exceção de software lists, se KEEP_SOFTWARE_BIOS estiver ativo)
    if REMOVE_BIOS:
        before = len(machines)
        if KEEP_SOFTWARE_BIOS:
            # Lista de prefixes de software lists (consoles/PCs domésticos)
            sw_prefixes = [
                'nes/', 'snes/', 'genesis/', 'megadriv/', 'psx/', 'n64/',
                'gb/', 'gba/', 'gbc/', 'sms/', 'sg/', 'pce/', 'tg16/',
                'cpc/', 'msx/', 'amiga/', 'atari/', 'pc/', 'apple/',
                'coleco/', 'intv/', 'vectrex/', 'odyssey2/'
            ]
            def is_software_bios(m):
                if m.isbios != 1:
                    return False
                if m.sourcefile:
                    for prefix in sw_prefixes:
                        if m.sourcefile.lower().startswith(prefix):
                            return True
                return False

            # Mantém máquinas que NÃO são BIOS OU são BIOS de software
            machines = [m for m in machines if m.isbios == 0 or is_software_bios(m)]
        else:
            # Remove todas as BIOS
            machines = [m for m in machines if m.isbios == 0]
        print(f"  Removidas BIOS: {len(machines)} (antes: {before})")

    # ---- 4.3 Resultado final ----
    print(f"\n--- Total de máquinas após todos os filtros: {len(machines):,} ---")

    if len(machines) == 0:
        print("\n⚠️ Nenhuma máquina passou pelos filtros. Verifique suas configurações.")
        print("  - Certifique-se de que os arquivos .ini estão na pasta correta.")
        print("  - Ajuste os filtros nas abas da GUI.")
        return

    # ==============================================================
    # 5. EXPORTAÇÃO PARA DAT
    # ==============================================================
    print("\n--- Exportando DAT ---")
    OUTPUT_DAT.parent.mkdir(parents=True, exist_ok=True)
    exporter = DATExporter(machines, OUTPUT_DAT, dat_name="MAME Filtrado")
    exporter.export()
    print(f"DAT exportado: {OUTPUT_DAT}")

    # Fechar conexão
    if hasattr(db, 'close'):
        db.close()
    else:
        conn.close()

    print("=" * 60)
    print("Concluído!")


if __name__ == "__main__":
    main()