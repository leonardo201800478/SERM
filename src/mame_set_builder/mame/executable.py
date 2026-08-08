# src/mame_set_builder/mame/executable.py
import os
import subprocess
from pathlib import Path
from typing import Optional

class MAMEExecutable:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._version: Optional[str] = None

    def validate(self) -> bool:
        """Verifica se o arquivo existe e parece ser um executável MAME."""
        return self.path.is_file() and os.access(self.path, os.X_OK)

    def get_version(self) -> str:
        """Retorna a versão do MAME (ex.: '0.270')."""
        if self._version is None:
            result = subprocess.run(
                [str(self.path), "-version"],
                capture_output=True,
                text=True,
                check=True,
            )
            # Exemplo de saída: "MAME 0.270 (mame0270)"
            # Extrair o número da versão
            for line in result.stdout.splitlines():
                if "MAME" in line:
                    parts = line.split()
                    # Pode variar; tentamos capturar a primeira sequência numérica com ponto
                    import re
                    match = re.search(r"(\d+\.\d+)", line)
                    if match:
                        self._version = match.group(1)
                        break
            if not self._version:
                raise RuntimeError("Não foi possível determinar a versão do MAME.")
        return self._version

    def generate_listxml(self) -> subprocess.Popen:
        """Retorna um processo Popen com stdout apontando para a saída do -listxml."""
        return subprocess.Popen(
            [str(self.path), "-listxml"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # line buffered
        )