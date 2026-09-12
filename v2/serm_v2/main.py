"""SERM V2 application entry point."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow
from .gui.retro_arcade_theme import apply_retro_arcade_theme
from .gui.startup_splash import StartupSplash
from .gui.theme import normalize_log_widgets, refine_dashboard
from .gui.ui_micro_refinement import refine_arcade_catalog_numbers
from .gui.ui_preferences import UiPreferences, apply_user_theme
from .gui.ui_refinement import apply_ui_refinement
from .gui.home_dashboard_refinement import refine_home_dashboard
from .gui.home_progress_refinement import refine_home_progress
from .gui.home_space_refinement import compact_home_space
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
    layout_stats = apply_ui_refinement(window)
    compact_home_space(window.home_section)
    refine_home_dashboard(window.home_section)
    refine_home_progress(window.home_section)
    refine_arcade_catalog_numbers(window.mame_studio_page.catalog_page)
    logger.info(
        "[SERM][UI] modo=%s | idioma=%s | fonte=%s | consoles=%d | painéis=%d | títulos=%d | seções=%d | splitters_arcade=%s | splitter_retroarch=%s",
        UiPreferences.theme(), UiPreferences.language(), font_family, log_count, ui_stats["panels"], ui_stats["titles"], ui_stats["sections"], layout_stats["arcade"], layout_stats["retroarch"],
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
