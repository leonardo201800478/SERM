import subprocess
import json
import time
from pathlib import Path
from config import (
    LISTXML, DATABASE, FOLDERS, OUTPUT_DAT, MAME_EXE,
    FILTER_WORKING, FILTER_ARCADE, FILTER_CLONES,
    FILTER_CONTROLS, FILTER_PLAYERS, FILTER_CATEGORIES,
    REMOVE_MECHANICAL, REMOVE_BIOS, REMOVE_DEVICES, REMOVE_JUNK, KEEP_SOFTWARE_BIOS,
    TORRENT_LINKS, ENABLE_TORRENT, ROM_DIR, SOFTWARE_ROM_DIR,
    QB_EXE, QB_HOST, QB_PORT, QB_USER, QB_PASS
)
from parsers.xml_parser import XMLParser
from parsers.ini_parser import INIParser
from core.database import Database
from core.migrations import run_migrations
from repositories.machine_repository import MachineRepository
from filters.filters import (
    working_filter, no_clones_filter, no_mechanical_filter,
    category_contains, CompositeFilter, ContainsFilter,
    BooleanFilter, FilterClass
)
from exporters.dat_exporter import DATExporter

# ===================================================================
# FUNÇÕES AUXILIARES
# ===================================================================

def ensure_listxml():
    if LISTXML.exists():
        print(f"Arquivo listxml já existe: {LISTXML}")
        return
    print("Gerando listxml.xml a partir do MAME...")
    if not MAME_EXE.exists():
        raise FileNotFoundError(f"Executável do MAME não encontrado: {MAME_EXE}")
    LISTXML.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(LISTXML, 'w', encoding='utf-8', errors='ignore') as f:
            subprocess.run([str(MAME_EXE), "-listxml"], stdout=f, check=True, text=True, encoding='utf-8', errors='ignore')
        print(f"listxml.xml gerado com sucesso em {LISTXML}")
    except Exception as e:
        print(f"Erro ao gerar listxml: {e}")
        raise

def get_connection(db):
    for attr in ['conn', 'connection', '_connection', '_conn', 'db']:
        if hasattr(db, attr):
            conn = getattr(db, attr)
            if conn is not None:
                return conn
    if hasattr(db, 'connect'):
        return db.connect()
    raise AttributeError("Conexão não encontrada no objeto Database.")

def generate_torrent_script(machines, output_dir):
    if not ENABLE_TORRENT:
        return
    rom_names = [m.name for m in machines]

    def get_missing_files(names, directory, extension='.zip'):
        if not directory.exists():
            return names
        existing = {f.stem for f in directory.glob(f'*{extension}') if f.is_file()}
        missing = [name for name in names if name not in existing]
        return missing

    categories = {
        'mame_roms': (rom_names, ROM_DIR, '.zip'),
        'mame_bios': (rom_names, ROM_DIR, '.zip'),
        'software_roms': (rom_names, SOFTWARE_ROM_DIR, '.zip'),
    }
    missing_by_category = {}
    for cat, (names, dir_path, ext) in categories.items():
        missing = get_missing_files(names, dir_path, ext)
        if missing:
            missing_by_category[cat] = missing

    if not missing_by_category:
        print("Todos os arquivos já estão presentes. Nenhum download necessário.")
        return

    json_path = output_dir / "missing_files.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(missing_by_category, f, indent=2)
    print(f"Lista de arquivos faltantes salva em: {json_path}")

    if QB_EXE or (QB_HOST and QB_PORT):
        try:
            from torrent_manager import start_qbittorrent, connect_qbittorrent, add_torrent_with_files
            if QB_EXE:
                start_qbittorrent(QB_EXE)
            client = connect_qbittorrent(QB_HOST, int(QB_PORT), QB_USER, QB_PASS)
            if client:
                for cat, files in missing_by_category.items():
                    magnet = TORRENT_LINKS.get(cat)
                    if magnet:
                        if cat in ('mame_roms', 'mame_bios'):
                            save_path = ROM_DIR
                        elif cat == 'software_roms':
                            save_path = SOFTWARE_ROM_DIR
                        else:
                            save_path = output_dir / "downloads"
                        print(f"Adicionando torrent para {cat} com {len(files)} arquivos...")
                        add_torrent_with_files(client, magnet, files, save_path)
                print("Torrents adicionados com sucesso.")
            else:
                print("Não foi possível conectar ao qBittorrent. Verifique as credenciais.")
        except Exception as e:
            print(f"Erro na integração com qBittorrent: {e}")
    else:
        print("qBittorrent não configurado. Gere o script manualmente.")

