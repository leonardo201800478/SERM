# parsers/ini_parser.py
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
    }

    # Arquivos que usam valor booleano (True/False) em vez do nome da seção
    BOOLEAN_FILES = {"working_arcade.ini"}

    def __init__(self, folders_dir: Path, db: Database):
        self.folders_dir = folders_dir
        self.db = db
        self.repo = MachineRepository(db)

    def parse_all(self):
        for ini_file in self.folders_dir.glob("*.ini"):
            self.parse_file(ini_file)

    def parse_file(self, ini_file: Path):
        column = self.FILE_TO_COLUMN.get(ini_file.name)
        if not column:
            print(f"Ignorando {ini_file.name} (sem mapeamento)")
            return

        print(f"Lendo {ini_file.name} -> coluna '{column}'...")
        
        # Dicionário: seção -> lista de nomes de máquinas
        sections = {}
        current_section = None
        total_lines = 0
        parsed_lines = 0

        with open(ini_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                total_lines += 1
                line = line.strip()
                if not line:
                    continue
                # Ignora comentários
                if line.startswith(';') or line.startswith('#'):
                    continue

                # Verifica se é uma seção
                if line.startswith('[') and line.endswith(']'):
                    current_section = line[1:-1].strip()
                    # Ignora seções de configuração
                    if current_section in ('FOLDER_SETTINGS', 'ROOT_FOLDER'):
                        current_section = None
                    else:
                        if current_section not in sections:
                            sections[current_section] = []
                    continue

                # Se não for seção e estiver dentro de uma seção válida, é um nome de máquina
                if current_section and current_section not in ('FOLDER_SETTINGS', 'ROOT_FOLDER'):
                    machine_name = line.lower()
                    if machine_name:
                        sections[current_section].append(machine_name)
                        parsed_lines += 1

        # Agora, para cada seção, geramos os updates
        updates = []
        is_boolean = ini_file.name in self.BOOLEAN_FILES

        for section, machines in sections.items():
            if not machines:
                continue
            # Define o valor a ser atribuído
            if is_boolean:
                value = "1"  # True
            else:
                value = section  # ex: "Action", "Sports"

            for machine in machines:
                updates.append((value, machine))

        if updates:
            self.repo.bulk_update_column(column, updates)
            print(f"  Atualizadas {len(updates)} máquinas.")
            # Mostra uma amostra dos valores
            sample = updates[:5]
            print(f"  Exemplos: {[(name, val) for val, name in sample]}")
        else:
            print(f"  Nenhuma máquina encontrada no arquivo. Verifique o formato.")