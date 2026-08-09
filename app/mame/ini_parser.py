from pathlib import Path
from typing import Dict, List, Optional, Tuple

class MameIniParser:
    def __init__(self, ini_path: Path):
        self.ini_path = ini_path
        self.lines: List[str] = []  # Linhas originais (incluindo comentários e seções)
        self.options: Dict[str, Tuple[int, str]] = {}  # key -> (line_index, value)
        self.modified: Dict[str, str] = {}  # key -> novo valor (apenas para opções modificadas)

    def load(self):
        """Carrega o arquivo preservando todas as linhas."""
        if not self.ini_path.exists():
            return
        with open(self.ini_path, 'r', encoding='utf-8') as f:
            self.lines = f.readlines()

        # Mapeia opções para índices de linha
        for i, line in enumerate(self.lines):
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and not stripped.startswith(';'):
                if '=' in stripped:
                    key, value = stripped.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    self.options[key] = (i, value)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Obtém o valor atual de uma opção (modificado ou original)."""
        if key in self.modified:
            return self.modified[key]
        if key in self.options:
            return self.options[key][1]
        return default

    def set(self, key: str, value: str):
        """Marca uma opção para ser modificada (apenas se ela já existir)."""
        if key in self.options:
            self.modified[key] = value
        else:
            # Opção não existe no arquivo original - não adicionar (conforme solicitado)
            pass

    def save(self):
        """Salva o arquivo com as modificações, mantendo comentários e estrutura."""
        if not self.ini_path:
            return

        # Aplica modificações nas linhas
        for key, new_value in self.modified.items():
            if key in self.options:
                idx, _ = self.options[key]
                line = self.lines[idx]
                # Preserva espaçamento e comentários após o valor
                if '=' in line:
                    prefix, _ = line.split('=', 1)
                    self.lines[idx] = f"{prefix}={new_value}\n"

        # Escreve o arquivo
        with open(self.ini_path, 'w', encoding='utf-8') as f:
            f.writelines(self.lines)

    def get_all_options(self) -> Dict[str, str]:
        """Retorna todas as opções com seus valores atuais (modificados ou não)."""
        result = {}
        for key, (idx, value) in self.options.items():
            result[key] = self.modified.get(key, value)
        return result