# ===================================================================
# FUNÇÕES PRINCIPAIS (com suporte a stop_flag)
# ===================================================================

def import_xml_only(stop_flag=None):
    """Apenas importa o XML para o banco (se vazio)."""
    print("=" * 60)
    print("MAME Set Builder - Importação XML")
    print("=" * 60)

    ensure_listxml()
    db = Database(DATABASE)
    conn = get_connection(db)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_machine_name ON machine(name);")
    conn.commit()
    run_migrations(db)
    repo = MachineRepository(db)

    if repo.count() == 0:
        print("Importando listxml.xml...")
        parser = XMLParser(LISTXML, DATABASE)
        total = parser.parse()
        print(f"Total importado: {total:,}")
    else:
        print(f"Banco já possui {repo.count():,} máquinas. Nenhuma importação necessária.")

    conn.close()
    return "Importação XML concluída."

def import_inis_only(stop_flag=None):
    """Apenas lê os arquivos .ini e atualiza o banco, com verificação de parada."""
    print("=" * 60)
    print("MAME Set Builder - Importação INIs")
    print("=" * 60)

    db = Database(DATABASE)
    conn = get_connection(db)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_machine_name ON machine(name);")
    conn.commit()
    run_migrations(db)

    if not FOLDERS.exists():
        print(f"Pasta de INIs não encontrada: {FOLDERS}")
        return "Pasta de INIs não encontrada."

    print("Lendo arquivos .ini da pasta folders...")
    ini_parser = INIParser(FOLDERS, db)

    # Sobrescrever o método parse_all para verificar stop_flag
    original_parse_all = ini_parser.parse_all

    def parse_all_with_stop():
        """Versão modificada que verifica stop_flag entre arquivos."""
        files = list(FOLDERS.glob("*.ini"))
        total = len(files)
        for idx, ini_file in enumerate(files):
            if stop_flag and getattr(stop_flag, 'stop_flag', False):
                print("\n⏹ Importação interrompida pelo usuário.")
                break
            print(f"Processando {ini_file.name} ({idx+1}/{total})...")
            ini_parser.parse_file(ini_file)
            # Opcional: atualizar progresso se houver callback
            if hasattr(stop_flag, 'progress_callback') and stop_flag.progress_callback:
                progress = int((idx+1) / total * 100)
                stop_flag.progress_callback(progress, f"Processando {ini_file.name}")
        # Atualizar progresso para 100% se concluído
        if hasattr(stop_flag, 'progress_callback') and stop_flag.progress_callback:
            stop_flag.progress_callback(100, "Importação de INIs concluída")

    # Substituir método
    ini_parser.parse_all = parse_all_with_stop
    ini_parser.parse_all()

    conn.close()
    return "Importação de INIs concluída."

