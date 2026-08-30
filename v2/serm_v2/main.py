"""SERM V2 application entry point."""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow
from .gui.startup_splash import StartupSplash
from .gui.theme import apply_theme, normalize_log_widgets, refine_dashboard
from .gui.ui_refinement import apply_ui_refinement


def configure_logging() -> None:
    """Configure logging for interactive development and diagnostics."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        force=True,
    )


def main() -> int:
    """Start SERM V2 with the refined unified gamer interface."""
    configure_logging()
    logger = logging.getLogger(__name__)
    app = QApplication(sys.argv)
    app.setApplicationName("SERM")
    app.setApplicationVersion("2.0.0-dev")
    apply_theme(app)

    splash = StartupSplash.startup()
    splash.set_phase("Inicializando SERM V2", "Carregando interface e serviços...")
    window = MainWindow()
    log_count = normalize_log_widgets(window)
    ui_stats = refine_dashboard(window)
    layout_stats = apply_ui_refinement(window)
    logger.info(
        "[SERM][UI] tema gamer refinado | consoles=%d | painéis=%d | títulos=%d | seções=%d | "
        "splitters_arcade=%s | splitter_retroarch=%s",
        log_count,
        ui_stats["panels"],
        ui_stats["titles"],
        ui_stats["sections"],
        layout_stats["arcade"],
        layout_stats["retroarch"],
    )
    splash.set_phase("Verificando emuladores", "Detectando executáveis e versões instaladas...")
    window.home_section.refresh()
    splash.set_phase("Pronto", "Abrindo a interface principal...")
    window.show()
    splash.finish(window)
    logger.info("[SERM][BOOT] SERM V2 iniciado")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
