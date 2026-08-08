# tools/build_dataset.py
import sys
import logging
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mame_set_builder.dataset_builder import DatasetBuilder

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python build_dataset.py <caminho_do_mame> <caminho_do_banco.db>")
        sys.exit(1)
    mame_path = Path(sys.argv[1])
    db_path = Path(sys.argv[2])
    builder = DatasetBuilder(mame_path, db_path)
    try:
        builder.build()
    finally:
        builder.close()