def generate_dat_only(stop_flag=None):
    """Aplica filtros e gera o DAT, sem reimportar XML/INIs."""
    print("=" * 60)
    print("MAME Set Builder - Geração de DAT")
    print("=" * 60)

    db = Database(DATABASE)
    conn = get_connection(db)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_machine_name ON machine(name);")
    conn.commit()
    run_migrations(db)
    repo = MachineRepository(db)

    if repo.count() == 0:
        print("Banco vazio! Execute 'Importar XML' primeiro.")
        return "Banco vazio. Execute Importar XML primeiro."

    machines = repo.get_all()
    print(f"Total de máquinas carregadas: {len(machines):,}")

    # Verificar parada antes de cada etapa
    if stop_flag and getattr(stop_flag, 'stop_flag', False):
        print("⏹ Processamento interrompido.")
        return "Processamento interrompido."

    print("\n--- Aplicando filtros básicos ---")
    if FILTER_WORKING:
        machines = working_filter().apply(machines)
        print(f"  Após working_filter: {len(machines)}")
    if FILTER_ARCADE:
        machines = category_contains("Arcade").apply(machines)
        print(f"  Após category_contains('Arcade'): {len(machines)}")
    if not FILTER_CLONES:
        machines = no_clones_filter().apply(machines)
        print(f"  Após no_clones_filter: {len(machines)}")
    if stop_flag and getattr(stop_flag, 'stop_flag', False):
        print("⏹ Processamento interrompido.")
        return "Processamento interrompido."

    if FILTER_CONTROLS:
        filters = [ContainsFilter("controls", c) for c in FILTER_CONTROLS]
        control_filter = CompositeFilter(filters, mode="OR")
        machines = control_filter.apply(machines)
        print(f"  Após controles {FILTER_CONTROLS}: {len(machines)}")
    if FILTER_PLAYERS:
        filters = [ContainsFilter("players", p) for p in FILTER_PLAYERS]
        players_filter = CompositeFilter(filters, mode="OR")
        machines = players_filter.apply(machines)
        print(f"  Após jogadores {FILTER_PLAYERS}: {len(machines)}")
    if FILTER_CATEGORIES:
        filters = [ContainsFilter("category", cat) for cat in FILTER_CATEGORIES]
        category_filter = CompositeFilter(filters, mode="OR")
        machines = category_filter.apply(machines)
        print(f"  Após categorias {FILTER_CATEGORIES}: {len(machines)}")
    if stop_flag and getattr(stop_flag, 'stop_flag', False):
        print("⏹ Processamento interrompido.")
        return "Processamento interrompido."

    print("\n--- Aplicando filtros avançados (limpeza) ---")
    if REMOVE_MECHANICAL:
        machines = [m for m in machines if m.ismechanical == 0]
        print(f"  Removidas mecânicas: {len(machines)}")
    if REMOVE_DEVICES:
        machines = [m for m in machines if m.isdevice == 0]
        print(f"  Removidos devices: {len(machines)}")
    if REMOVE_JUNK:
        junk_keywords = ['bootleg', 'mahjong', 'gambling', 'casino', 'quiz', 'pachinko']
        before = len(machines)
        machines = [
            m for m in machines
            if not any(k in (m.category or '').lower() or k in (m.genre or '').lower() for k in junk_keywords)
        ]
        print(f"  Removidos junk: {len(machines)} (antes: {before})")
    if REMOVE_BIOS:
        before = len(machines)
        if KEEP_SOFTWARE_BIOS:
            sw_prefixes = ['nes/', 'snes/', 'genesis/', 'megadriv/', 'psx/', 'n64/',
                           'gb/', 'gba/', 'gbc/', 'sms/', 'sg/', 'pce/', 'tg16/',
                           'cpc/', 'msx/', 'amiga/', 'atari/', 'pc/', 'apple/',
                           'coleco/', 'intv/', 'vectrex/', 'odyssey2/']
            def is_software_bios(m):
                if m.isbios != 1:
                    return False
                if m.sourcefile:
                    for prefix in sw_prefixes:
                        if m.sourcefile.lower().startswith(prefix):
                            return True
                return False
            machines = [m for m in machines if m.isbios == 0 or is_software_bios(m)]
        else:
            machines = [m for m in machines if m.isbios == 0]
        print(f"  Removidas BIOS: {len(machines)} (antes: {before})")
    if stop_flag and getattr(stop_flag, 'stop_flag', False):
        print("⏹ Processamento interrompido.")
        return "Processamento interrompido."

    print(f"\n--- Total de máquinas após todos os filtros: {len(machines):,} ---")
    if len(machines) == 0:
        print("\n⚠️ Nenhuma máquina passou pelos filtros.")
        return "Nenhuma máquina passou pelos filtros."

    generate_torrent_script(machines, OUTPUT_DAT.parent)

    print("\n--- Exportando DAT ---")
    OUTPUT_DAT.parent.mkdir(parents=True, exist_ok=True)
    exporter = DATExporter(machines, OUTPUT_DAT, dat_name="MAME Filtrado")
    exporter.export()
    print(f"DAT exportado: {OUTPUT_DAT}")

    conn.close()
    return f"DAT gerado com {len(machines):,} máquinas."

# ===================================================================
# MAIN ORIGINAL (mantido para compatibilidade)
# ===================================================================

def main():
    import_xml_only()
    import_inis_only()
    generate_dat_only()

if __name__ == "__main__":
    main()