import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.gui.main_window import MainWindow
from app.gui.startup_splash import StartupSplash

sys.path.insert(0, str(Path(__file__).parent.parent))


# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------
LOG_DIR = Path.home() / ".mame-set-builder" / "logs"
LOG_FILE = LOG_DIR / "mame-set-builder.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(
            LOG_FILE,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def main():
    """Inicializa a aplicação mantendo a MainWindow oculta até concluir a carga."""
    logger.info("=" * 60)
    logger.info("Iniciando MAME Set Builder...")
    logger.info("Python: %s", sys.version)
    logger.info("Platform: %s", sys.platform)
    logger.info("Log file: %s", LOG_FILE)

    app = QApplication(sys.argv)
    splash = StartupSplash.startup()

    window = None
    exit_code = 1
    try:
        splash.set_phase("Preparando banco de dados…", "Abrindo e validando o SQLite e suas migrações.")
        window = MainWindow()

        # A MainWindow executa somente as inicializações necessárias para
        # construir a interface. Dados pesados devem ser carregados pela aba
        # correspondente quando ela se torna ativa.
        splash.set_phase("Inicialização concluída", "Abrindo a interface principal.")
        app.processEvents()

        window.show()
        splash.close()
        splash.deleteLater()
        logger.info("Aplicação iniciada com sucesso.")
        exit_code = app.exec()
    except Exception:
        logger.exception("Falha fatal durante a inicialização da aplicação.")
        splash.set_phase("Falha na inicialização", f"Consulte {LOG_FILE} para obter o diagnóstico.")
        app.processEvents()
        raise
    finally:
        # Quando app.exec() retorna, a MainWindow já recebeu closeEvent ou
        # está sendo finalizada pelo sistema. O splash de encerramento é
        # apresentado antes da saída definitiva do processo.
        if window is not None:
            shutdown = StartupSplash.shutdown()
            shutdown.set_phase("Encerrando aplicação…", "Finalizando workers e liberando recursos.")
            app.processEvents()
            if window.isVisible():
                window.close()
            shutdown.set_phase("Encerramento concluído", "Até a próxima execução.")
            app.processEvents()
            shutdown.close()
            shutdown.deleteLater()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
