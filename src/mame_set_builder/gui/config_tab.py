"""
Aba Configuração – com seletor manual do mame.ini e parser robusto.
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QPushButton, QFileDialog, QMessageBox, QScrollArea
)
from .settings import Settings
from .mame_ini_parser import MameIniParser
from .widgets import FileSelector, PathListEditor
from ..mame.executable import MAMEExecutable
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ConfigTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.config = Settings.load()
        self._setup_ui()
        self._load_from_config()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        vbox = QVBoxLayout(content)

        # --- Executável ---
        group_exe = QGroupBox("Executável do MAME")
        hbox_exe = QHBoxLayout(group_exe)
        self.exe_selector = FileSelector(
            placeholder="Selecione o executável do MAME (mame.exe, mame64.exe, etc.)",
            file_mode=True
        )
        hbox_exe.addWidget(self.exe_selector, 1)
        detect_btn = QPushButton("Detectar Versão")
        detect_btn.clicked.connect(self._detect_version)
        hbox_exe.addWidget(detect_btn)
        vbox.addWidget(group_exe)

        # --- mame.ini (seletor manual) ---
        group_ini = QGroupBox("Arquivo mame.ini")
        hbox_ini = QHBoxLayout(group_ini)
        self.ini_selector = FileSelector(
            placeholder="Selecione o arquivo mame.ini (opcional)",
            file_mode=True
        )
        hbox_ini.addWidget(self.ini_selector, 1)
        load_ini_btn = QPushButton("Carregar do mame.ini")
        load_ini_btn.clicked.connect(self._load_from_mame_ini)
        hbox_ini.addWidget(load_ini_btn)
        vbox.addWidget(group_ini)

        # --- Diretórios ---
        group_dirs = QGroupBox("Diretórios do MAME")
        dirs_layout = QVBoxLayout(group_dirs)

        # ROMs (múltiplas)
        rom_group = QGroupBox("Pastas de ROMs (até 5)")
        rom_layout = QVBoxLayout(rom_group)
        self.rom_editor = PathListEditor(max_items=5, placeholder="Adicionar pasta de ROMs")
        rom_layout.addWidget(self.rom_editor)
        dirs_layout.addWidget(rom_group)

        # Samples
        self.samples_selector = FileSelector(placeholder="Pasta de samples", file_mode=False)
        dirs_layout.addWidget(QLabel("Samples:"))
        dirs_layout.addWidget(self.samples_selector)

        # Artwork
        self.artwork_selector = FileSelector(placeholder="Pasta de artwork", file_mode=False)
        dirs_layout.addWidget(QLabel("Artwork:"))
        dirs_layout.addWidget(self.artwork_selector)

        # Software
        self.software_selector = FileSelector(placeholder="Pasta de software", file_mode=False)
        dirs_layout.addWidget(QLabel("Software:"))
        dirs_layout.addWidget(self.software_selector)

        # Fullset (origem)
        self.fullset_selector = FileSelector(placeholder="Pasta do FULLSET (origem)", file_mode=False)
        dirs_layout.addWidget(QLabel("Fullset (origem):"))
        dirs_layout.addWidget(self.fullset_selector)

        # Folders (ini)
        self.folders_selector = FileSelector(placeholder="Pasta 'folders' ou 'ini' do MAME", file_mode=False)
        dirs_layout.addWidget(QLabel("Folders (ini):"))
        dirs_layout.addWidget(self.folders_selector)

        vbox.addWidget(group_dirs)

        # --- Botões ---
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Salvar Configurações")
        save_btn.clicked.connect(self._save_config)
        btn_layout.addWidget(save_btn)
        vbox.addLayout(btn_layout)

        vbox.addStretch()

    def _detect_version(self):
        exe_path = self.exe_selector.text().strip()
        if not exe_path:
            QMessageBox.warning(self, "Aviso", "Selecione o executável primeiro.")
            return
        exe_file = Path(exe_path)
        if not exe_file.exists():
            QMessageBox.warning(self, "Erro", "Arquivo não encontrado.")
            return
        try:
            mame = MAMEExecutable(exe_file)
            version = mame.get_version()
            self.config["mame_executable"] = exe_path
            self.config["mame_version"] = version
            QMessageBox.information(self, "Versão detectada", f"Versão do MAME: {version}")
            if hasattr(self.main_window, 'home_tab'):
                self.main_window.home_tab.set_version(version)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao detectar versão: {e}")

    def _load_from_mame_ini(self):
        """Carrega configurações do mame.ini selecionado ou tenta localizar automaticamente."""
        ini_path = self.ini_selector.text().strip()

        # Se o campo estiver vazio, tenta localizar automaticamente a partir do executável
        if not ini_path:
            exe_path = self.exe_selector.text().strip()
            if exe_path:
                found = MameIniParser.find_ini(Path(exe_path))
                if found.exists():
                    ini_path = str(found)
                else:
                    QMessageBox.warning(self, "Aviso", 
                        "Arquivo mame.ini não encontrado automaticamente.\n"
                        "Selecione-o manualmente ou configure o executável.")
                    return
            else:
                # Pergunta ao usuário
                file_path, _ = QFileDialog.getOpenFileName(
                    self, "Selecionar arquivo mame.ini", "",
                    "Arquivos INI (*.ini);;Todos os arquivos (*.*)"
                )
                if file_path:
                    ini_path = file_path
                    self.ini_selector.setText(ini_path)
                else:
                    return

        if not ini_path or not Path(ini_path).exists():
            QMessageBox.warning(self, "Erro", "Arquivo mame.ini não encontrado.")
            return

        ini_file = Path(ini_path)
        config = MameIniParser.parse(ini_file)

        logger.info(f"📊 Configurações parseadas: {len(config)}")
        logger.info(f"📊 Chaves encontradas: {list(config.keys())}")

        if not config:
            # Tenta ler novamente com codificação forçada (Windows-1252)
            try:
                with open(ini_file, 'r', encoding='windows-1252') as f:
                    lines = f.readlines()
                # Parse manual com fallback
                fallback_config = {}
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith(';'):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        fallback_config[key.strip()] = value.strip().strip('"')
                if fallback_config:
                    config = fallback_config
            except:
                pass

        if not config:
            QMessageBox.warning(self, "Aviso", 
                "Não foi possível ler o mame.ini.\n"
                "Verifique se o arquivo está no formato correto.\n"
                f"Caminho: {ini_file}")
            return

        # Preencher campos
        roms = config.get("rompath", "").split(';')
        self.rom_editor.setPaths([p.strip() for p in roms if p.strip()])
        self.samples_selector.setText(config.get("samplepath", ""))
        self.artwork_selector.setText(config.get("artpath", ""))
        self.software_selector.setText(config.get("swpath", "").split(';')[0] if config.get("swpath") else "")
        self.folders_selector.setText(config.get("inipath", ""))

        # Se o executável não estiver definido, tenta extrair da variável homepath
        if not self.exe_selector.text().strip():
            home = config.get("homepath", "")
            if home and home != ".":
                possible_exe = Path(home) / "mame.exe"
                if possible_exe.exists():
                    self.exe_selector.setText(str(possible_exe))
                else:
                    possible_exe = Path(home) / "mame64.exe"
                    if possible_exe.exists():
                        self.exe_selector.setText(str(possible_exe))

        QMessageBox.information(self, "Sucesso", "Configurações carregadas do mame.ini.")
        # Atualiza a versão se possível
        self._detect_version()

    def _load_from_config(self):
        config = self.config
        self.exe_selector.setText(config.get("mame_executable", ""))
        self.rom_editor.setPaths(config.get("rom_paths", []))
        self.samples_selector.setText(config.get("sample_path", ""))
        self.artwork_selector.setText(config.get("artwork_path", ""))
        self.software_selector.setText(config.get("software_path", ""))
        self.fullset_selector.setText(config.get("fullset_path", ""))
        self.folders_selector.setText(config.get("folders_path", ""))
        version = config.get("mame_version", "")
        if version and hasattr(self.main_window, 'home_tab'):
            self.main_window.home_tab.set_version(version)

    def _save_config(self):
        config = {
            "mame_executable": self.exe_selector.text().strip(),
            "mame_version": self.config.get("mame_version", ""),
            "rom_paths": self.rom_editor.getPaths(),
            "sample_path": self.samples_selector.text().strip(),
            "artwork_path": self.artwork_selector.text().strip(),
            "software_path": self.software_selector.text().strip(),
            "fullset_path": self.fullset_selector.text().strip(),
            "folders_path": self.folders_selector.text().strip(),
        }
        Settings.save(config)
        self.config = config
        QMessageBox.information(self, "Sucesso", "Configurações salvas.")
        version = config.get("mame_version", "")
        if version and hasattr(self.main_window, 'home_tab'):
            self.main_window.home_tab.set_version(version)

    def get_config(self) -> dict:
        return self.config