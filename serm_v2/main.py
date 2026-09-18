"""SERM V2 application entry point."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow
from .gui.retro_arcade_theme import apply_retro_arcade_theme
from .gui.startup_splash import StartupSplash
from .gui.theme import normalize_log_widgets, refine_dashboard
from .gui.ui_preferences import UiPreferences, apply_user_theme
from .services.crash_diagnostics import configure_logging


def main() -> int:
    """Start SERM V2 with persistent diagnostics enabled before Qt startup."""
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("[SERM][BOOT] iniciando processo | pid=%s | python=%s", __import__("os").getpid(), sys.version.replace("\n", " "))
    app = QApplication(sys.argv)
    app.setApplicationName("SERM")
    app.setApplicationVersion("2.0.0-dev")
    font_family = apply_retro_arcade_theme(app)
    apply_user_theme(app, UiPreferences.theme())
    splash = StartupSplash.startup()
    splash.set_phase("Inicializando SERM V2", "Carregando interface e serviços...")
    window = MainWindow()
    log_count = normalize_log_widgets(window)
    ui_stats = refine_dashboard(window)
    logger.info(
        "[SERM][UI] modo=%s | idioma=%s | fonte=%s | consoles=%d | painéis=%d | títulos=%d | seções=%d",
        UiPreferences.theme(), UiPreferences.language(), font_family, log_count, ui_stats["panels"], ui_stats["titles"], ui_stats["sections"],
    )
    splash.set_phase("Verificando emuladores", "Detectando executáveis e versões instaladas...")
    window.home_section.refresh()
    splash.set_phase("Pronto", "Abrindo a interface principal...")
    window.show()
    window.input_connection_monitor.start()
    splash.finish(window)
    logger.info("[SERM][BOOT] SERM V2 iniciado")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
