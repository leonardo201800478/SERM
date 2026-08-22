import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication
from app.gui.main_window import MainWindow
from app.gui.design.theme import apply_theme

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
    logger.info("=" * 60)
    logger.info("Iniciando MAME Set Builder...")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Platform: {sys.platform}")

    app = QApplication(sys.argv)
    apply_theme(app)
    window = MainWindow()
    window.show()
    logger.info("Aplicação iniciada com sucesso.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
