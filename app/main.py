import sys
import logging
import multiprocessing
from pathlib import Path
from PySide6.QtWidgets import QApplication
from app.gui.main_window import MainWindow
from app.core.system import PerformanceManager

sys.path.insert(0, str(Path(__file__).parent.parent))


# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mame-set-builder.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Inicializa o aplicativo e registra o perfil de hardware detectado."""
    multiprocessing.freeze_support()
    logger.info("=" * 60)
    logger.info("Iniciando MAME Set Builder...")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Platform: {sys.platform}")

    performance = PerformanceManager.detect()
    logger.info("Perfil de hardware: %s", performance.describe())
    logger.info("Executor CPU selecionado: %s", performance.choose_cpu_executor())

    app = QApplication(sys.argv)
    # Disponibiliza o scheduler para widgets/serviços sem criar outro perfil.
    app.setProperty("performance_manager", performance)
    window = MainWindow()
    window.show()
    logger.info("Aplicação iniciada com sucesso.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
