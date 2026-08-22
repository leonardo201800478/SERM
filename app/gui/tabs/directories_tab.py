"""Aba centralizada de diretórios e configurações dos emuladores.

A aba passa a ser a interface permanente para os quatro diretórios de
instalação (MAME, Flycast, Supermodel e FBNeo), reutilizando exatamente os
valores persistidos pela Home. A configuração específica do MAME permanece
nesta aba porque inclui o executável, mame.ini e seus caminhos internos.
"""

from __future__ import annotations

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
    """Configura os diretórios dos quatro emuladores e os caminhos do MAME."""

    EMULATORS = (
        ("mame", "MAME"),
        ("flycast", "Flycast"),
        ("supermodel", "Supermodel"),
        ("fbneo", "FBNeo"),
    )

    EXECUTABLES = {
        "mame": "mame.exe",
        "flycast": "flycast.exe",
        "supermodel": "supermodel.exe",
        "fbneo": "fbneo64.exe",
    }

    settings_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.parent_window = parent
        self.config = getattr(parent, "config", None) or AppConfig()
        self.ini_service: IniService | None = None
        self.mame_exec: MameExecutable | None = None
        self.emulator_dir_edits: dict[str, QLineEdit] = {}
        self.emulator_status_labels: dict[str, QLabel] = {}

        self._setup_ui()
        self._refresh_ui_state()

    # ========================================================================
    # UI
    # ========================================================================
    def _setup_ui(self) -> None:
        """Constrói a interface centralizada de diretórios."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        # --------------------------------------------------------------------
        # Instalações dos emuladores
        # --------------------------------------------------------------------
        grp_emulators = QGroupBox("Diretórios de instalação dos emuladores")
        grp_emulators.setToolTip(
            "Diretório raiz de cada instalação. Downloads e atualizações são "
            "extraídos diretamente nessas pastas, sem criar uma pasta adicional."
        )
        form_emulators = QFormLayout(grp_emulators)

        for key, label in self.EMULATORS:
            edit = QLineEdit()
            edit.setPlaceholderText("Pasta de instalação do emulador")
            edit.setReadOnly(True)
            button = QPushButton("Selecionar…")
            button.clicked.connect(lambda _=False, k=key: self._select_emulator_directory(k))
            status = QLabel("Não configurado")
            status.setStyleSheet("color:#999;")

            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(button)
            form_emulators.addRow(f"{label}:", row)
            form_emulators.addRow("", status)

            self.emulator_dir_edits[key] = edit
            self.emulator_status_labels[key] = status

        note = QLabel(
            "Os diretórios definidos aqui são os mesmos utilizados pela Home. "
            "Alterações são persistidas em ~/.mame-set-builder/config.json."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#888;font-size:10px;")
        form_emulators.addRow("", note)
        layout.addWidget(grp_emulators)

        # --------------------------------------------------------------------
        # Executável MAME
        # --------------------------------------------------------------------
        grp_mame = QGroupBox("Executável MAME")
        grp_mame.setToolTip("O executável válido do MAME é sempre mame.exe dentro do diretório configurado.")
        form_mame = QFormLayout(grp_mame)

        self.edit_mame_path = QLineEdit()
        self.edit_mame_path.setReadOnly(True)
        self.edit_mame_path.setPlaceholderText("mame.exe não localizado")
        btn_browse_mame = QPushButton("Selecionar…")
        btn_browse_mame.clicked.connect(self._select_mame_executable)
        row = QHBoxLayout()
        row.addWidget(self.edit_mame_path, 1)
        row.addWidget(btn_browse_mame)
        form_mame.addRow("Executável:", row)

        self.lbl_version = QLabel("Versão: não detectada")
        form_mame.addRow("", self.lbl_version)
        btn_reload = QPushButton("Recarregar e detectar")
        btn_reload.clicked.connect(self._detect_mame_version)
        form_mame.addRow("", btn_reload)
        layout.addWidget(grp_mame)

        # --------------------------------------------------------------------
        # mame.ini
        # --------------------------------------------------------------------
        grp_ini = QGroupBox("Arquivo mame.ini")
        grp_ini.setToolTip("O mame.ini deve permanecer na raiz da instalação, junto ao mame.exe.")
        form_ini = QFormLayout(grp_ini)

        self.edit_ini_path = QLineEdit()
        self.edit_ini_path.setReadOnly(True)
        self.edit_ini_path.setPlaceholderText("mame.ini não localizado")
        btn_browse_ini = QPushButton("Selecionar…")
        btn_browse_ini.clicked.connect(self._select_ini_file)
        row = QHBoxLayout()
        row.addWidget(self.edit_ini_path, 1)
        row.addWidget(btn_browse_ini)
        form_ini.addRow("Caminho:", row)

        self.lbl_ini_status = QLabel("Não carregado")
        self.lbl_ini_status.setStyleSheet("color:#999;")
        form_ini.addRow("Status:", self.lbl_ini_status)

        btn_load_ini = QPushButton("Carregar mame.ini")
        btn_load_ini.clicked.connect(self._load_ini)
        form_ini.addRow("", btn_load_ini)
        layout.addWidget(grp_ini)

        # --------------------------------------------------------------------
        # Diretórios internos do MAME
        # --------------------------------------------------------------------
        grp_paths = QGroupBox("Diretórios internos do MAME")
        grp_paths.setToolTip("Configure os caminhos definidos no mame.ini.")
        form_paths = QFormLayout(grp_paths)

        self.rom_paths: list[QLineEdit] = []
        for i in range(1, 6):
            edit = QLineEdit()
            edit.setPlaceholderText(f"Diretório ROM {i}")
            button = QPushButton("…")
            button.setFixedWidth(34)
            button.clicked.connect(self._create_folder_selector(edit, f"Selecionar diretório ROM {i}"))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(button)
            self.rom_paths.append(edit)
            form_paths.addRow(f"ROM {i}:", row)

        dirs = [
            ("Sample Path:", "samplepath", "samples"),
            ("Artwork Path:", "artpath", "artwork"),
            ("CFG Path:", "cfgpath", "cfg"),
            ("NVRAM Path:", "nvrampath", "nvram"),
            ("State Path:", "statepath", "sta"),
            ("Snapshot Path:", "snappath", "snap"),
            ("Diff Path:", "diffpath", "diff"),
            ("INI Path:", "inipath", "ini"),
        ]
        self.dir_edits: dict[str, QLineEdit] = {}
        for label, attr, placeholder in dirs:
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            button = QPushButton("…")
            button.setFixedWidth(34)
            button.clicked.connect(self._create_folder_selector(edit, f"Selecionar {label}"))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(button)
            self.dir_edits[attr] = edit
            form_paths.addRow(label, row)

        btn_save_ini = QPushButton("Salvar mame.ini")
        btn_save_ini.setStyleSheet("font-weight:bold;padding:8px;")
        btn_save_ini.clicked.connect(self._save_ini)
        form_paths.addRow("", btn_save_ini)
        layout.addWidget(grp_paths)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)
        self._set_ini_fields_enabled(False)

    # ========================================================================
    # Estado
    # ========================================================================
    def _refresh_ui_state(self) -> None:
        """Recarrega todos os valores persistidos e reflete a Home na aba."""
        self.config.load()
        for key, label in self.EMULATORS:
            directory = getattr(self.config, f"{key}_dir", None)
            self.emulator_dir_edits[key].setText(str(directory) if directory else "")
            self._update_emulator_directory_status(key, directory)

        self._refresh_mame_from_config()

    def _update_emulator_directory_status(self, key: str, directory: Path | None) -> None:
        """Mostra se o diretório e o executável esperado estão presentes."""
        status = self.emulator_status_labels[key]
        if not directory:
            status.setText("● Diretório não configurado")
            status.setStyleSheet("color:#999;font-weight:bold;")
            return
        executable = Path(directory) / self.EXECUTABLES[key]
        if executable.is_file():
            version = getattr(self.config, f"{key}_version", None)
            suffix = f" | versão {version}" if version else ""
            status.setText(f"● Instalação detectada: {executable.name}{suffix}")
            status.setStyleSheet("color:#55d66b;font-weight:bold;")
        else:
            status.setText(f"● Diretório definido; {self.EXECUTABLES[key]} não localizado")
            status.setStyleSheet("color:#e5c454;font-weight:bold;")

    def _refresh_mame_from_config(self) -> None:
        """Atualiza os campos específicos do MAME sem executar outro processo."""
        mame_dir = self.config.mame_dir
        mame_path = Path(mame_dir) / "mame.exe" if mame_dir else self.config.mame_path
        if mame_path and mame_path.is_file():
            self.config.mame_path = mame_path
            self.edit_mame_path.setText(str(mame_path))
            self._detect_mame_version()
        else:
            self.edit_mame_path.clear()
            self.lbl_version.setText("Versão: não detectada")

        ini = Path(mame_dir) / "mame.ini" if mame_dir else None
        if ini and ini.is_file():
            self.config.ini_path = ini
            self.config.save()
            self.edit_ini_path.setText(str(ini))
            self._load_ini()
        elif self.config.ini_path and self.config.ini_path.is_file():
            self.edit_ini_path.setText(str(self.config.ini_path))
            self._load_ini()
        else:
            self.edit_ini_path.clear()
            self.lbl_ini_status.setText("mame.ini não encontrado na raiz do MAME")
            self.lbl_ini_status.setStyleSheet("color:#e5c454;font-weight:bold;")

    # ========================================================================
    # Diretórios dos quatro emuladores
    # ========================================================================
    def _select_emulator_directory(self, key: str) -> None:
        """Seleciona e persiste a pasta de instalação de um emulador."""
        current = self.emulator_dir_edits[key].text().strip()
        selected = QFileDialog.getExistingDirectory(
            self,
            f"Selecionar diretório do {dict(self.EMULATORS)[key]}",
            current,
        )
        if not selected:
            return

        directory = Path(selected)
        setattr(self.config, f"{key}_dir", directory)

        # Se o executável já existe no diretório, ele passa a ser a instalação
        # canônica imediatamente. Nunca apontamos para o pacote baixado.
        executable = directory / self.EXECUTABLES[key]
        setattr(self.config, f"{key}_path", executable if executable.is_file() else None)
        self.config.save()

        self.emulator_dir_edits[key].setText(str(directory))
        self._update_emulator_directory_status(key, directory)

        # MAME precisa também recalcular o mame.ini a partir da nova raiz.
        if key == "mame":
            self._refresh_mame_from_config()

        self.settings_changed.emit()

    # ========================================================================
    # MAME executable / version
    # ========================================================================
    def _select_mame_executable(self) -> None:
        """Seleciona mame.exe e transforma sua pasta na instalação canônica."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar executável MAME",
            str(self.config.mame_dir or ""),
            "Executável MAME (mame.exe);;Executáveis (*.exe)",
        )
        if not file_path:
            return
        path = Path(file_path)
        if path.name.casefold() != "mame.exe":
            QMessageBox.warning(self, "MAME", "Selecione o mame.exe da instalação. Pacotes/instaladores não são aceitos.")
            return

        self.config.mame_dir = path.parent
        self.config.mame_path = path
        self.config.save()
        self.edit_mame_path.setText(str(path))
        self.emulator_dir_edits["mame"].setText(str(path.parent))
        self._update_emulator_directory_status("mame", path.parent)
        self._detect_mame_version()
        self._load_default_mame_ini()
        self.settings_changed.emit()

    def _detect_mame_version(self) -> None:
        """Detecta a versão exclusivamente executando o mame.exe instalado."""
        path = self.config.mame_path
        if not path or path.name.casefold() != "mame.exe" or not path.is_file():
            self.lbl_version.setText("Versão: mame.exe não encontrado")
            return
        try:
            self.mame_exec = MameExecutable(path)
            version = self.mame_exec.version
            self.lbl_version.setText(f"Versão: {version}")
            self.config.mame_version = str(version)
            self.config.save()
        except Exception:
            self.lbl_version.setText("Versão: erro na detecção")

    # ========================================================================
    # mame.ini
    # ========================================================================
    def _load_default_mame_ini(self) -> None:
        """Carrega mame.ini da raiz do diretório MAME, se existir."""
        if not self.config.mame_dir:
            return
        path = Path(self.config.mame_dir) / "mame.ini"
        if path.is_file():
            self.config.ini_path = path
            self.config.save()
            self.edit_ini_path.setText(str(path))
            self._load_ini()
        else:
            self.edit_ini_path.clear()
            self.lbl_ini_status.setText("mame.ini não encontrado na raiz do MAME")
            self.lbl_ini_status.setStyleSheet("color:#e5c454;font-weight:bold;")

    def _select_ini_file(self) -> None:
        """Seleciona manualmente um arquivo INI existente."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar mame.ini",
            str(self.config.mame_dir or ""),
            "Arquivos INI (*.ini);;Todos os arquivos (*)",
        )
        if not file_path:
            return
        self.config.ini_path = Path(file_path)
        self.config.save()
        self.edit_ini_path.setText(file_path)
        self._load_ini()

    def _load_ini(self) -> None:
        """Carrega o mame.ini e preenche os campos internos."""
        path = Path(self.edit_ini_path.text())
        if not path.is_file():
            self.lbl_ini_status.setText("mame.ini não encontrado")
            self.lbl_ini_status.setStyleSheet("color:#e5c454;font-weight:bold;")
            self._set_ini_fields_enabled(False)
            return
        try:
            self.ini_service = IniService(path)
            self._load_ini_values()
            self.lbl_ini_status.setText("● Carregado")
            self.lbl_ini_status.setStyleSheet("color:#55d66b;font-weight:bold;")
        except Exception as exc:
            self.lbl_ini_status.setText(f"● Erro: {exc}")
            self.lbl_ini_status.setStyleSheet("color:#e05a5a;font-weight:bold;")
            self._set_ini_fields_enabled(False)

    def _load_ini_values(self) -> None:
        """Preenche a interface com os caminhos encontrados no mame.ini."""
        if not self.ini_service:
            return
        rom_list = self.ini_service.get_paths("rompath")
        for i, edit in enumerate(self.rom_paths):
            edit.setText(rom_list[i] if i < len(rom_list) else "")

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
            self.dir_edits[attr].setText(getter() or "")
        self._set_ini_fields_enabled(True)

    def _save_ini(self) -> None:
        """Salva os caminhos alterados no mame.ini existente."""
        if not self.ini_service:
            QMessageBox.warning(self, "MAME", "Nenhum mame.ini carregado para salvar.")
            return
        try:
            rom_paths = [edit.text().strip() for edit in self.rom_paths if edit.text().strip()]
            self.ini_service.set_paths("rompath", rom_paths)
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
            QMessageBox.information(self, "MAME", "mame.ini salvo com sucesso.")
            self.settings_changed.emit()
        except PermissionError:
            QMessageBox.critical(self, "MAME", "Permissão negada para salvar o mame.ini.")
        except Exception as exc:
            QMessageBox.critical(self, "MAME", f"Falha ao salvar mame.ini:\n{exc}")

    # ========================================================================
    # Helpers
    # ========================================================================
    def _set_ini_fields_enabled(self, enabled: bool) -> None:
        """Habilita ou desabilita os campos internos do MAME."""
        for edit in self.rom_paths:
            edit.setEnabled(enabled)
        for edit in self.dir_edits.values():
            edit.setEnabled(enabled)

    def _create_folder_selector(self, edit_widget: QLineEdit, title: str):
        """Cria o callback de seleção de uma pasta."""
        def selector() -> None:
            selected = QFileDialog.getExistingDirectory(self, title, edit_widget.text())
            if selected:
                edit_widget.setText(selected)
        return selector

    def refresh(self) -> None:
        """Atualiza a aba após alterações realizadas por outra interface."""
        self._refresh_ui_state()
