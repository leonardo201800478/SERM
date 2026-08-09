from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox
from PySide6.QtCore import Qt, QTimer
from app.config.app_config import AppConfig
from app.mame.executable import MameExecutable

class HomeTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = AppConfig()
        self.mame_exec = None

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.label_title = QLabel("MAME Set Builder")
        self.label_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label_title)

        self.label_version = QLabel("Versão do programa: 1.0.0")
        layout.addWidget(self.label_version)

        self.label_mame = QLabel("MAME não detectado")
        layout.addWidget(self.label_mame)

        self.btn_official = QPushButton("Site oficial do MAME")
        self.btn_official.clicked.connect(self.open_official_site)
        layout.addWidget(self.btn_official)

        self.refresh_status()

    def refresh_status(self):
        if self.config.mame_path and self.config.mame_path.exists():
            try:
                self.mame_exec = MameExecutable(self.config.mame_path)
                version = self.mame_exec.version
                self.label_mame.setText(f"MAME detectado: {self.config.mame_path}\nVersão: {version}")
            except Exception as e:
                self.label_mame.setText(f"Erro ao detectar MAME: {e}")
        else:
            self.label_mame.setText("MAME não configurado. Acesse a aba Diretórios para selecionar.")

    def open_official_site(self):
        import webbrowser
        webbrowser.open("https://www.mamedev.org/")