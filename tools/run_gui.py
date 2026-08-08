#!/usr/bin/env python
"""
Ponto de entrada para a interface gráfica.
Uso: python tools/run_gui.py <caminho_do_banco.db>
"""

import sys
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from PyQt6.QtWidgets import QApplication
from mame_set_builder.gui.main_window import MainWindow

def main():
    if len(sys.argv) < 2:
        print("Uso: python tools/run_gui.py <caminho_do_banco.db>")
        sys.exit(1)
    
    db_path = Path(sys.argv[1])
    if not db_path.exists():
        print(f"Erro: arquivo {db_path} não encontrado.")
        sys.exit(1)
    
    app = QApplication(sys.argv)
    window = MainWindow(str(db_path))
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()