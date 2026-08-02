from pathlib import Path
from core.database import Database
from repositories.machine_repository import MachineRepository

class INIParser:
    # Mapeamento do nome do arquivo para a coluna no banco
    FILE_TO_COLUMN = {
        "category.ini": "category",
        "genre.ini": "genre",
        "genre_ows.ini": "genre_ows",
        "machine_category.ini": "machine_category",
        "machine_type.ini": "machine_type",
        "players.ini": "players",
        "resolution.ini": "resolution",
        "version.ini": "version",
        "working_arcade.ini": "working_arcade",
        "controls.ini": "controls",   # se tiver a coluna
        "cpu.ini": "cpu",             # se tiver
        "sound.ini": "sound",         # se tiver
    }

    # Arquivos que usam valor booleano (True/False) em vez do nome da seção
    BOOLEAN_FILES = {"working_arcade.ini"}

    # Arquivos que devem ser processados como chave=valor (em vez de seções)
    KEY_VALUE_FILES = {
        "players.ini",
        "resolution.ini",
        "version.ini",
        "controls.ini",
        "cpu.ini",
        "sound.ini",
        "machine_type.ini",  # pode ter valores como "<not available>"
    }

    def __init__(self, folders_dir: Path, db: Database):
        self.folders_dir = folders_dir
        self.db = db
        self.repo = MachineRepository(db)

    def parse_all(self, stop_flag=None):
        """Processa todos os arquivos .ini na pasta, com suporte a interrupção."""
        files = list(self.folders_dir.glob("*.ini"))
        total = len(files)
        for idx, ini_file in enumerate(files):
            if stop_flag and getattr(stop_flag, 'stop_flag', False):
                print("\n⏹ Importação de INIs interrompida pelo usuário.")
                break
            print(f"Processando {ini_file.name} ({idx+1}/{total})...")
            self.parse_file(ini_file)
            # Atualiza progresso se disponível
            if stop_flag and hasattr(stop_flag, 'progress_callback') and stop_flag.progress_callback:
                progress = int((idx + 1) / total * 100)
                stop_flag.progress_callback(progress, f"Processando {ini_file.name}")

    def parse_file(self, ini_file: Path):
        column = self.FILE_TO_COLUMN.get(ini_file.name)
        if not column:
            print(f"Ignorando {ini_file.name} (sem mapeamento)")
            return

        print(f"Lendo {ini_file.name} -> coluna '{column}'...")

        # Detecta formato: se qualquer linha não vazia contém '=', é key=value
        is_key_value = False
        try:
            with open(ini_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith(';') and not line.startswith('#'):
                        if '=' in line:
                            is_key_value = True
                        break
        except Exception as e:
            print(f"  Erro ao ler arquivo: {e}")
            return

        updates = []

        if is_key_value or ini_file.name in self.KEY_VALUE_FILES:
            # Formato chave=valor
            with open(ini_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith(';') or line.startswith('#'):
                        continue
                    if '=' not in line:
                        continue
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    if key:
                        updates.append((value, key))
        else:
            # Formato com seções
            sections = {}
            current_section = None
            with open(ini_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith(';') or line.startswith('#'):
                        continue
                    if line.startswith('[') and line.endswith(']'):
                        current_section = line[1:-1].strip()
                        if current_section in ('FOLDER_SETTINGS', 'ROOT_FOLDER'):
                            current_section = None
                        else:
                            if current_section not in sections:
                                sections[current_section] = []
                        continue
                    if current_section and current_section not in ('FOLDER_SETTINGS', 'ROOT_FOLDER'):
                        machine_name = line.lower()
                        if machine_name:
                            sections[current_section].append(machine_name)

            is_boolean = ini_file.name in self.BOOLEAN_FILES
            for section, machines in sections.items():
                if not machines:
                    continue
                if is_boolean:
                    value = "1"  # True
                else:
                    value = section  # ex: "Action"
                for machine in machines:
                    updates.append((value, machine))

        if updates:
            self.repo.bulk_update_column(column, updates)
            print(f"  Atualizadas {len(updates)} máquinas.")
            sample = updates[:5]
            # Mostra exemplos: (nome, valor)
            print(f"  Exemplos: {[(name, val) for val, name in sample]}")
        else:
            print(f"  Nenhuma máquina encontrada no arquivo. Verifique o formato.")