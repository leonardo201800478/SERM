from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QFrame, QGridLayout)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
import webbrowser

from app.config.app_config import AppConfig
from app.mame.executable import MameExecutable

class HomeTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = AppConfig()
        self.mame_exec = None

        self.setup_ui()
        self.refresh_status()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Título
        title = QLabel("MAME Set Builder")
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(28)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)

        # Subtítulo
        subtitle = QLabel("Gerenciamento, filtragem e construção de conjuntos de ROMs")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle_font = QFont()
        subtitle_font.setPointSize(12)
        subtitle.setFont(subtitle_font)
        main_layout.addWidget(subtitle)

        main_layout.addSpacing(20)

        # Card de informações do MAME
        info_frame = QFrame()
        info_frame.setFrameShape(QFrame.Box)
        info_frame.setFrameShadow(QFrame.Raised)
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #000000;
                border: 1px solid #c0c0c0;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        info_layout = QGridLayout(info_frame)
        info_layout.setVerticalSpacing(8)
        info_layout.setHorizontalSpacing(20)

        # Labels de informações
        self.lbl_version_programa = QLabel("Versão do programa: 1.0.0")
        self.lbl_version_programa.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.lbl_version_programa, 0, 0, 1, 2)

        self.lbl_mame_status = QLabel("MAME não configurado")
        self.lbl_mame_status.setStyleSheet("color: #888;")
        info_layout.addWidget(self.lbl_mame_status, 1, 0, 1, 2)

        self.lbl_mame_path = QLabel("")
        self.lbl_mame_path.setWordWrap(True)
        info_layout.addWidget(self.lbl_mame_path, 2, 0, 1, 2)

        self.lbl_mame_version = QLabel("")
        self.lbl_mame_version.setWordWrap(True)
        info_layout.addWidget(self.lbl_mame_version, 3, 0, 1, 2)

        main_layout.addWidget(info_frame)

        main_layout.addSpacing(10)

        # Botões de ação
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        btn_official = QPushButton("🌐 Site oficial do MAME")
        btn_official.clicked.connect(self.open_official_site)
        btn_official.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        btn_layout.addWidget(btn_official)

        btn_refresh = QPushButton("🔄 Atualizar")
        btn_refresh.clicked.connect(self.refresh_status)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        btn_layout.addWidget(btn_refresh)

        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        main_layout.addStretch()

        # Rodapé
        footer = QLabel("O software não distribui ROMs. Trabalha apenas com arquivos que o usuário já possui.")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color: #888; font-size: 10px;")
        main_layout.addWidget(footer)

    def refresh_status(self):
        """Atualiza as informações do MAME na home."""
        if self.config.mame_path and self.config.mame_path.exists():
            try:
                self.mame_exec = MameExecutable(self.config.mame_path)
                version = self.mame_exec.version
                self.lbl_mame_status.setText("✅ MAME detectado")
                self.lbl_mame_status.setStyleSheet("color: green; font-weight: bold;")
                self.lbl_mame_path.setText(f"📁 Caminho: {self.config.mame_path}")
                self.lbl_mame_version.setText(f"📌 Versão: {version}")
            except Exception as e:
                self.lbl_mame_status.setText("⚠️ Erro ao detectar MAME")
                self.lbl_mame_status.setStyleSheet("color: orange; font-weight: bold;")
                self.lbl_mame_path.setText(f"📁 Caminho: {self.config.mame_path}")
                self.lbl_mame_version.setText(f"❌ Erro: {e}")
        else:
            self.lbl_mame_status.setText("❌ MAME não configurado")
            self.lbl_mame_status.setStyleSheet("color: red; font-weight: bold;")
            self.lbl_mame_path.setText("Acesse a aba Diretórios para selecionar o executável MAME.")
            self.lbl_mame_version.setText("")

    def open_official_site(self):
        webbrowser.open("https://www.mamedev.org/")