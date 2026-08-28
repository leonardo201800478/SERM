"""Configuração central dos diretórios dos emuladores.

A aba usa o ``adapter_registry`` como fonte única para identidade,
executável e contrato de diretórios. O tratamento físico específico de MAME
e Flycast permanece nesta camada porque esses formatos têm regras próprias.
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QTabWidget, QVBoxLayout, QWidget, QFileDialog,
)

from app.config.app_config import AppConfig
from app.core.services.ini_service import IniService
from app.emulators.adapter_registry import DirectorySpec, get_adapter, list_adapters
from app.mame.executable import MameExecutable


class DirectoriesTab(QWidget):
    """Aba central de diretórios, orientada pelo registro de adapters."""

    # MAME/Flycast/Supermodel/FBNeo são as abas tradicionais desta tela.
    # RetroArch possui uma tela própria de diretórios e não deve ser duplicado
    # aqui. A identidade, porém, vem do registry e não de constantes locais.
    DIRECTORY_EMULATORS = ("mame", "flycast", "supermodel", "fbneo")

    settings_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.parent_window = parent
        self.config = getattr(parent, "config", None) or AppConfig()
        self.ini_service = None
        self.mame_exec = None
        self.emulator_dir_edits: dict[str, QLineEdit] = {}
        self.emulator_status_labels: dict[str, QLabel] = {}
        self.path_edits: dict[str, dict[str, QLineEdit]] = {}
        self.flycast_rom_edits: list[QLineEdit] = []
        self._setup_ui()
        self._refresh_ui_state()

    @staticmethod
    def _adapter(key: str):
        """Retorna o adapter central do emulador solicitado."""
        return get_adapter(key)

    def _setup_ui(self) -> None:
        """Cria a aba e suas páginas a partir dos adapters registrados."""
        root = QVBoxLayout(self)
        title = QLabel("Diretórios dos emuladores")
        title.setStyleSheet("font-size:20px;font-weight:bold;")
        root.addWidget(title)
        info = QLabel(
            "Cada emulador possui sua própria instalação e seus diretórios de conteúdo. "
            "As configurações são compartilhadas com Home, Catálogos, Scan e Reconstrução."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#888;padding-bottom:4px;")
        root.addWidget(info)
        self.subtabs = QTabWidget()
        root.addWidget(self.subtabs, 1)
        for key in self.DIRECTORY_EMULATORS:
            adapter = self._adapter(key)
            self.subtabs.addTab(self._create_emulator_page(adapter), adapter.label)

    def _create_emulator_page(self, adapter) -> QWidget:
        """Cria a página rolável usando somente o contrato do adapter."""
        key = adapter.emulator
        label = adapter.label
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        layout = QVBoxLayout(container)

        installation = QGroupBox(f"Instalação do {label}")
        form = QFormLayout(installation)
        directory = QLineEdit()
        directory.setReadOnly(True)
        directory.setPlaceholderText("Diretório de instalação")
        browse = QPushButton("Selecionar…")
        browse.clicked.connect(lambda _=False, k=key: self._select_emulator_directory(k))
        row = QHBoxLayout()
        row.addWidget(directory, 1)
        row.addWidget(browse)
        form.addRow("Diretório:", row)
        executable = QLineEdit()
        executable.setReadOnly(True)
        executable.setPlaceholderText(adapter.executable)
        form.addRow("Executável:", executable)
        status = QLabel("● Não configurado")
        status.setStyleSheet("color:#999;font-weight:bold;")
        form.addRow("Status:", status)
        layout.addWidget(installation)

        self.emulator_dir_edits[key] = directory
        self.emulator_status_labels[key] = status
        setattr(self, f"{key}_executable_edit", executable)

        if key == "mame":
            self._build_mame_content(layout)
        elif key == "flycast":
            self._build_flycast_content(layout)
        else:
            self._build_generic_content(layout, adapter)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _build_mame_content(self, layout: QVBoxLayout) -> None:
        """Constrói a configuração de diretórios baseada no mame.ini real."""
        grp_ini = QGroupBox("mame.ini")
        form_ini = QFormLayout(grp_ini)
        self.edit_ini_path = QLineEdit()
        self.edit_ini_path.setReadOnly(True)
        self.edit_ini_path.setPlaceholderText("mame.ini não localizado")
        btn = QPushButton("Selecionar…")
        btn.clicked.connect(self._select_ini_file)
        row = QHBoxLayout()
        row.addWidget(self.edit_ini_path, 1)
        row.addWidget(btn)
        form_ini.addRow("Arquivo:", row)
        self.lbl_ini_status = QLabel("Não carregado")
        form_ini.addRow("Status:", self.lbl_ini_status)
        load = QPushButton("Carregar mame.ini")
        load.clicked.connect(self._load_ini)
        form_ini.addRow("", load)
        layout.addWidget(grp_ini)

        grp = QGroupBox("Diretórios definidos no mame.ini")
        form = QFormLayout(grp)
        self.rom_paths = []
        rom_spec = self._adapter("mame").directory("roms")
        for i in range(1, rom_spec.max_entries + 1):
            edit = QLineEdit()
            edit.setPlaceholderText(f"Diretório ROM {i}")
            b = QPushButton("…")
            b.setFixedWidth(34)
            b.clicked.connect(self._create_folder_selector(edit, f"Selecionar diretório ROM {i}"))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(b)
            self.rom_paths.append(edit)
            form.addRow(f"ROM {i}:", row)

        self.dir_edits = {}
        for spec in self._adapter("mame").directories:
            if spec.key == "roms":
                continue
            edit = QLineEdit()
            edit.setPlaceholderText(spec.label)
            b = QPushButton("…")
            b.setFixedWidth(34)
            b.clicked.connect(self._create_folder_selector(edit, f"Selecionar {spec.label}"))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(b)
            self.dir_edits[spec.key] = edit
            form.addRow(f"{spec.label}:", row)

        save = QPushButton("Salvar mame.ini")
        save.setStyleSheet("font-weight:bold;padding:8px;")
        save.clicked.connect(self._save_ini)
        form.addRow("", save)
        layout.addWidget(grp)
        note = QLabel(
            "O MAME usa o mame.ini como fonte de verdade. Os caminhos acima são lidos e gravados diretamente nesse arquivo."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#888;font-size:10px;")
        layout.addWidget(note)

    def _build_flycast_content(self, layout: QVBoxLayout) -> None:
        """Constrói os diretórios do Flycast segundo o contrato do adapter."""
        group = QGroupBox("Diretórios de conteúdo do Flycast")
        form = QFormLayout(group)
        adapter = self._adapter("flycast")
        self.path_edits["flycast"] = {}
        self.flycast_rom_edits = []
        rom_spec = adapter.directory("roms")

        for index in range(1, rom_spec.max_entries + 1):
            edit = QLineEdit()
            edit.setPlaceholderText(f"Diretório ROM {index}")
            button = QPushButton("…")
            button.setFixedWidth(34)
            button.clicked.connect(self._create_folder_selector(edit, f"Selecionar diretório ROM {index}"))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(button)
            self.flycast_rom_edits.append(edit)
            form.addRow(f"ROM {index}:", row)

        for spec in adapter.directories:
            if spec.key == "roms":
                continue
            edit = QLineEdit()
            edit.setPlaceholderText(spec.label)
            button = QPushButton("…")
            button.setFixedWidth(34)
            button.clicked.connect(self._create_emulator_path_selector("flycast", spec, edit))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(button)
            self.path_edits["flycast"][spec.key] = edit
            form.addRow(f"{spec.label}:", row)

        save = QPushButton("Salvar diretórios do Flycast")
        save.setStyleSheet("font-weight:bold;padding:8px;")
        save.clicked.connect(lambda _=False: self._save_flycast_paths())
        form.addRow("", save)
        layout.addWidget(group)

        note = QLabel(
            f"Os quatro campos de ROM são gravados em {rom_spec.native_key} na mesma linha, "
            "separados por ';'. Os demais diretórios permanecem como campos únicos."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#888;font-size:10px;padding:4px;")
        layout.addWidget(note)

    def _build_generic_content(self, layout: QVBoxLayout, adapter) -> None:
        """Constrói os diretórios de conteúdo usando ``DirectorySpec``."""
        key = adapter.emulator
        label = adapter.label
        group = QGroupBox(f"Diretórios de conteúdo do {label}")
        form = QFormLayout(group)
        self.path_edits[key] = {}
        for spec in adapter.directories:
            edit = QLineEdit()
            edit.setPlaceholderText(spec.label)
            b = QPushButton("…")
            b.setFixedWidth(34)
            b.clicked.connect(self._create_emulator_path_selector(key, spec, edit))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(b)
            self.path_edits[key][spec.key] = edit
            form.addRow(f"{spec.label}:", row)
        save = QPushButton(f"Salvar diretórios do {label}")
        save.setStyleSheet("font-weight:bold;padding:8px;")
        save.clicked.connect(lambda _=False, k=key: self._save_generic_paths(k))
        form.addRow("", save)
        layout.addWidget(group)
        note = QLabel(
            "Os diretórios exibidos são definidos pelo adapter e permanecem disponíveis para os serviços do projeto."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#888;font-size:10px;padding:4px;")
        layout.addWidget(note)

    def _refresh_ui_state(self) -> None:
        """Recarrega a configuração persistida e atualiza as subabas."""
        self.config.load()
        for key in self.DIRECTORY_EMULATORS:
            adapter = self._adapter(key)
            directory = getattr(self.config, f"{key}_dir", None)
            self.emulator_dir_edits[key].setText(str(directory) if directory else "")
            executable = Path(directory) / adapter.executable if directory else None
            getattr(self, f"{key}_executable_edit").setText(str(executable) if executable else "")
            self._update_emulator_directory_status(key, directory)
            if key != "mame":
                self._load_generic_paths(key, directory)
        self._refresh_mame_from_config()

    def _update_emulator_directory_status(self, key: str, directory: Path | None) -> None:
        """Mostra se o diretório e o executável registrado estão presentes."""
        adapter = self._adapter(key)
        status = self.emulator_status_labels[key]
        if not directory:
            status.setText("● Diretório não configurado")
            status.setStyleSheet("color:#999;font-weight:bold;")
            return
        executable = Path(directory) / adapter.executable
        if executable.is_file():
            version = getattr(self.config, f"{key}_version", None)
            suffix = f" | versão {version}" if version else ""
            status.setText(f"● Instalação detectada: {executable.name}{suffix}")
            status.setStyleSheet("color:#55d66b;font-weight:bold;")
        else:
            status.setText(f"● Diretório definido; {adapter.executable} não localizado")
            status.setStyleSheet("color:#e5c454;font-weight:bold;")

    def _select_emulator_directory(self, key: str) -> None:
        """Seleciona e persiste a raiz de instalação do emulador."""
        adapter = self._adapter(key)
        current = self.emulator_dir_edits[key].text().strip()
        selected = QFileDialog.getExistingDirectory(self, f"Selecionar diretório do {adapter.label}", current)
        if not selected:
            return
        directory = Path(selected)
        setattr(self.config, f"{key}_dir", directory)
        executable = directory / adapter.executable
        setattr(self.config, f"{key}_path", executable if executable.is_file() else None)
        if key != "mame":
            self._initialize_generic_defaults(key, directory)
        self.config.save()
        self.emulator_dir_edits[key].setText(str(directory))
        getattr(self, f"{key}_executable_edit").setText(str(executable))
        self._update_emulator_directory_status(key, directory)
        if key != "mame":
            self._load_generic_paths(key, directory)
        else:
            self._refresh_mame_from_config()
        self.settings_changed.emit()

    def _initialize_generic_defaults(self, key: str, directory: Path) -> None:
        """Inicializa defaults sem sobrescrever caminhos existentes."""
        for spec in self._adapter(key).directories:
            if not spec.relative_default:
                continue
            if spec.key == "roms" and spec.multiple:
                continue
            if self.config.get_emulator_path(key, spec.key) is None:
                self.config.set_emulator_path(key, spec.key, directory / spec.relative_default)

    def _load_generic_paths(self, key: str, directory: Path | None) -> None:
        """Carrega caminhos persistidos segundo o contrato do adapter."""
        if key == "flycast":
            if directory:
                self._initialize_generic_defaults(key, directory)
            rom_paths = self.config.get_flycast_rom_paths()
            for index, edit in enumerate(self.flycast_rom_edits):
                edit.setText(str(rom_paths[index]) if index < len(rom_paths) else "")
            for path_key, edit in self.path_edits[key].items():
                path = self.config.get_emulator_path(key, path_key)
                edit.setText(str(path) if path else "")
            self._load_flycast_native_config()
            return
        if key not in self.path_edits:
            return
        if directory:
            self._initialize_generic_defaults(key, directory)
        for path_key, edit in self.path_edits[key].items():
            path = self.config.get_emulator_path(key, path_key)
            edit.setText(str(path) if path else "")

    def _create_emulator_path_selector(self, key: str, spec: DirectorySpec, edit_widget: QLineEdit):
        """Cria o callback de seleção para um diretório do adapter."""
        def selector() -> None:
            current = edit_widget.text().strip()
            selected = QFileDialog.getExistingDirectory(self, f"Selecionar {spec.label}", current)
            if selected:
                edit_widget.setText(selected)
                self.config.set_emulator_path(key, spec.key, Path(selected))
        return selector

    def _save_generic_paths(self, key: str) -> None:
        """Persiste os diretórios definidos pelo adapter."""
        for path_key, edit in self.path_edits[key].items():
            value = edit.text().strip()
            self.config.set_emulator_path(key, path_key, Path(value) if value else None)
        self.config.save()
        self._update_emulator_directory_status(key, getattr(self.config, f"{key}_dir", None))
        self.settings_changed.emit()
        QMessageBox.information(self, self._adapter(key).label, f"Diretórios do {self._adapter(key).label} salvos com sucesso.")

    def _flycast_config_path(self) -> Path | None:
        """Localiza o emu.cfg do Flycast."""
        directory = self.config.flycast_dir
        candidates: list[Path] = []
        if directory:
            candidates.extend((Path(directory) / "emu.cfg", Path(directory) / "config" / "emu.cfg"))
        appdata = os.environ.get("APPDATA")
        local_appdata = os.environ.get("LOCALAPPDATA")
        if appdata:
            candidates.append(Path(appdata) / "flycast" / "emu.cfg")
        if local_appdata:
            candidates.append(Path(local_appdata) / "flycast" / "emu.cfg")
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return (Path(directory) / "emu.cfg") if directory else None

    @staticmethod
    def _replace_flycast_key(text: str, key: str, value: str) -> str:
        """Substitui/cria uma chave dentro da seção [config] do emu.cfg."""
        lines = text.splitlines(keepends=True)
        section_start = None
        section_end = len(lines)
        for index, raw in enumerate(lines):
            stripped = raw.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                if stripped.casefold() == "[config]":
                    section_start = index
                elif section_start is not None:
                    section_end = index
                    break
        if section_start is None:
            if text and not text.endswith(("\n", "\r")):
                text += "\n"
            return f"{text}[config]\n{key} = {value}\n"
        for index in range(section_start + 1, section_end):
            stripped = lines[index].strip()
            if not stripped or stripped.startswith(("#", ";")) or "=" not in stripped:
                continue
            current_key, _ = stripped.split("=", 1)
            if current_key.strip() == key:
                newline = "\n" if lines[index].endswith("\n") else ""
                lines[index] = f"{key} = {value}{newline}"
                return "".join(lines)
        lines.insert(section_end, f"{key} = {value}\n")
        return "".join(lines)

    def _load_flycast_native_config(self) -> None:
        """Relê Dreamcast.ContentPath do emu.cfg quando disponível."""
        config_path = self._flycast_config_path()
        if not config_path or not config_path.is_file():
            return
        try:
            text = config_path.read_text(encoding="utf-8")
        except OSError:
            return
        rom_spec = self._adapter("flycast").directory("roms")
        native_key = rom_spec.native_key
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if native_key and stripped.startswith(native_key) and "=" in stripped:
                _, value = stripped.split("=", 1)
                native_paths = [Path(item.strip()) for item in value.split(";") if item.strip()]
                if native_paths:
                    self.config.set_flycast_rom_paths(native_paths)
                for index, edit in enumerate(self.flycast_rom_edits):
                    edit.setText(str(native_paths[index]) if index < len(native_paths) else "")
                break

    def _save_flycast_paths(self) -> None:
        """Salva os diretórios do Flycast e sincroniza o emu.cfg."""
        rom_spec = self._adapter("flycast").directory("roms")
        rom_paths = [Path(edit.text().strip()) for edit in self.flycast_rom_edits if edit.text().strip()]
        self.config.set_flycast_rom_paths(rom_paths)
        for path_key, edit in self.path_edits["flycast"].items():
            value = edit.text().strip()
            self.config.set_emulator_path("flycast", path_key, Path(value) if value else None)
        self.config.save()
        config_path = self._flycast_config_path()
        if not config_path:
            QMessageBox.warning(self, "Flycast", "Diretório de instalação do Flycast não configurado.")
            return
        try:
            text = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
            content_value = ";".join(str(path) for path in rom_paths)
            text = self._replace_flycast_key(text, rom_spec.native_key or "Dreamcast.ContentPath", content_value)
            for spec in self._adapter("flycast").directories:
                if spec.key == "roms" or not spec.native_key:
                    continue
                path = self.config.get_emulator_path("flycast", spec.key)
                text = self._replace_flycast_key(text, spec.native_key, str(path) if path else "")
            config_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = config_path.with_suffix(config_path.suffix + ".tmp")
            temp_path.write_text(text, encoding="utf-8", newline="")
            temp_path.replace(config_path)
            self._load_flycast_native_config()
        except PermissionError:
            QMessageBox.critical(self, "Flycast", f"Permissão negada para salvar o arquivo:\n{config_path}")
            return
        except OSError as exc:
            QMessageBox.critical(self, "Flycast", f"Falha ao salvar o emu.cfg:\n{exc}")
            return
        self._update_emulator_directory_status("flycast", getattr(self.config, "flycast_dir", None))
        self.settings_changed.emit()
        QMessageBox.information(self, "Flycast", "Diretórios do Flycast salvos com sucesso.")

    def _refresh_mame_from_config(self) -> None:
        """Atualiza o MAME a partir da instalação configurada."""
        mame_dir = self.config.mame_dir
        mame_path = Path(mame_dir) / self._adapter("mame").executable if mame_dir else self.config.mame_path
        if mame_path and mame_path.is_file():
            self.config.mame_path = mame_path
            self._detect_mame_version()
            self._load_default_mame_ini()
        else:
            self.mame_executable_edit.setText(str(mame_path) if mame_path else "")
            self.lbl_ini_status.setText("mame.ini não encontrado")
            self._set_ini_fields_enabled(False)

    def _select_mame_executable(self) -> None:
        """Compatibilidade: seleção direta do MAME passa a selecionar sua pasta."""
        self._select_emulator_directory("mame")

    def _detect_mame_version(self) -> None:
        """Detecta a versão do mame.exe instalado."""
        path = self.config.mame_path
        if not path or path.name.casefold() != self._adapter("mame").executable.casefold() or not path.is_file():
            self.mame_executable_edit.setText(str(path) if path else "")
            return
        self.mame_executable_edit.setText(str(path))
        try:
            self.mame_exec = MameExecutable(path)
            version = self.mame_exec.version
            self.config.mame_version = str(version)
            self.config.save()
            self._update_emulator_directory_status("mame", self.config.mame_dir)
        except Exception:
            self.emulator_status_labels["mame"].setText("● Erro na detecção da versão")
            self.emulator_status_labels["mame"].setStyleSheet("color:#e05a5a;font-weight:bold;")

    def _load_default_mame_ini(self) -> None:
        """Carrega o mame.ini da raiz da instalação."""
        if not self.config.mame_dir:
            return
        path = Path(self.config.mame_dir) / self._adapter("mame").config_filename
        if path.is_file():
            self.config.ini_path = path
            self.config.save()
            self.edit_ini_path.setText(str(path))
            self._load_ini()
        else:
            self.edit_ini_path.clear()
            self.lbl_ini_status.setText("mame.ini não encontrado na raiz do MAME")
            self.lbl_ini_status.setStyleSheet("color:#e5c454;font-weight:bold;")
            self._set_ini_fields_enabled(False)

    def _select_ini_file(self) -> None:
        """Seleciona manualmente um mame.ini existente."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Selecionar mame.ini", str(self.config.mame_dir or ""), "Arquivos INI (*.ini);;Todos os arquivos (*)")
        if not file_path:
            return
        self.config.ini_path = Path(file_path)
        self.config.save()
        self.edit_ini_path.setText(file_path)
        self._load_ini()

    def _load_ini(self) -> None:
        """Carrega o mame.ini e preenche os caminhos internos."""
        path = Path(self.edit_ini_path.text())
        if not path.is_file():
            self.lbl_ini_status.setText("mame.ini não encontrado")
            self._set_ini_fields_enabled(False)
            return
        try:
            self.ini_service = IniService(path)
            self._load_ini_values()
            self.lbl_ini_status.setText("● Carregado")
            self.lbl_ini_status.setStyleSheet("color:#55d66b;font-weight:bold;")
        except Exception as exc:
            self.ini_service = None
            self.lbl_ini_status.setText(f"● Erro: {exc}")
            self.lbl_ini_status.setStyleSheet("color:#e05a5a;font-weight:bold;")
            self._set_ini_fields_enabled(False)

    def _load_ini_values(self) -> None:
        """Preenche os campos com os caminhos encontrados no mame.ini."""
        if not self.ini_service:
            return
        rom_list = self.ini_service.get_paths("rompath")
        for i, edit in enumerate(self.rom_paths):
            edit.setText(rom_list[i] if i < len(rom_list) else "")
        mapping = {
            "samples": self.ini_service.get_samplepath,
            "artwork": self.ini_service.get_artpath,
            "cfg": self.ini_service.get_cfgpath,
            "nvram": self.ini_service.get_nvrampath,
            "states": self.ini_service.get_statepath,
            "snapshots": self.ini_service.get_snappath,
            "diff": self.ini_service.get_diffpath,
            "ini": self.ini_service.get_inipath,
        }
        for key, getter in mapping.items():
            if key in self.dir_edits:
                self.dir_edits[key].setText(getter() or "")
        self._set_ini_fields_enabled(True)

    def _save_ini(self) -> None:
        """Salva os caminhos alterados diretamente no mame.ini."""
        if not self.ini_service:
            QMessageBox.warning(self, "MAME", "Nenhum mame.ini carregado para salvar.")
            return
        try:
            self.ini_service.set_paths("rompath", [edit.text().strip() for edit in self.rom_paths if edit.text().strip()])
            fields = {spec.native_key: self.dir_edits[spec.key].text().strip() for spec in self._adapter("mame").directories if spec.key != "roms" and spec.native_key and spec.key in self.dir_edits}
            for key, value in fields.items():
                self.ini_service.set(key, value)
            self.ini_service.save()
            self.config.ini_path = Path(self.edit_ini_path.text())
            self.config.save()
            self.settings_changed.emit()
            QMessageBox.information(self, "MAME", "mame.ini salvo com sucesso.")
        except PermissionError:
            QMessageBox.critical(self, "MAME", "Permissão negada para salvar o mame.ini.")
        except Exception as exc:
            QMessageBox.critical(self, "MAME", f"Falha ao salvar o mame.ini:\n{exc}")

    def _set_ini_fields_enabled(self, enabled: bool) -> None:
        """Habilita ou desabilita os campos de diretórios do MAME."""
        for edit in self.rom_paths:
            edit.setEnabled(enabled)
        for edit in self.dir_edits.values():
            edit.setEnabled(enabled)

    def _create_folder_selector(self, edit_widget: QLineEdit, title: str):
        """Cria um seletor de pasta para um campo do MAME."""
        def selector() -> None:
            selected = QFileDialog.getExistingDirectory(self, title, edit_widget.text())
            if selected:
                edit_widget.setText(selected)
        return selector

    def refresh(self) -> None:
        """Atualiza as subabas após alterações realizadas por outra interface."""
        self._refresh_ui_state()
