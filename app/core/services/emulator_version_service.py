"""Detecção silenciosa das versões dos emuladores configurados.

A detecção nunca abre diálogos e nunca interrompe a inicialização. Erros são
registrados em DEBUG e retornados como estado para a GUI decidir como exibir.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Sequence


@dataclass(frozen=True, slots=True)
class EmulatorVersion:
    """Estado da versão detectada de um emulador."""

    name: str
    executable: str | None
    version: str | None
    available: bool
    error: str | None = None


class EmulatorVersionService:
    """Detecta versões sem UI e sem produzir pop-ups."""

    _COMMANDS: dict[str, tuple[str, ...]] = {
        "mame": ("-version",),
        "flycast": ("--version",),
        "supermodel": ("--version",),
        "fbneo": ("--version",),
    }

    def detect(self, name: str, executable: str | Path | None) -> EmulatorVersion:
        """Executa o binário configurado e extrai sua versão silenciosamente."""
        if not executable:
            return EmulatorVersion(name, None, None, False, "executável não configurado")

        path = Path(executable)
        if not path.exists() or not path.is_file():
            return EmulatorVersion(name, str(path), None, False, "executável não encontrado")

        args = self._COMMANDS.get(name.lower(), ("--version",))
        try:
            completed = subprocess.run(
                [str(path), *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return EmulatorVersion(name, str(path), None, False, str(exc))

        output = "\n".join(x for x in (completed.stdout, completed.stderr) if x)
        version = self._extract_version(output)
        if completed.returncode != 0 and not version:
            return EmulatorVersion(name, str(path), None, False, output.strip() or "falha ao consultar versão")
        return EmulatorVersion(name, str(path), version or "desconhecida", True)

    @staticmethod
    def _extract_version(output: str) -> str | None:
        """Extrai a primeira versão sem impor um formato específico ao projeto."""
        patterns = (
            r"\b(?:version|v)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)+(?:[-+._][0-9A-Za-z.-]+)?)\b",
            r"\b([0-9]+\.[0-9]+(?:\.[0-9]+)+(?:[-+._][0-9A-Za-z.-]+)?)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def detect_many(self, executables: dict[str, str | Path | None]) -> dict[str, EmulatorVersion]:
        """Detecta todos os emuladores configurados sem alterar a UI."""
        return {name: self.detect(name, executable) for name, executable in executables.items()}
