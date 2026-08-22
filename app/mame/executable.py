"""Integração segura e silenciosa com o executável do MAME."""
from __future__ import annotations

import logging
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, TextIO

logger = logging.getLogger(__name__)


class MameExecutable:
    """Representa o executável do MAME e suas operações de processo.

    A detecção de versão é deliberadamente silenciosa: falhas de detecção
    retornam ``None`` e não provocam diálogos, exceções ou logs de warning.
    """

    _VERSION_TIMEOUT = 5
    _LISTXML_TIMEOUT = 120

    def __init__(self, path: Path | str):
        self.path = Path(path).expanduser()
        self._version: Optional[str] = None
        self._version_checked = False

    @property
    def version(self) -> Optional[str]:
        """Retorna a versão detectada, consultando o executável apenas uma vez."""
        if not self._version_checked:
            self._detect_version()
        return self._version

    def _detect_version(self) -> None:
        """Detecta ``MAME -version`` sem abrir console ou gerar alertas."""
        self._version_checked = True

        if not self.path.is_file():
            return

        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(
                [str(self.path), "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._VERSION_TIMEOUT,
                shell=False,
                check=False,
                creationflags=creationflags,
            )
        except (OSError, subprocess.SubprocessError):
            return

        output = "\n".join((result.stdout or "", result.stderr or ""))
        match = re.search(
            r"\b(?:MAME\s+)?([0-9]+(?:\.[0-9]+)+(?:[-+._][0-9A-Za-z.-]+)?)\b",
            output,
            re.IGNORECASE,
        )
        if match:
            self._version = match.group(1)

    def get_listxml(self) -> str:
        """Executa ``mame -listxml`` e retorna o XML completo.

        Para importações grandes, ``stream_listxml`` deve ser preferido para
        evitar materializar o XML inteiro na memória.
        """
        try:
            result = subprocess.run(
                [str(self.path), "-listxml"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._LISTXML_TIMEOUT,
                shell=False,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"Executável MAME não encontrado: {self.path}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Timeout ao executar MAME -listxml.") from exc
        except OSError as exc:
            raise RuntimeError(f"Falha ao executar MAME -listxml: {exc}") from exc

        if result.returncode != 0:
            detail = (result.stderr or "").strip()
            raise RuntimeError(
                f"MAME -listxml terminou com código {result.returncode}"
                + (f": {detail}" if detail else ".")
            )
        return result.stdout

    @contextmanager
    def stream_listxml(self) -> Iterator[TextIO]:
        """Executa ``mame -listxml`` e fornece seu stdout em streaming.

        O processo não abre janela de console no Windows. O stderr é drenado
        antes de ``wait`` para evitar bloqueio caso o MAME produza muita saída.
        """
        process = subprocess.Popen(
            [str(self.path), "-listxml"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        try:
            if process.stdout is None:
                raise RuntimeError("MAME não forneceu stdout para -listxml.")
            yield process.stdout
        finally:
            if process.stdout is not None:
                process.stdout.close()

            stderr_output = process.stderr.read() if process.stderr is not None else ""
            if process.stderr is not None:
                process.stderr.close()

            try:
                returncode = process.wait(timeout=self._LISTXML_TIMEOUT)
            except subprocess.TimeoutExpired as exc:
                process.kill()
                process.wait()
                raise RuntimeError("Timeout ao finalizar MAME -listxml.") from exc

            if returncode != 0:
                detail = stderr_output.strip()
                raise RuntimeError(
                    f"MAME -listxml terminou com código {returncode}"
                    + (f": {detail}" if detail else ".")
                )
