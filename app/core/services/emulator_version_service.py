"""Detecção silenciosa e uniforme das versões dos emuladores configurados."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional


class EmulatorVersionService:
    """Consulta versões de executáveis sem gerar janelas ou mensagens de erro."""

    _TIMEOUT = 5
    _VERSION_ARGS = {
        "mame": ("-version",),
        "flycast": ("--version",),
        "supermodel": ("-version",),
        "fbneo": ("-version",),
    }

    def detect(self, emulator: str, path: Path | str | None) -> Optional[str]:
        """Retorna a versão textual detectada ou ``None`` quando indisponível."""
        if not path:
            return None
        executable = Path(path).expanduser()
        if not executable.is_file():
            return None

        args = self._VERSION_ARGS.get(emulator.lower(), ("--version",))
        try:
            result = subprocess.run(
                [str(executable), *args],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._TIMEOUT,
                shell=False,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError):
            return None

        output = "\n".join((result.stdout or "", result.stderr or ""))
        patterns = (
            r"(?i)\b(?:version|v)?\s*([0-9]+(?:\.[0-9]+)+(?:[-+._][0-9A-Za-z.-]+)?)\b",
            r"\b([0-9]{3,4})\b",
        )
        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                return match.group(1)
        return None

    def detect_all(self, paths: dict[str, Path | str | None]) -> dict[str, Optional[str]]:
        """Detecta todas as versões fornecidas sem interromper por falhas individuais."""
        return {name: self.detect(name, path) for name, path in paths.items()}
