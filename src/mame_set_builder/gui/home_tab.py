"""
Aba Home – exibe versão do MAME e link para download.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QGroupBox
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices

class HomeTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Título
        title = QLabel("MAME Set Builder")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # Grupo de versão
        group = QGroupBox("Versão do MAME")
        vbox = QVBoxLayout(group)

        self.version_label = QLabel("Versão: não detectada")
        vbox.addWidget(self.version_label)

        download_btn = QPushButton("Baixar MAME (site oficial)")
        download_btn.clicked.connect(self._open_download)
        vbox.addWidget(download_btn)

        self.update_label = QLabel("")
        self.update_label.setStyleSheet("color: orange;")
        vbox.addWidget(self.update_label)

        layout.addWidget(group)

        # Botão para carregar configurações
        load_btn = QPushButton("Carregar configurações salvas")
        load_btn.clicked.connect(self._load_config)
        layout.addWidget(load_btn)

        layout.addStretch()

    def _open_download(self):
        QDesktopServices.openUrl(QUrl("https://www.mamedev.org/release.html"))

    def _load_config(self):
        from .settings import Settings
        config = Settings.load()
        version = config.get("mame_version", "")
        if version:
            self.set_version(version)
        else:
            self.version_label.setText("Versão: não detectada. Configure o executável na aba Configuração.")
            self.update_label.setText("")

    def set_version(self, version: str):
        self.version_label.setText(f"Versão: {version}")
        self.update_label.setText("Verifique no site oficial se há uma versão mais recente.")