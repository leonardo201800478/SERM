"""
Módulo para interagir com o executável do MAME.
Obtém versão e gera o -listxml com encoding UTF-8.
"""

import os
import subprocess
import re
from pathlib import Path
from typing import Optional

class MAMEExecutable:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._version: Optional[str] = None

    def validate(self) -> bool:
        """Verifica se o arquivo existe e tem permissão de execução."""
        return self.path.is_file() and os.access(self.path, os.X_OK)

    def get_version(self) -> str:
        """
        Executa mame -version e extrai o número da versão.
        Suporta formatos como:
          - "0.289 (mame0289)"
          - "MAME 0.270 (mame0270)"
        """
        if self._version is not None:
            return self._version

        try:
            result = subprocess.run(
                [str(self.path), "-version"],
                capture_output=True,
                text=True,
                encoding='utf-8',          # forçar UTF-8 para evitar erros de decodificação
                check=True,
            )
            output = result.stdout.strip()
            print(f"[DEBUG] Saída do -version: {output}")

            # Tenta capturar o número da versão no início ou em qualquer lugar
            match = re.search(r'^(\d+\.\d+(?:\.\d+)?)', output)
            if not match:
                match = re.search(r'(\d+\.\d+(?:\.\d+)?)', output)

            if match:
                self._version = match.group(1)
                print(f"[DEBUG] Versão detectada: {self._version}")
                return self._version

            raise RuntimeError(f"Não foi possível extrair a versão da saída: {output}")

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Erro ao executar {self.path} -version: {e.stderr}") from e
        except FileNotFoundError:
            raise RuntimeError(f"Executável não encontrado: {self.path}") from None

    def generate_listxml(self) -> subprocess.Popen:
        """
        Retorna um processo Popen com stdout em modo texto e encoding UTF-8.
        Isso evita erros de decodificação com caracteres especiais no listxml.
        """
        return subprocess.Popen(
            [str(self.path), "-listxml"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,                 # modo texto (retorna strings)
            encoding='utf-8',          # encoding explícito
            bufsize=1,                 # line buffered
        )