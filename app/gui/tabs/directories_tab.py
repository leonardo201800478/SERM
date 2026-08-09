from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QFileDialog, QMessageBox, QGroupBox, QFormLayout)
from PySide6.QtCore import Qt
from app.config.app_config import AppConfig
from app.mame.executable import MameExecutable
from app.mame.ini_parser import MameIniParser
from app.core.services.ini_service import IniService
from pathlib import Path

class DirectoriesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = AppConfig()
        self.ini_service = None

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        # Grupo MAME Executable
        grp_mame = QGroupBox("Executável MAME")
        form_mame = QFormLayout()
        grp_mame.setLayout(form_mame)

        self.edit_mame_path = QLineEdit()
        self.edit_mame_path.setReadOnly(True)
        if self.config.mame_path:
            self.edit_mame_path.setText(str(self.config.mame_path))
        btn_browse = QPushButton("Selecionar...")
        btn_browse.clicked.connect(self.select_mame_executable)

        hbox = QHBoxLayout()
        hbox.addWidget(self.edit_mame_path)
        hbox.addWidget(btn_browse)
        form_mame.addRow("Caminho:", hbox)

        self.lbl_version = QLabel("Versão: não detectada")
        form_mame.addRow("", self.lbl_version)

        btn_reload = QPushButton("Recarregar e detectar")
        btn_reload.clicked.connect(self.detect_mame_version)
        form_mame.addRow("", btn_reload)

        layout.addWidget(grp_mame)

        # Grupo mame.ini
        grp_ini = QGroupBox("Arquivo mame.ini")
        form_ini = QFormLayout()
        grp_ini.setLayout(form_ini)

        self.edit_ini_path = QLineEdit()
        self.edit_ini_path.setReadOnly(True)
        btn_ini_browse = QPushButton("Selecionar...")
        btn_ini_browse.clicked.connect(self.select_ini_file)

        hbox_ini = QHBoxLayout()
        hbox_ini.addWidget(self.edit_ini_path)
        hbox_ini.addWidget(btn_ini_browse)
        form_ini.addRow("Caminho:", hbox_ini)

        btn_load_ini = QPushButton("Carregar mame.ini")
        btn_load_ini.clicked.connect(self.load_ini)
        form_ini.addRow("", btn_load_ini)

        layout.addWidget(grp_ini)

        # Grupo de diretórios (exemplo com rompath)
        grp_paths = QGroupBox("Diretórios do MAME")
        form_paths = QFormLayout()
        grp_paths.setLayout(form_paths)

        self.edit_rompath = QLineEdit()
        self.edit_samplepath = QLineEdit()
        self.edit_artpath = QLineEdit()
        self.edit_cfgpath = QLineEdit()

        form_paths.addRow("ROM Path:", self.edit_rompath)
        form_paths.addRow("Sample Path:", self.edit_samplepath)
        form_paths.addRow("Artwork Path:", self.edit_artpath)
        form_paths.addRow("CFG Path:", self.edit_cfgpath)

        btn_save_ini = QPushButton("Salvar mame.ini")
        btn_save_ini.clicked.connect(self.save_ini)
        form_paths.addRow("", btn_save_ini)

        layout.addWidget(grp_paths)

        # Inicialmente, desabilitar campos até carregar ini
        self.set_ini_fields_enabled(False)

    def select_mame_executable(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Selecionar executável MAME", "",
                                                   "Executáveis (*.exe);;Todos os arquivos (*)")
        if file_path:
            path = Path(file_path)
            self.config.mame_path = path
            self.config.save()
            self.edit_mame_path.setText(str(path))
            self.detect_mame_version()

    def detect_mame_version(self):
        if not self.config.mame_path or not self.config.mame_path.exists():
            QMessageBox.warning(self, "Erro", "Caminho do MAME inválido.")
            return
        try:
            mame = MameExecutable(self.config.mame_path)
            self.lbl_version.setText(f"Versão: {mame.version}")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao detectar versão: {e}")

    def select_ini_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Selecionar mame.ini", "",
                                                   "Arquivos INI (*.ini);;Todos os arquivos (*)")
        if file_path:
            self.edit_ini_path.setText(file_path)
            self.load_ini()

    def load_ini(self):
        path = Path(self.edit_ini_path.text())
        if not path.exists():
            QMessageBox.warning(self, "Erro", "Arquivo mame.ini não encontrado.")
            return
        try:
            self.ini_service = IniService(path)
            self.edit_rompath.setText(self.ini_service.get_rompath() or "")
            self.edit_samplepath.setText(self.ini_service.get_samplepath() or "")
            self.edit_artpath.setText(self.ini_service.get_artpath() or "")
            self.edit_cfgpath.setText(self.ini_service.get_cfgpath() or "")
            self.set_ini_fields_enabled(True)
            QMessageBox.information(self, "Sucesso", "mame.ini carregado com sucesso.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao carregar mame.ini: {e}")

    def save_ini(self):
        if not self.ini_service:
            QMessageBox.warning(self, "Erro", "Nenhum mame.ini carregado.")
            return
        try:
            self.ini_service.set_rompath(self.edit_rompath.text())
            self.ini_service.set_samplepath(self.edit_samplepath.text())
            self.ini_service.set_artpath(self.edit_artpath.text())
            self.ini_service.set_cfgpath(self.edit_cfgpath.text())
            self.ini_service.save()
            QMessageBox.information(self, "Sucesso", "mame.ini salvo com sucesso.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao salvar mame.ini: {e}")

    def set_ini_fields_enabled(self, enabled):
        self.edit_rompath.setEnabled(enabled)
        self.edit_samplepath.setEnabled(enabled)
        self.edit_artpath.setEnabled(enabled)
        self.edit_cfgpath.setEnabled(enabled)