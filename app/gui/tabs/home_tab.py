from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QFrame, QGridLayout)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
import webbrowser

from app.config.app_config import AppConfig
from app.mame.executable import MameExecutable
from app.core.services.emulator_version_service import EmulatorVersionService


class HomeTab(QWidget):
    """Home com estado dos emuladores detectado sem diálogos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = AppConfig()
        self.mame_exec = None
        self.version_service = EmulatorVersionService()

        self.setup_ui()
        self.refresh_status()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title = QLabel("MAME Set Builder")
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(28)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)

        subtitle = QLabel("Gerenciamento, filtragem e construção de conjuntos de ROMs")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle_font = QFont()
        subtitle_font.setPointSize(12)
        subtitle.setFont(subtitle_font)
        main_layout.addWidget(subtitle)
        main_layout.addSpacing(20)

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

        self.emulator_labels: dict[str, QLabel] = {}
        emulator_names = {
            "flycast": "Flycast",
            "supermodel": "Supermodel",
            "fbneo": "FBNeo",
        }
        row = 4
        for key, display_name in emulator_names.items():
            label = QLabel(f"{display_name}: não configurado")
            label.setWordWrap(True)
            info_layout.addWidget(label, row, 0, 1, 2)
            self.emulator_labels[key] = label
            row += 1

        main_layout.addWidget(info_frame)
        main_layout.addSpacing(10)

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
            QPushButton:hover { background-color: #45a049; }
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
            QPushButton:hover { background-color: #1976D2; }
        """)
        btn_layout.addWidget(btn_refresh)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)
        main_layout.addStretch()

        footer = QLabel("O software não distribui ROMs. Trabalha apenas com arquivos que o usuário já possui.")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color: #888; font-size: 10px;")
        main_layout.addWidget(footer)

    def refresh_status(self):
        """Atualiza o estado dos quatro emuladores sem abrir qualquer diálogo."""
        self.config.load()
        result = self.version_service.detect_many({
            "mame": self.config.mame_path,
            "flycast": self.config.flycast_path,
            "supermodel": self.config.supermodel_path,
            "fbneo": self.config.fbneo_path,
        })

        mame = result["mame"]
        if mame.available:
            self.mame_exec = MameExecutable(self.config.mame_path)
            self.lbl_mame_status.setText("✅ MAME detectado")
            self.lbl_mame_status.setStyleSheet("color: green; font-weight: bold;")
            self.lbl_mame_path.setText(f"📁 Caminho: {mame.executable}")
            self.lbl_mame_version.setText(f"📌 Versão: {mame.version}")
        elif self.config.mame_path:
            self.lbl_mame_status.setText("⚠️ MAME indisponível")
            self.lbl_mame_status.setStyleSheet("color: orange; font-weight: bold;")
            self.lbl_mame_path.setText(f"📁 Caminho: {mame.executable}")
            self.lbl_mame_version.setText(f"ℹ️ {mame.error or 'versão não detectada'}")
        else:
            self.lbl_mame_status.setText("❌ MAME não configurado")
            self.lbl_mame_status.setStyleSheet("color: red; font-weight: bold;")
            self.lbl_mame_path.setText("Acesse a aba Diretórios para selecionar o executável MAME.")
            self.lbl_mame_version.setText("")

        for key, label in self.emulator_labels.items():
            item = result[key]
            display = {"flycast": "Flycast", "supermodel": "Supermodel", "fbneo": "FBNeo"}[key]
            if item.available:
                label.setText(f"✅ {display}: {item.version}  |  📁 {item.executable}")
                label.setStyleSheet("color: green; font-weight: bold;")
            elif item.executable:
                label.setText(f"⚠️ {display}: indisponível | 📁 {item.executable}")
                label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                label.setText(f"❌ {display}: não configurado")
                label.setStyleSheet("color: #888;")

    def open_official_site(self):
        webbrowser.open("https://www.mamedev.org/")
