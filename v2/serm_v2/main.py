"""SERM V2 application entry point."""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow


def configure_logging() -> None:
    """Configure visible console logging for interactive development."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        force=True,
    )


def main() -> int:
    """Create the Qt application and display the V2 main window."""
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("[SERM][BOOT] iniciando SERM V2")
    app = QApplication(sys.argv)
    app.setApplicationName("SERM")
    app.setApplicationVersion("2.0.0-dev")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
