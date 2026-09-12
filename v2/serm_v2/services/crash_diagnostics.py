"""Persistent diagnostics for SERM V2 startup and native crashes."""

from __future__ import annotations

import faulthandler
import logging
import os
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parents[2] / "data" / "logs"
_APP_LOG = _LOG_DIR / "serm.log"
_CRASH_LOG = _LOG_DIR / "crash.log"
_INPUT_LOG = _LOG_DIR / "input_diagnostics.log"


def log_dir() -> Path:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    return _LOG_DIR


def configure_logging() -> None:
    """Configure console + persistent application logging."""
    log_dir()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    for handler in list(root.handlers):
        if isinstance(handler, logging.FileHandler):
            root.removeHandler(handler)
            handler.close()
    file_handler = logging.FileHandler(_APP_LOG, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    if not any(isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler) for handler in root.handlers):
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)

    crash_handler = logging.FileHandler(_CRASH_LOG, encoding="utf-8")
    crash_handler.setFormatter(formatter)
    crash_logger = logging.getLogger("SERM.CRASH")
    crash_logger.handlers.clear()
    crash_logger.propagate = False
    crash_logger.addHandler(crash_handler)
    crash_logger.setLevel(logging.ERROR)

    input_handler = logging.FileHandler(_INPUT_LOG, encoding="utf-8")
    input_handler.setFormatter(formatter)
    input_logger = logging.getLogger("SERM.INPUT")
    input_logger.handlers.clear()
    input_logger.propagate = True
    input_logger.addHandler(input_handler)
    input_logger.setLevel(logging.INFO)

    try:
        crash_file = open(_CRASH_LOG, "a", encoding="utf-8", buffering=1)
        faulthandler.enable(file=crash_file, all_threads=True)
    except (OSError, RuntimeError):
        pass

    sys.excepthook = _uncaught_exception
    threading.excepthook = _thread_exception
    logging.getLogger(__name__).info("[DIAG] logs=%s", _LOG_DIR)


def _uncaught_exception(exc_type, exc_value, exc_traceback) -> None:
    logger = logging.getLogger("SERM.CRASH")
    logger.critical("Exceção não tratada", exc_info=(exc_type, exc_value, exc_traceback))
    traceback.print_exception(exc_type, exc_value, exc_traceback)


def _thread_exception(args) -> None:
    logging.getLogger("SERM.CRASH").critical(
        "Exceção não tratada na thread %s", getattr(args.thread, "name", "unknown"),
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


def diagnostic_paths() -> tuple[Path, Path, Path]:
    log_dir()
    return _APP_LOG, _CRASH_LOG, _INPUT_LOG


__all__ = ["configure_logging", "diagnostic_paths", "log_dir"]
