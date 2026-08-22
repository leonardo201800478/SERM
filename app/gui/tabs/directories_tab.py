"""
Aba de configuração de diretórios do MAME.

Permite selecionar o executável MAME, carregar/editar o mame.ini
e configurar os caminhos de ROMs, samples, artwork, etc.
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)
from app.config.app_config import AppConfig
from app.core.services.ini_service import IniService
from app.mame.executable import MameExecutable


class DirectoriesTab(QWidget):
    """
    Aba para configuração de diretórios e arquivos do MAME.
    """

    settings_changed = Signal()
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.parent_window = parent
        self.config = AppConfig()
        self.ini_service: IniService | None = None
        self.mame_exec: MameExecutable | None = None

        self._setup_ui()
        self._refresh_ui_state()

    # ========================================================================
    # UI Setup
    # ========================================================================
    def _setup_ui(self) -> None:
        """Constrói a interface gráfica."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)
        # --- Executável MAME ---
        grp_mame = QGroupBox("Executável MAME")
        grp_mame.setToolTip("Selecione o arquivo mame.exe")
        form_mame = QFormLayout()
        grp_mame.setLayout(form_mame)

        self.edit_mame_path = QLineEdit()
        self.edit_mame_path.setReadOnly(True)
        self.edit_mame_path.setPlaceholderText("Nenhum arquivo selecionado")
        btn_browse_mame = QPushButton("Selecionar...")
        btn_browse_mame.clicked.connect(self._select_mame_executable)
        hbox_mame = QHBoxLayout()
        hbox_mame.addWidget(self.edit_mame_path)
        hbox_mame.addWidget(btn_browse_mame)
        form_mame.addRow("Caminho:", hbox_mame)

        self.lbl_version = QLabel("Versão: não detectada")
        self.lbl_version.setToolTip("Versão do MAME obtida através de --version")
        form_mame.addRow("", self.lbl_version)
        btn_reload = QPushButton("Recarregar e detectar")
        btn_reload.clicked.connect(self._detect_mame_version)
        form_mame.addRow("", btn_reload)

        layout.addWidget(grp_mame)

        # --- mame.ini ---
        grp_ini = QGroupBox("Arquivo mame.ini")
        grp_ini.setToolTip("Arquivo de configuração principal do MAME")
        form_ini = QFormLayout()
        grp_ini.setLayout(form_ini)
        self.edit_ini_path = QLineEdit()
        self.edit_ini_path.setReadOnly(True)
        self.edit_ini_path.setPlaceholderText("Nenhum arquivo carregado")
        btn_browse_ini = QPushButton("Selecionar...")
        btn_browse_ini.clicked.connect(self._select_ini_file)

        hbox_ini = QHBoxLayout()
        hbox_ini.addWidget(self.edit_ini_path)
        hbox_ini.addWidget(btn_browse_ini)
        form_ini.addRow("Caminho:", hbox_ini)
        btn_load_ini = QPushButton("Carregar mame.ini")
        btn_load_ini.clicked.connect(self._load_ini)
        form_ini.addRow("", btn_load_ini)

        layout.addWidget(grp_ini)

        # --- Diretórios do MAME ---
        grp_paths = QGroupBox("Diretórios do MAME")
        grp_paths.setToolTip("Configure os caminhos para ROMs, samples, artwork e outros")
        form_paths = QFormLayout()
        grp_paths.setLayout(form_paths)
        # ROM Path (5 campos com botão de seleção)
        self.rom_paths: list[QLineEdit] = []
        for i in range(1, 6):
            edit = QLineEdit()
            edit.setPlaceholderText(f"Diretório ROM {i}")
            edit.setToolTip(f"Caminho para o diretório de ROMs #{i}")
            btn_folder = QPushButton("...")
            btn_folder.setFixedWidth(30)
            btn_folder.clicked.connect(self._create_folder_selector(edit, f"Selecionar diretório ROM {i}"))
            hbox = QHBoxLayout()
            hbox.addWidget(edit)
            hbox.addWidget(btn_folder)
            self.rom_paths.append(edit)
            form_paths.addRow(f"ROM {i}:", hbox)
        # Função auxiliar para criar seletores de pasta
        def make_folder_selector(edit_widget: QLineEdit, title: str):
            def selector() -> None:
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
        self.dir_edits: dict[str, QLineEdit] = {}
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
        btn_save_ini.clicked.connect(self._save_ini)
        btn_save_ini.setStyleSheet("font-weight: bold; padding: 8px;")
        form_paths.addRow("", btn_save_ini)

        layout.addWidget(grp_paths)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

        self._set_ini_fields_enabled(False)
    # ========================================================================
    # UI State
    # ========================================================================
    def _refresh_ui_state(self) -> None:
        """Atualiza a UI com os valores salvos na configuração."""
        if self.config.mame_path and self.config.mame_path.exists():
            self.edit_mame_path.setText(str(self.config.mame_path))
            self._detect_mame_version()
        else:
            self.edit_mame_path.clear()
            self.lbl_version.setText("Versão: não detectada")
        if self.config.ini_path and self.config.ini_path.exists():
            self.edit_ini_path.setText(str(self.config.ini_path))
            self._load_ini()
        else:
            if self.config.mame_path and self.config.mame_path.parent:
                default_ini = self.config.mame_path.parent / "mame.ini"
                if default_ini.exists():
                    self.edit_ini_path.setText(str(default_ini))
                    self.config.ini_path = default_ini
                    self.config.save()
                    self._load_ini()
    # ========================================================================
    # MAME Executable
    # ========================================================================
    def _select_mame_executable(self) -> None:
        """Abre diálogo para selecionar o executável MAME."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar executável MAME",
            "",
            "Executáveis (*.exe);;Todos os arquivos (*)"
        )
        if not file_path:
            return
        path = Path(file_path)
        self.config.mame_path = path
        self.config.save()
        self.edit_mame_path.setText(str(path))
        self._detect_mame_version()

        # Tenta carregar mame.ini automaticamente da mesma pasta
        default_ini = path.parent / "mame.ini"
        if default_ini.exists():
            self.edit_ini_path.setText(str(default_ini))
            self.config.ini_path = default_ini
            self.config.save()
            self._load_ini()
        self.settings_changed.emit()

    def _detect_mame_version(self) -> None:
        """Detecta a versão do MAME e atualiza o label."""
        if not self.config.mame_path or not self.config.mame_path.exists():
            self.lbl_version.setText("Versão: arquivo não encontrado")
            return
        try:
            self.mame_exec = MameExecutable(self.config.mame_path)
            version = self.mame_exec.version
            self.lbl_version.setText(f"Versão: {version}")
            # A detecção é silenciosa durante a inicialização e ao recarregar.
            # O estado continua visível no próprio label da aba.
        except Exception as e:
            self.lbl_version.setText("Versão: erro na detecção")
            # Falhas de detecção também são silenciosas durante a inicialização.
            # O detalhe técnico permanece disponível no log do MAME.
    # ========================================================================
    # MAME.INI
    # ========================================================================

    def _select_ini_file(self) -> None:
        """Abre diálogo para selecionar o arquivo mame.ini."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar mame.ini",
            "",
            "Arquivos INI (*.ini);;Todos os arquivos (*)"
        )
        if not file_path:
            return
        self.edit_ini_path.setText(file_path)
        self.config.ini_path = Path(file_path)
        self.config.save()
        self._load_ini()

    def _load_ini(self) -> None:
        """Carrega o mame.ini e preenche os campos."""
        path = Path(self.edit_ini_path.text())
        if not path.exists():
            # Não interrompe a inicialização com um pop-up; o estado pode ser
            # visualizado na própria aba e o usuário pode selecionar outro INI.
            return
        try:
            self.ini_service = IniService(path)
            self._load_ini_values()
            # Carregamento normal é silencioso. O estado dos campos indica que
            # o arquivo foi carregado; erros continuam sendo tratados abaixo.
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao carregar mame.ini:\n{str(e)}")

    def _load_ini_values(self) -> None:
        """Preenche os campos da UI com os valores do mame.ini."""
        if not self.ini_service:
            return
        # ROM paths
        rom_list = self.ini_service.get_paths("rompath")
        for i, edit in enumerate(self.rom_paths):
            if i < len(rom_list):
                edit.setText(rom_list[i])
            else:
                edit.clear()
        # Outros diretórios
        mapping = {
            "samplepath": self.ini_service.get_samplepath,
            "artpath": self.ini_service.get_artpath,
            "cfgpath": self.ini_service.get_cfgpath,
            "nvrampath": self.ini_service.get_nvrampath,
            "statepath": self.ini_service.get_statepath,
            "snappath": self.ini_service.get_snappath,
            "diffpath": self.ini_service.get_diffpath,
            "inipath": self.ini_service.get_inipath,
        }
        for attr, getter in mapping.items():
            if attr in self.dir_edits:
                self.dir_edits[attr].setText(getter() or "")
        self._set_ini_fields_enabled(True)

    # ========================================================================
    # Save
    # ========================================================================

    def _save_ini(self) -> None:
        """Salva as alterações no mame.ini."""
        if not self.ini_service:
            QMessageBox.warning(self, "Erro", "Nenhum mame.ini carregado para salvar.")
            return
        try:
            # Coleta ROM paths
            rom_paths = [edit.text().strip() for edit in self.rom_paths if edit.text().strip()]
            self.ini_service.set_paths("rompath", rom_paths)
            # Outros campos
            fields = {
                "samplepath": self.dir_edits["samplepath"].text().strip(),
                "artpath": self.dir_edits["artpath"].text().strip(),
                "cfg_directory": self.dir_edits["cfgpath"].text().strip(),
                "nvram_directory": self.dir_edits["nvrampath"].text().strip(),
                "state_directory": self.dir_edits["statepath"].text().strip(),
                "snapshot_directory": self.dir_edits["snappath"].text().strip(),
                "diff_directory": self.dir_edits["diffpath"].text().strip(),
                "inipath": self.dir_edits["inipath"].text().strip(),
            }
            for key, value in fields.items():
                self.ini_service.set(key, value)
            self.ini_service.save()
            QMessageBox.information(self, "Sucesso", "mame.ini salvo com sucesso.")
            self.settings_changed.emit()

        except PermissionError:
            QMessageBox.critical(self, "Erro", "Permissão negada para salvar o arquivo.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao salvar mame.ini:\n{str(e)}")
    # ========================================================================
    # Helpers
    # ========================================================================

    def _set_ini_fields_enabled(self, enabled: bool) -> None:
        """Habilita/desabilita os campos de edição de diretórios."""
        for edit in self.rom_paths:
            edit.setEnabled(enabled)
        for edit in self.dir_edits.values():
            edit.setEnabled(enabled)
    def _create_folder_selector(self, edit_widget: QLineEdit, title: str):
        """Cria um seletor de pasta para um campo."""
        def selector() -> None:
            dir_path = QFileDialog.getExistingDirectory(self, title, edit_widget.text())
            if dir_path:
                edit_widget.setText(dir_path)
        return selector
