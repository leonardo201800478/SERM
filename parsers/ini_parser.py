from pathlib import Path
from core.database import Database
from repositories.machine_repository import MachineRepository

class INIParser:
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
        "controls.ini": "controls",
        "cpu.ini": "cpu",
        "sound.ini": "sound",
        "display.ini": "display",
        "graphics.ini": "graphics",
    }

    BOOLEAN_FILES = {"working_arcade.ini"}

    KEY_VALUE_FILES = {
        "controls.ini",
        "cpu.ini",
        "sound.ini",
        "display.ini",
        "graphics.ini",
        "machine_type.ini",
    }

    def __init__(self, folders_dir: Path, db: Database):
        self.folders_dir = folders_dir
        self.db = db
        self.repo = MachineRepository(db)

    def parse_all(self, stop_flag=None):
        files = list(self.folders_dir.glob("*.ini"))
        total = len(files)
        print(f"Encontrados {total} arquivos .ini para processar.")

        for idx, ini_file in enumerate(files):
            if stop_flag and getattr(stop_flag, 'stop_flag', False):
                print("\n⏹ Importação de INIs interrompida pelo usuário.")
                break

            print(f"Processando {ini_file.name} ({idx+1}/{total})...")
            self.parse_file(ini_file)

            # Atualiza ambas as barras de progresso
            if stop_flag and hasattr(stop_flag, 'progress_callback') and stop_flag.progress_callback:
                progress = int((idx + 1) / total * 100)
                stop_flag.progress_callback(
                    value=progress,                # barra total
                    status=f"INIs: {progress}%",
                    partial_value=progress         # barra parcial
                )

    def parse_file(self, ini_file: Path):
        column = self.FILE_TO_COLUMN.get(ini_file.name)
        if not column:
            print(f"Ignorando {ini_file.name} (sem mapeamento)")
            return

        print(f"Lendo {ini_file.name} -> coluna '{column}'...")

        # Detecção de formato
        is_key_value = False
        try:
            with open(ini_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith(';') or line.startswith('#'):
                        continue
                    if '=' in line:
                        is_key_value = True
                    break
        except Exception as e:
            print(f"  Erro ao ler arquivo: {e}")
            return

        # Formato key=value
        if is_key_value or ini_file.name in self.KEY_VALUE_FILES:
            updates = []
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
            if updates:
                self.repo.bulk_update_column(column, updates)
                print(f"  Atualizadas {len(updates)} máquinas.")
                sample = updates[:5]
                print(f"  Exemplos: {[(name, val) for val, name in sample]}")
            else:
                print(f"  Nenhuma máquina encontrada no arquivo.")
            return

        # Formato de seções
        sections = {}
        current_section = None
        with open(ini_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith(';') or line.startswith('#'):
                    continue
                if line.startswith('[') and line.endswith(']'):
                    current_section = line[1:-1].strip()
                    if current_section == 'FOLDER_SETTINGS':
                        current_section = None
                    else:
                        if current_section not in sections:
                            sections[current_section] = []
                    continue
                if current_section and current_section != 'FOLDER_SETTINGS':
                    machine_name = line.lower()
                    if machine_name:
                        sections[current_section].append(machine_name)

        updates = []
        is_boolean = ini_file.name in self.BOOLEAN_FILES

        for section, machines in sections.items():
            if not machines:
                continue
            value = "1" if is_boolean else section
            for machine in machines:
                updates.append((value, machine))

        if updates:
            self.repo.bulk_update_column(column, updates)
            print(f"  Atualizadas {len(updates)} máquinas.")
            sample = updates[:5]
            print(f"  Exemplos: {[(name, val) for val, name in sample]}")
        else:
            print(f"  Nenhuma máquina encontrada no arquivo. Verifique o formato.")