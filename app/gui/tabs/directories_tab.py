from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QFileDialog, QMessageBox,
                               QGroupBox, QFormLayout, QScrollArea)
from PySide6.QtCore import Qt, Signal
from pathlib import Path

from app.config.app_config import AppConfig
from app.mame.executable import MameExecutable
from app.core.services.ini_service import IniService


class DirectoriesTab(QWidget):
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = AppConfig()
        self.ini_service = None
        self.mame_exec = None

        self.setup_ui()
        self.refresh_ui_state()

    def setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        # --- GRUPO: Executável MAME ---
        grp_mame = QGroupBox("Executável MAME")
        grp_mame.setToolTip("Selecione o arquivo mame.exe")
        form_mame = QFormLayout()
        grp_mame.setLayout(form_mame)

        self.edit_mame_path = QLineEdit()
        self.edit_mame_path.setReadOnly(True)
        self.edit_mame_path.setPlaceholderText("Nenhum arquivo selecionado")
        btn_browse_mame = QPushButton("Selecionar...")
        btn_browse_mame.clicked.connect(self.select_mame_executable)

        hbox_mame = QHBoxLayout()
        hbox_mame.addWidget(self.edit_mame_path)
        hbox_mame.addWidget(btn_browse_mame)
        form_mame.addRow("Caminho:", hbox_mame)

        self.lbl_version = QLabel("Versão: não detectada")
        self.lbl_version.setToolTip("Versão do MAME obtida através de --version")
        form_mame.addRow("", self.lbl_version)

        btn_reload = QPushButton("Recarregar e detectar")
        btn_reload.clicked.connect(self.detect_mame_version)
        form_mame.addRow("", btn_reload)

        layout.addWidget(grp_mame)

        # --- GRUPO: mame.ini ---
        grp_ini = QGroupBox("Arquivo mame.ini")
        grp_ini.setToolTip("Arquivo de configuração principal do MAME")
        form_ini = QFormLayout()
        grp_ini.setLayout(form_ini)

        self.edit_ini_path = QLineEdit()
        self.edit_ini_path.setReadOnly(True)
        self.edit_ini_path.setPlaceholderText("Nenhum arquivo carregado")
        btn_browse_ini = QPushButton("Selecionar...")
        btn_browse_ini.clicked.connect(self.select_ini_file)

        hbox_ini = QHBoxLayout()
        hbox_ini.addWidget(self.edit_ini_path)
        hbox_ini.addWidget(btn_browse_ini)
        form_ini.addRow("Caminho:", hbox_ini)

        btn_load_ini = QPushButton("Carregar mame.ini")
        btn_load_ini.clicked.connect(self.load_ini)
        form_ini.addRow("", btn_load_ini)

        layout.addWidget(grp_ini)

        # --- GRUPO: Diretórios do MAME ---
        grp_paths = QGroupBox("Diretórios do MAME")
        grp_paths.setToolTip("Configure os caminhos para ROMs, samples, artwork e outros")
        form_paths = QFormLayout()
        grp_paths.setLayout(form_paths)

        # ROM Path (5 campos com botão de seleção)
        self.rom_paths = []
        for i in range(1, 6):
            edit = QLineEdit()
            edit.setPlaceholderText(f"Diretório ROM {i}")
            edit.setToolTip(f"Caminho para o diretório de ROMs #{i}")
            btn_folder = QPushButton("...")
            btn_folder.setFixedWidth(30)
            btn_folder.clicked.connect(self.create_folder_selector(edit, f"Selecionar diretório ROM {i}"))
            hbox = QHBoxLayout()
            hbox.addWidget(edit)
            hbox.addWidget(btn_folder)
            self.rom_paths.append(edit)
            form_paths.addRow(f"ROM {i}:", hbox)

        def make_folder_selector(edit_widget, title):
            def selector():
                dir_path = QFileDialog.getExistingDirectory(self, title, edit_widget.text())
                if dir_path:
                    edit_widget.setText(dir_path)
            return selector

        # Outros diretórios com botão de seleção
        dirs = [
            ("Sample Path:", "samplepath", "samples"),
            ("Artwork Path:", "artpath", "artwork"),
            ("CFG Path:", "cfgpath", "cfg"),
            ("NVRAM Path:", "nvrampath", "nvram"),
            ("State Path:", "statepath", "sta"),
            ("Snapshot Path:", "snappath", "snap"),
            ("Diff Path:", "diffpath", "diff"),
            ("INI Path:", "inipath", "ini")
        ]

        self.dir_edits = {}
        for label, attr, placeholder in dirs:
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            btn_folder = QPushButton("...")
            btn_folder.setFixedWidth(30)
            btn_folder.clicked.connect(make_folder_selector(edit, f"Selecionar {label}"))
            hbox = QHBoxLayout()
            hbox.addWidget(edit)
            hbox.addWidget(btn_folder)
            self.dir_edits[attr] = edit
            form_paths.addRow(label, hbox)

        btn_save_ini = QPushButton("Salvar mame.ini")
        btn_save_ini.clicked.connect(self.save_ini)
        btn_save_ini.setStyleSheet("font-weight: bold; padding: 8px;")
        form_paths.addRow("", btn_save_ini)

        layout.addWidget(grp_paths)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

        self.set_ini_fields_enabled(False)

    def refresh_ui_state(self):
        if self.config.mame_path and self.config.mame_path.exists():
            self.edit_mame_path.setText(str(self.config.mame_path))
            self.detect_mame_version()
        else:
            self.edit_mame_path.clear()
            self.lbl_version.setText("Versão: não detectada")

        if self.config.ini_path and self.config.ini_path.exists():
            self.edit_ini_path.setText(str(self.config.ini_path))
            self.load_ini()
        else:
            if self.config.mame_path and self.config.mame_path.parent:
                default_ini = self.config.mame_path.parent / "mame.ini"
                if default_ini.exists():
                    self.edit_ini_path.setText(str(default_ini))
                    self.config.ini_path = default_ini
                    self.config.save()
                    self.load_ini()

    def load_ini_values(self):
        if not self.ini_service:
            return

        rompath = self.ini_service.get_rompath() or ""
        parts = [p.strip() for p in rompath.split(";") if p.strip()]
        for i, edit in enumerate(self.rom_paths):
            if i < len(parts):
                edit.setText(parts[i])
            else:
                edit.clear()

        mapping = {
            'samplepath': self.ini_service.get_samplepath,
            'artpath': self.ini_service.get_artpath,
            'cfgpath': self.ini_service.get_cfgpath,
            'nvrampath': self.ini_service.get_nvrampath,
            'statepath': self.ini_service.get_statepath,
            'snappath': self.ini_service.get_snappath,
            'diffpath': self.ini_service.get_diffpath,
            'inipath': self.ini_service.get_inipath
        }
        for attr, getter in mapping.items():
            if attr in self.dir_edits:
                self.dir_edits[attr].setText(getter() or "")

        self.set_ini_fields_enabled(True)

    def select_mame_executable(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar executável MAME", "",
            "Executáveis (*.exe);;Todos os arquivos (*)"
        )
        if file_path:
            path = Path(file_path)
            self.config.mame_path = path
            self.config.save()
            self.edit_mame_path.setText(str(path))
            self.detect_mame_version()
            default_ini = path.parent / "mame.ini"
            if default_ini.exists():
                self.edit_ini_path.setText(str(default_ini))
                self.config.ini_path = default_ini
                self.config.save()
                self.load_ini()
            self.settings_changed.emit()

    def detect_mame_version(self):
        if not self.config.mame_path or not self.config.mame_path.exists():
            self.lbl_version.setText("Versão: arquivo não encontrado")
            return
        try:
            self.mame_exec = MameExecutable(self.config.mame_path)
            version = self.mame_exec.version
            self.lbl_version.setText(f"Versão: {version}")
            QMessageBox.information(self, "Sucesso", f"Versão do MAME detectada: {version}")
        except Exception as e:
            self.lbl_version.setText("Versão: erro na detecção")
            QMessageBox.critical(self, "Erro", f"Falha ao detectar versão:\n{str(e)}\n\nVerifique o arquivo mame_executable.log para mais detalhes.")

    def select_ini_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar mame.ini", "",
            "Arquivos INI (*.ini);;Todos os arquivos (*)"
        )
        if file_path:
            self.edit_ini_path.setText(file_path)
            self.config.ini_path = Path(file_path)
            self.config.save()
            self.load_ini()

    def load_ini(self):
        path = Path(self.edit_ini_path.text())
        if not path.exists():
            QMessageBox.warning(self, "Erro", "Arquivo mame.ini não encontrado.")
            return
        try:
            self.ini_service = IniService(path)
            self.load_ini_values()
            QMessageBox.information(self, "Sucesso", "mame.ini carregado com sucesso.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao carregar mame.ini:\n{str(e)}")

    def save_ini(self):
        """
        Salva somente as configurações alteradas pelo usuário.
        """

        if not self.ini_service:
            QMessageBox.warning(
                self,
                "Erro",
                "Nenhum mame.ini carregado."
            )
            return

        try:

            rom_paths = [
                edit.text().strip()
                for edit in self.rom_paths
                if edit.text().strip()
            ]

            self.ini_service.set(
                "rompath",
                self.ini_service.join_paths(
                    rom_paths
                )
            )

            fields = {
                "samplepath": self.dir_edits["samplepath"].text(),
                "artpath": self.dir_edits["artpath"].text(),
                "cfg_directory": self.dir_edits["cfgpath"].text(),
                "nvram_directory": self.dir_edits["nvrampath"].text(),
                "state_directory": self.dir_edits["statepath"].text(),
                "snapshot_directory": self.dir_edits["snappath"].text(),
                "diff_directory": self.dir_edits["diffpath"].text(),
                "inipath": self.dir_edits["inipath"].text(),
            }

            for key, value in fields.items():

                self.ini_service.set(
                    key,
                    value.strip()
                )

            self.ini_service.save()

            QMessageBox.information(
                self,
                "Sucesso",
                "mame.ini salvo com sucesso."
            )

            self.settings_changed.emit()

        except PermissionError:

            QMessageBox.critical(
                self,
                "Erro",
                "Permissão negada para salvar o mame.ini."
            )

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Erro",
                f"Falha ao salvar mame.ini:\n{exc}"
            )

    def set_ini_fields_enabled(self, enabled: bool):
        for edit in self.rom_paths:
            edit.setEnabled(enabled)
        for edit in self.dir_edits.values():
            edit.setEnabled(enabled)

    def create_folder_selector(self, edit_widget, title):
        def selector():
            dir_path = QFileDialog.getExistingDirectory(self, title, edit_widget.text())
            if dir_path:
                edit_widget.setText(dir_path)
        return selector