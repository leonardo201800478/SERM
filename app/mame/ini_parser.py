from pathlib import Path
from typing import Dict, Optional, List, Tuple

class MameIniParser:
    def __init__(self, ini_path: Path):
        self.ini_path = ini_path
        self.lines: List[Tuple[str, str, str]] = []  # (key, value, original_line) para opções conhecidas
        self.comments: List[str] = []  # linhas de comentário
        self.options: Dict[str, str] = {}

    def load(self):
        if not self.ini_path.exists():
            return
        with open(self.ini_path, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith('#') or stripped.startswith(';'):
                    self.comments.append(line)
                    continue
                if '=' in stripped:
                    key, value = stripped.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    self.options[key] = value
                    self.lines.append((key, value, line))
                else:
                    # linha vazia ou não reconhecida, manter como está
                    self.lines.append(('', '', line))

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.options.get(key, default)

    def set(self, key: str, value: str):
        self.options[key] = value
        # Atualiza a linha se já existir
        for i, (k, v, line) in enumerate(self.lines):
            if k == key:
                self.lines[i] = (key, value, f"{key}={value}\n")
                break
        else:
            # Adiciona nova opção ao final
            self.lines.append((key, value, f"{key}={value}\n"))

    def save(self):
        with open(self.ini_path, 'w', encoding='utf-8') as f:
            # Escreve as linhas na ordem original, atualizando opções
            for item in self.lines:
                if len(item) == 3:
                    key, value, line = item
                    if key:  # opção conhecida
                        f.write(f"{key}={value}\n")
                    else:
                        f.write(line)
                else:
                    f.write(item)  # comentário ou linha não reconhecida
            # Adiciona opções novas que não estavam na lista
            for key, value in self.options.items():
                if not any(k == key for k, _, _ in self.lines if k):
                    f.write(f"{key}={value}\n")