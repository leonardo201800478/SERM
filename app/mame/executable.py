import subprocess
import re
from pathlib import Path
from typing import Optional

class MameExecutable:
    def __init__(self, path: Path):
        self.path = path
        self._version = None

    @property
    def version(self) -> Optional[str]:
        if self._version is None:
            self._detect_version()
        return self._version

    def _detect_version(self):
        if not self.path.exists():
            raise FileNotFoundError(f"MAME executable not found: {self.path}")
        try:
            result = subprocess.run([str(self.path), "-version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                match = re.search(r'MAME\s+([\d.]+)', result.stdout)
                if match:
                    self._version = match.group(1)
                else:
                    self._version = "unknown"
            else:
                self._version = "unknown"
        except Exception as e:
            raise RuntimeError(f"Failed to detect MAME version: {e}")

    def get_listxml(self) -> str:
        """Executa mame -listxml e retorna o XML como string."""
        try:
            result = subprocess.run([str(self.path), "-listxml"], capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                raise RuntimeError(f"Error running listxml: {result.stderr}")
            return result.stdout
        except Exception as e:
            raise RuntimeError(f"Failed to get listxml: {e}")