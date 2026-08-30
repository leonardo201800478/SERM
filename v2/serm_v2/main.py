"""SERM V2 application entry point."""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow
from .gui.startup_splash import StartupSplash


def configure_logging() -> None:
    """Configure logging for interactive development and diagnostics."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        force=True,
    )


def main() -> int:
    """Start SERM V2 with the 16:9 splash screen."""
    configure_logging()
    logger = logging.getLogger(__name__)
    app = QApplication(sys.argv)
    app.setApplicationName("SERM")
    app.setApplicationVersion("2.0.0-dev")

    splash = StartupSplash.startup()
    splash.set_phase("Inicializando SERM V2", "Carregando interface e serviços...")
    window = MainWindow()
    splash.set_phase("Verificando emuladores", "Detectando executáveis e versões instaladas...")
    window.home_section.refresh()
    splash.set_phase("Pronto", "Abrindo a interface principal...")
    window.show()
    splash.finish(window)
    logger.info("[SERM][BOOT] SERM V2 iniciado")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
