"""Validação de CHD usando o chdman da mesma distribuição do MAME.

CHD não é validado calculando SHA-1 do arquivo físico. O digest esperado pelo
MAME é o digest do conteúdo lógico armazenado no CHD; o tamanho físico também
pode variar conforme a compressão. Por isso a validação é delegada ao chdman e,
quando disponível, o SHA-1 lógico reportado por ``chdman info`` é comparado ao
SHA-1 esperado no LISTXML.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.config.app_config import AppConfig

_SHA1_RE = re.compile(r"\b[0-9a-fA-F]{40}\b")


@dataclass(frozen=True, slots=True)
class ChdValidationResult:
    """Resultado determinístico da validação de um CHD."""

    valid: bool
    verified: bool
    logical_sha1: str | None
    reason: str
    command: tuple[str, ...] = ()


class ChdValidator:
    """Valida CHDs sem modificar a fonte física."""

    def __init__(self, chdman_path: str | Path | None = None, *, timeout: int = 1800) -> None:
        self.timeout = max(30, int(timeout))
        self.chdman_path = self._resolve_chdman(chdman_path)

    @staticmethod
    def _resolve_chdman(configured: str | Path | None) -> Path | None:
        """Resolve explicitamente ou por autodetecção o executável chdman."""
        candidates: list[Path] = []
        if configured:
            candidates.append(Path(configured).expanduser())

        config = AppConfig()
        if config.chdman_path:
            candidates.append(Path(config.chdman_path).expanduser())
        if config.mame_path:
            root = Path(config.mame_path).expanduser().parent
            candidates.extend((root / "chdman.exe", root / "chdman", root / "exe" / "chdman.exe", root / "exe" / "chdman"))

        seen: set[Path] = set()
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            if resolved.is_file():
                return resolved
        return None

    @property
    def available(self) -> bool:
        """Indica se o chdman está disponível para validação."""
        return self.chdman_path is not None

    def _run(self, args: Iterable[str]) -> subprocess.CompletedProcess[str]:
        """Executa chdman sem shell e captura saída para diagnóstico."""
        if not self.chdman_path:
            raise FileNotFoundError("chdman.exe não está configurado ou não foi encontrado")
        command = [str(self.chdman_path), *args]
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.timeout,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    @staticmethod
    def _output(result: subprocess.CompletedProcess[str]) -> str:
        """Combina stdout/stderr preservando a mensagem útil do chdman."""
        return "\n".join(part for part in (result.stdout, result.stderr) if part).strip()

    @staticmethod
    def _extract_sha1(output: str, expected: str | None) -> str | None:
        """Obtém o SHA-1 lógico informado pelo chdman.info.

        O ``info`` pode apresentar mais de um SHA-1 (dados e metadados). Quando
        há um digest esperado, procuramos exatamente esse digest entre os
        valores reportados; caso contrário retornamos o primeiro digest de 40
        caracteres encontrado para fins de diagnóstico.
        """
        values = [value.lower() for value in _SHA1_RE.findall(output)]
        if not values:
            return None
        expected_norm = (expected or "").strip().lower()
        if expected_norm and expected_norm in values:
            return expected_norm
        return values[0]

    def validate(self, path: str | Path, expected_sha1: str | None = None) -> ChdValidationResult:
        """Executa verify e compara o digest lógico, sem alterar o CHD."""
        chd = Path(path).expanduser().resolve()
        if not chd.is_file():
            return ChdValidationResult(False, False, None, f"CHD inexistente: {chd}")
        if chd.suffix.lower() != ".chd":
            return ChdValidationResult(False, False, None, f"Arquivo não é CHD: {chd}")
        if not self.available:
            return ChdValidationResult(False, False, None, "chdman.exe não configurado")

        verify_command = ("verify", "-i", str(chd))
        try:
            verify = self._run(verify_command)
        except subprocess.TimeoutExpired:
            return ChdValidationResult(False, False, None, "chdman verify excedeu o timeout", verify_command)
        except OSError as exc:
            return ChdValidationResult(False, False, None, f"falha ao executar chdman: {exc}", verify_command)

        if verify.returncode != 0:
            output = self._output(verify)
            reason = output.splitlines()[-1] if output else f"chdman verify retornou código {verify.returncode}"
            return ChdValidationResult(False, True, None, reason, verify_command)

        expected = (expected_sha1 or "").strip().lower() or None
        if not expected:
            return ChdValidationResult(True, True, None, "chdman verify OK; manifesto não fornece SHA-1 lógico", verify_command)

        info_command = ("info", "-i", str(chd))
        try:
            info = self._run(info_command)
        except subprocess.TimeoutExpired:
            return ChdValidationResult(False, True, None, "chdman info excedeu o timeout", info_command)
        except OSError as exc:
            return ChdValidationResult(False, True, None, f"falha ao executar chdman info: {exc}", info_command)

        if info.returncode != 0:
            output = self._output(info)
            reason = output.splitlines()[-1] if output else f"chdman info retornou código {info.returncode}"
            return ChdValidationResult(False, True, None, reason, info_command)

        output = self._output(info)
        logical_sha1 = self._extract_sha1(output, expected)
        if expected not in {value.lower() for value in _SHA1_RE.findall(output)}:
            return ChdValidationResult(False, True, logical_sha1, f"SHA-1 lógico divergente: esperado={expected}, reportado={logical_sha1 or 'não encontrado'}", info_command)

        return ChdValidationResult(True, True, expected, "chdman verify OK e SHA-1 lógico compatível", info_command)
