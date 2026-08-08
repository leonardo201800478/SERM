# src/mame_set_builder/mame/executable.py
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
        return self.path.is_file() and os.access(self.path, os.X_OK)

    def get_version(self) -> str:
        if self._version is None:
            result = subprocess.run(
                [str(self.path), "-version"],
                capture_output=True,
                text=True,
                check=True,
            )
            for line in result.stdout.splitlines():
                if "MAME" in line:
                    match = re.search(r"(\d+\.\d+)", line)
                    if match:
                        self._version = match.group(1)
                        break
            if not self._version:
                raise RuntimeError("Não foi possível determinar a versão do MAME.")
        return self._version

    def generate_listxml(self) -> subprocess.Popen:
        return subprocess.Popen(
            [str(self.path), "-listxml"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )