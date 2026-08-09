import subprocess
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SetValidator:
    def __init__(self, mame_executable: Path):
        self.mame = mame_executable

    def verify(self, set_path: Path, machine_names: list) -> Dict[str, str]:
        results = {}
        for machine in machine_names:
            try:
                result = subprocess.run(
                    [str(self.mame), "-verifyroms", machine],
                    cwd=str(set_path),
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if "is good" in result.stdout or "is best available" in result.stdout:
                    results[machine] = "OK"
                else:
                    results[machine] = result.stdout.strip() or "FAIL"
            except Exception as e:
                results[machine] = f"ERROR: {e}"
        return results