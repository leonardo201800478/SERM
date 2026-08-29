"""Sessão Home do RetroArch com gerenciamento em lote dos cores update."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt, Slot
from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QPlainTextEdit, QProgressBar, QVBoxLayout, QWidget

from app.config.app_config import AppConfig
from app.core.services.retroarch_download_service import RetroArchDownloadService
from app.gui.widgets.retroarch_download_worker import RetroArchDownloadWorker


class RetroArchHomeTab(QWidget):
    """Gerencia instalação, atualização e cores do RetroArch pelo Buildbot oficial."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = getattr(parent, "config", None) or AppConfig()
        self._thread: QThread | None = None
        self._worker: RetroArchDownloadWorker | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Monta diagnóstico, canais, operações e seleção em lote de cores."""
        layout = QVBoxLayout(self)
        title = QLabel("RetroArch")
        title.setStyleSheet("font-size:22px;font-weight:bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        status = QGroupBox("Estado da instalação")
        form = QFormLayout(status)
        self.status_label, self.path_label, self.config_label, self.cores_label = QLabel(), QLabel(), QLabel(), QLabel()
        for label in (self.status_label, self.path_label, self.config_label, self.cores_label):
            label.setWordWrap(True)
        form.addRow("Status:", self.status_label)
        form.addRow("Instalação:", self.path_label)
        form.addRow("Configuração:", self.config_label)
        form.addRow("Cores:", self.cores_label)
        layout.addWidget(status)

        channel = QGroupBox("Distribuição oficial")
        channel_form = QFormLayout(channel)
        self.channel_combo = QComboBox()
        self.channel_combo.addItems(["Nightly", "Stable"])
        self.channel_combo.currentTextChanged.connect(self._channel_changed)
        self.stable_combo = QComboBox()
        self.stable_combo.setEnabled(False)
        channel_form.addRow("Canal:", self.channel_combo)
        channel_form.addRow("Versão Stable:", self.stable_combo)
        stable_refresh = QPushButton("Consultar versões Stable")
        stable_refresh.clicked.connect(self.refresh_stable_versions)
        channel_form.addRow("", stable_refresh)
        layout.addWidget(channel)

        operations = QGroupBox("RetroArch")
        actions = QHBoxLayout(operations)
        self.install_button = QPushButton("Nova instalação")
        self.install_button.clicked.connect(self.install_new)
        actions.addWidget(self.install_button)
        self.update_button = QPushButton("Atualizar RetroArch")
        self.update_button.clicked.connect(self.update_retroarch)
        actions.addWidget(self.update_button)
        layout.addWidget(operations)

        cores_group = QGroupBox("Cores libretro")
        cores_layout = QVBoxLayout(cores_group)
        core_actions = QHBoxLayout()
        self.core_refresh_button = QPushButton("Atualizar lista de cores")
        self.core_refresh_button.clicked.connect(self.refresh_cores)
        core_actions.addWidget(self.core_refresh_button)
        self.core_install_button = QPushButton("Instalar / atualizar selecionados")
        self.core_install_button.clicked.connect(self.install_selected_cores)
        core_actions.addWidget(self.core_install_button)
        self.core_update_installed_button = QPushButton("Atualizar cores instalados")
        self.core_update_installed_button.clicked.connect(self.update_installed_cores)
        core_actions.addWidget(self.core_update_installed_button)
        self.select_all_button = QPushButton("Selecionar tudo")
        self.select_all_button.clicked.connect(self.select_all_cores)
        core_actions.addWidget(self.select_all_button)
        self.clear_button = QPushButton("Limpar")
        self.clear_button.clicked.connect(self.clear_core_selection)
        core_actions.addWidget(self.clear_button)
        core_actions.addStretch()
        cores_layout.addLayout(core_actions)

        self.core_list = QListWidget()
        self.core_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        cores_layout.addWidget(self.core_list, 1)
        layout.addWidget(cores_group, 1)

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.log.setStyleSheet("QPlainTextEdit{background:#0b0b0b;color:#d7d7d7;font-family:Consolas;font-size:10px;}")
        layout.addWidget(QLabel("Log do downloader"))
        layout.addWidget(self.log, 1)

        shortcuts = QHBoxLayout()
        directories = QPushButton("Configurar diretórios")
        directories.clicked.connect(self.open_directories)
        shortcuts.addWidget(directories)
        catalog = QPushButton("Abrir catálogo de cores")
        catalog.clicked.connect(self.open_catalog)
        shortcuts.addWidget(catalog)
        settings = QPushButton("Configurações do RetroArch")
        settings.clicked.connect(self.open_settings)
        shortcuts.addWidget(settings)
        layout.addLayout(shortcuts)

    def refresh(self) -> None:
        """Atualiza diagnóstico e preserva a lista de cores sem baixar o índice novamente."""
        self.config.load()
        executable = self.config.retroarch_path
        root = self.config.retroarch_dir
        config_path = self.config.get_emulator_path("retroarch", "config") or root
        cores = self.config.get_emulator_path("retroarch", "cores")
        if executable and Path(executable).is_file():
            detected = RetroArchDownloadService.detect_installed_version(executable)
            if detected and detected != self.config.retroarch_version:
                self.config.retroarch_version = detected
                self.config.save()
        self.path_label.setText(str(root or "não configurada"))
        self.config_label.setText(str(config_path or "não configurada"))
        self.cores_label.setText(str(cores or "não configurado"))
        if executable and Path(executable).is_file():
            self.status_label.setText(f"● Pronto | versão {self.config.retroarch_version or 'não detectada'}")
            self.status_label.setStyleSheet("color:#55d66b;font-weight:bold;")
        elif root:
            self.status_label.setText("● Diretório configurado; executável não localizado")
            self.status_label.setStyleSheet("color:#e5c454;font-weight:bold;")
        else:
            self.status_label.setText("● Não configurado")
            self.status_label.setStyleSheet("color:#999;font-weight:bold;")
        self._refresh_installed_markers()
        self._update_busy_state()

    def _channel_changed(self, value: str) -> None:
        """Habilita Stable e atualiza sua lista quando o canal é selecionado."""
        is_stable = value.casefold() == "stable"
        self.stable_combo.setEnabled(is_stable)
        if is_stable and self.stable_combo.count() == 0:
            self.refresh_stable_versions()

    def refresh_stable_versions(self) -> None:
        """Consulta versões Stable diretamente no índice oficial."""
        try:
            versions = RetroArchDownloadService.discover_stable_versions()
            self.stable_combo.clear()
            self.stable_combo.addItems(versions)
            self._append_log(f"STABLE | versões encontradas={len(versions)} | mais recente={versions[0] if versions else '—'}")
        except Exception as exc:
            self._append_log(f"ERRO STABLE | {type(exc).__name__}: {exc}")

    def _channel(self) -> tuple[str, str | None]:
        """Retorna canal e versão Stable selecionados."""
        mode = self.channel_combo.currentText().casefold()
        version = self.stable_combo.currentText().strip() if mode == "stable" else None
        return mode, version or None

    def _destination(self) -> Path:
        """Retorna a raiz de instalação configurada ou uma pasta portátil padrão."""
        return Path(self.config.retroarch_dir or Path.home() / "RetroArch-Win64").expanduser()

    def install_new(self) -> None:
        """Inicia nova instalação."""
        self._start_worker("install")

    def update_retroarch(self) -> None:
        """Atualiza RetroArch preservando config, saves e states."""
        if not self.config.retroarch_dir:
            self._append_log("ERRO | selecione o retroarch.exe em Diretórios antes de atualizar.")
            return
        self._start_worker("update")

    def _installed_core_filenames(self) -> set[str]:
        """Lê diretamente o diretório de cores configurado e retorna DLLs instaladas."""
        cores_dir = self.config.get_emulator_path("retroarch", "cores")
        if not cores_dir:
            return set()
        path = Path(cores_dir).expanduser()
        if not path.is_dir():
            return set()
        return {item.name.casefold() for item in path.glob("*_libretro.dll") if item.is_file()}

    def _refresh_installed_markers(self) -> None:
        """Atualiza [INSTALADO]/[NOVO] sem consultar a rede e sem alterar seleção."""
        if not hasattr(self, "core_list"):
            return
        installed = self._installed_core_filenames()
        for index in range(self.core_list.count()):
            item = self.core_list.item(index)
            filename = str(item.data(Qt.ItemDataRole.UserRole) or "")
            base = item.text()
            for prefix in ("[INSTALADO] ", "[NOVO] ", "[ATUALIZAÇÃO] "):
                if base.startswith(prefix):
                    base = base[len(prefix):]
                    break
            marker = "[INSTALADO] " if filename.removesuffix(".zip").casefold() in installed else "[NOVO] "
            item.setText(marker + base)

    def refresh_cores(self) -> None:
        """Atualiza o índice oficial e identifica os cores existentes pelo nome exato da DLL."""
        try:
            mode, version = self._channel()
            channel = RetroArchDownloadService.channel(mode, version)
            service = RetroArchDownloadService()
            cores = service.list_cores(channel)
            self.core_list.clear()
            installed = self._installed_core_filenames()
            installed_count = 0
            new_count = 0
            for core in cores:
                item = QListWidgetItem()
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setData(Qt.ItemDataRole.UserRole, core.filename)
                dll_filename = core.filename.removesuffix(".zip")
                is_installed = dll_filename.casefold() in installed
                marker = "[INSTALADO] " if is_installed else "[NOVO] "
                installed_count += int(is_installed)
                new_count += int(not is_installed)
                item.setText(f"{marker}{core.core_name} | {core.filename} | {core.date} | CRC {core.crc32}")
                self.core_list.addItem(item)
            self._append_log(f"CORES | índice carregado={len(cores)} | instalados={installed_count} | novos={new_count} | diretório={self.config.get_emulator_path('retroarch', 'cores') or 'não configurado'}")
        except Exception as exc:
            self._append_log(f"ERRO CORES | {type(exc).__name__}: {exc}")

    def update_installed_cores(self) -> None:
        """Consulta o índice oficial e exibe somente cores instalados com CRC diferente.

        Esta operação não baixa arquivos. Os cores desatualizados ficam selecionados
        para confirmação explícita pelo botão 'Instalar / atualizar selecionados'.
        """
        try:
            cores_dir = self.config.get_emulator_path("retroarch", "cores")
            if not cores_dir or not Path(cores_dir).expanduser().is_dir():
                self._append_log("AVISO | diretório de cores do RetroArch não configurado ou inexistente.")
                return

            mode, version = self._channel()
            channel = RetroArchDownloadService.channel(mode, version)
            service = RetroArchDownloadService(log_callback=self._append_log)
            comparison = service.compare_installed_cores(channel, Path(cores_dir).expanduser())

            self.core_list.clear()
            updates = [entry for entry in comparison if entry.needs_update]
            current = sum(1 for entry in comparison if entry.is_current)
            unknown = len(comparison) - len(updates) - current

            for entry in updates:
                item = QListWidgetItem()
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                item.setData(Qt.ItemDataRole.UserRole, f"{entry.core_name}_libretro.dll.zip")
                item.setText(
                    f"[ATUALIZAÇÃO] {entry.core_name} | "
                    f"CRC local {entry.local_crc32} → remoto {entry.remote_crc32}"
                )
                self.core_list.addItem(item)

            self._append_log(
                f"ATUALIZAÇÕES | instalados={len(comparison)} | "
                f"atualizações={len(updates)} | atualizados={current} | "
                f"sem correspondência={unknown}"
            )
            if not updates:
                self._append_log("ATUALIZAÇÕES | nenhum core instalado necessita de atualização.")
        except Exception as exc:
            self._append_log(f"ERRO ATUALIZAÇÕES | {type(exc).__name__}: {exc}")

    def _checked_core_filenames(self) -> list[str]:
        """Retorna os arquivos de core atualmente marcados."""
        return [
            self.core_list.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self.core_list.count())
            if self.core_list.item(index).checkState() == Qt.CheckState.Checked
        ]

    def select_all_cores(self) -> None:
        """Marca todos os cores exibidos."""
        for index in range(self.core_list.count()):
            self.core_list.item(index).setCheckState(Qt.CheckState.Checked)

    def clear_core_selection(self) -> None:
        """Desmarca todos os cores exibidos."""
        for index in range(self.core_list.count()):
            self.core_list.item(index).setCheckState(Qt.CheckState.Unchecked)

    def install_selected_cores(self) -> None:
        """Baixa e instala todos os cores marcados."""
        selected = self._checked_core_filenames()
        if not selected:
            self._append_log("AVISO | marque pelo menos um core na lista.")
            return
        self._start_worker("cores", selected)

    def _start_worker(self, operation: str, selected_cores: list[str] | None = None) -> None:
        """Cria o worker assíncrono para a operação solicitada."""
        if self._thread is not None and self._thread.isRunning():
            self._append_log("AVISO | já existe uma operação em execução.")
            return
        mode, version = self._channel()
        destination = self._destination()
        self._thread = QThread(self)
        self._worker = RetroArchDownloadWorker(
            operation=operation,
            service=RetroArchDownloadService(log_callback=self._append_log),
            channel=RetroArchDownloadService.channel(mode, version),
            destination=destination,
            selected_cores=selected_cores or [],
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.log.connect(self._append_log)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()
        self._update_busy_state()

    @Slot(int, int)
    def _on_progress(self, current: int, total: int) -> None:
        """Atualiza a barra de progresso."""
        self.progress.setRange(0, total)
        self.progress.setValue(current)

    @Slot(bool, str)
    def _on_worker_finished(self, success: bool, message: str) -> None:
        """Registra resultado da operação e atualiza a tela."""
        self._append_log(f"RESULTADO | sucesso={success} | {message}")
        self._refresh_installed_markers()
        self._update_busy_state()

    def _update_busy_state(self) -> None:
        """Bloqueia ações concorrentes enquanto uma operação estiver ativa."""
        busy = bool(self._thread and self._thread.isRunning())
        for widget in (
            self.install_button,
            self.update_button,
            self.core_refresh_button,
            self.core_install_button,
            self.core_update_installed_button,
            self.select_all_button,
            self.clear_button,
        ):
            widget.setEnabled(not busy)

    def _append_log(self, message: str) -> None:
        """Adiciona uma linha ao log visual."""
        self.log.appendPlainText(str(message))

    def open_directories(self) -> None:
        """Abre a tela de diretórios do emulador."""
        if self.parent_window and hasattr(self.parent_window, "open_emulator_directories"):
            self.parent_window.open_emulator_directories("retroarch")

    def open_catalog(self) -> None:
        """Abre o catálogo de cores do RetroArch."""
        if self.parent_window and hasattr(self.parent_window, "open_retroarch_catalog"):
            self.parent_window.open_retroarch_catalog()

    def open_settings(self) -> None:
        """Abre as configurações do RetroArch."""
        if self.parent_window and hasattr(self.parent_window, "open_emulator_settings"):
            self.parent_window.open_emulator_settings("retroarch")
