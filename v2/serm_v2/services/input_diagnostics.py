"""Diagnóstico robusto do subsistema de entrada.

Registra cada etapa da descoberta em um arquivo dedicado. O objetivo é
localizar falhas em bindings nativos sem depender apenas do stdout da GUI.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path


class InputDiagnostics:
    """Configura logging dedicado e hooks de falha para o subsistema INPUT."""

    LOG_FILE = Path("data/logs/input_diagnostics.log")

    @classmethod
    def logger(cls) -> logging.Logger:
        """Retorna o logger dedicado ao diagnóstico de controles."""
        logger = logging.getLogger("serm.input")
        if not logger.handlers:
            cls.configure(logger)
        return logger

    @classmethod
    def configure(cls, logger: logging.Logger | None = None) -> logging.Logger:
        """Inicializa o arquivo de diagnóstico de forma idempotente."""
        logger = logger or logging.getLogger("serm.input")
        logger.setLevel(logging.DEBUG)
        logger.propagate = True
        cls.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        resolved = cls.LOG_FILE.resolve()
        if not any(isinstance(handler, logging.FileHandler) and Path(handler.baseFilename).resolve() == resolved for handler in logger.handlers):
            handler = logging.FileHandler(resolved, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
            logger.addHandler(handler)
        return logger

    @classmethod
    def install_crash_hooks(cls) -> None:
        """Registra exceções não tratadas e falhas de threads Python."""
        logger = cls.logger()

        def excepthook(exc_type, exc_value, exc_traceback) -> None:
            logger.critical(
                "[CRASH] exceção não tratada: %s: %s\n%s",
                exc_type.__name__, exc_value,
                "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
            )
            sys.__excepthook__(exc_type, exc_value, exc_traceback)

        def thread_hook(args: threading.ExceptHookArgs) -> None:
            logger.critical(
                "[CRASH][THREAD] thread=%s exceção=%s: %s\n%s",
                args.thread.name if args.thread else "unknown",
                args.exc_type.__name__, args.exc_value,
                "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)),
            )

        sys.excepthook = excepthook
        threading.excepthook = thread_hook
        logger.info(
            "[BOOT] input diagnostics installed | pid=%s | python=%s | platform=%s | utc=%s",
            os.getpid(), sys.version.split()[0], sys.platform,
            datetime.now(timezone.utc).isoformat(),
        )


__all__ = ["InputDiagnostics"]
