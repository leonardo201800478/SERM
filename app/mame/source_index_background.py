"""Execução assíncrona da indexação de fontes alternativas de ROM.

A indexação de todos os ZIPs não pertence ao caminho crítico do scan. Este
módulo fornece um worker em background para atualizar o índice persistente
enquanto o scanner continua verificando as machines selecionadas.
"""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Iterable

from app.mame.persistent_rom_scanner import PersistentRomScanner

logger = logging.getLogger(__name__)


class BackgroundRomSourceIndexer:
    """Executa a indexação alternativa em segundo plano."""

    def __init__(
        self,
        rom_paths: Iterable[str | Path],
        *,
        index_path: str | Path | None = None,
    ) -> None:
        self.scanner = PersistentRomScanner(
            rom_paths,
            index_path=index_path,
            enable_alternate_search=False,
            include_chds=False,
        )
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rom-index")
        self._future: Future[int] | None = None

    @property
    def running(self) -> bool:
        """Indica se uma atualização do índice está em execução."""
        return self._future is not None and not self._future.done()

    def start(self, *, force: bool = False, callback: Callable[[int], None] | None = None) -> Future[int]:
        """Inicia a atualização sem bloquear o scan.

        O callback é executado na thread do indexador quando a operação
        termina. Ele recebe a quantidade total de membros presentes no índice.
        """
        if self.running:
            return self._future  # type: ignore[return-value]

        def work() -> int:
            try:
                total = self.scanner.build_archive_index(force=force)
                if callback is not None:
                    callback(total)
                return total
            except Exception:
                logger.exception("Falha atualizando índice de fontes ROM em background.")
                raise

        self._future = self._executor.submit(work)
        return self._future

    def close(self, *, wait: bool = False) -> None:
        """Encerra o worker do indexador."""
        self._executor.shutdown(wait=wait, cancel_futures=True)
