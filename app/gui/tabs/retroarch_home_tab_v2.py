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
            for prefix in ("[INSTALADO] ", "[NOVO] "):
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
                # RetroArchCoreInfo expõe o arquivo publicado como `filename`.
                # O índice usa <core>_libretro.dll.zip; a instalação contém <core>_libretro.dll.
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
        if not self.config.retroarch_dir:
            self._append_log("ERRO | selecione o retroarch.exe em Diretórios antes de instalar cores.")
            return
        mode, version = self._channel()
        self._start_worker("core", core_filenames=selected, mode=mode, stable_version=version)

    def update_installed_cores(self) -> None:
        """Escaneia a instalação, marca somente [NOVO] e instala apenas os cores ausentes."""
        if not self.config.retroarch_dir:
            self._append_log("ERRO | selecione o retroarch.exe em Diretórios antes de atualizar cores.")
            return
        if self.core_list.count() == 0:
            self.refresh_cores()
        self.clear_core_selection()
        selected: list[str] = []
        for index in range(self.core_list.count()):
            item = self.core_list.item(index)
            if item.text().startswith("[NOVO] "):
                item.setCheckState(Qt.CheckState.Checked)
                selected.append(str(item.data(Qt.ItemDataRole.UserRole)))
        if not selected:
            self._append_log("CORES | nenhum core novo para instalar. Todos os cores do índice já estão instalados.")
            return
        self._append_log(f"CORES | novos selecionados automaticamente={len(selected)}")
        mode, version = self._channel()
        self._start_worker("core", core_filenames=selected, mode=mode, stable_version=version)

    def _start_worker(self, operation: str, *, core_filename: str | None = None, core_filenames: list[str] | None = None, mode: str | None = None, stable_version: str | None = None) -> None:
        """Cria o worker de download e mantém a GUI responsiva."""
        if self._thread is not None:
            return
        selected_mode, selected_version = self._channel()
        self._thread = QThread(self)
        self._worker = RetroArchDownloadWorker(operation, self._destination(), mode=mode or selected_mode, stable_version=stable_version if mode else selected_version, core_filename=core_filename, core_filenames=core_filenames)
        self._worker.moveToThread(self._thread)
        self._worker.progress.connect(self._on_progress)
        self._worker.status.connect(self._on_status)
        self._worker.log_message.connect(self._append_log)
        self._worker.finished.connect(self._finished)
        self._worker.failed.connect(self._failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.failed.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread_finished)
        self._thread.finished.connect(self._thread.deleteLater)
        self.progress.setRange(0, 0)
        self._update_busy_state()
        self._thread.started.connect(self._worker.run)
        self._thread.start()

    @Slot(int, int)
    def _on_progress(self, received: int, total: int) -> None:
        """Atualiza progresso do download."""
        if total > 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(min(100, int(received * 100 / total)))
        else:
            self.progress.setRange(0, 0)

    @Slot(str)
    def _on_status(self, message: str) -> None:
        """Exibe a etapa corrente do worker."""
        self.status_label.setText(f"● {message}")
        self.status_label.setStyleSheet("color:#e5c454;font-weight:bold;")

    @Slot(str, str, str)
    def _finished(self, kind: str, value: str, path: str) -> None:
        """Registra conclusão e atualiza as sessões relacionadas."""
        self._append_log(f"SUCESSO | tipo={kind} | valor={value} | caminho={path}")
        self.refresh()
        self._refresh_installed_markers()
        catalog = getattr(self.parent_window, "retroarch_catalog_tab", None)
        if catalog is not None:
            catalog.refresh()

    @Slot(str)
    def _failed(self, message: str) -> None:
        """Registra erro completo sem encerrar a aplicação."""
        self._append_log(message)
        self.status_label.setText("● Erro no downloader")
        self.status_label.setStyleSheet("color:#e05a5a;font-weight:bold;")

    @Slot()
    def _thread_finished(self) -> None:
        """Libera thread e restaura controles."""
        self._thread = None
        self._worker = None
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self._update_busy_state()

    def _update_busy_state(self) -> None:
        """Desabilita operações concorrentes durante um download."""
        busy = self._thread is not None
        for button in (self.install_button, self.update_button, self.core_refresh_button, self.core_install_button, self.core_update_installed_button, self.select_all_button, self.clear_button):
            button.setEnabled(not busy)

    def _append_log(self, message: str) -> None:
        """Adiciona uma linha ao log visual."""
        self.log.appendPlainText(str(message).rstrip())
        self.log.ensureCursorVisible()

    def _activate(self, attribute: str) -> None:
        """Seleciona uma aba principal da janela quando disponível."""
        window = self.parent_window
        widget = getattr(window, attribute, None)
        tab_widget = getattr(window, "tab_widget", None)
        if widget is not None and tab_widget is not None:
            tab_widget.setCurrentWidget(widget)

    def open_directories(self) -> None:
        """Abre a sessão dedicada de diretórios do RetroArch."""
        self._activate("retroarch_directories_tab")

    def open_catalog(self) -> None:
        """Abre a sessão de catálogo de cores."""
        self._activate("retroarch_catalog_tab")

    def open_settings(self) -> None:
        """Abre a sessão geral de configurações dos emuladores."""
        self._activate("emulator_settings_tab")
        settings = getattr(self.parent_window, "emulator_settings_tab", None)
        if settings is not None and hasattr(settings, "select_emulator"):
            settings.select_emulator("retroarch")

    def closeEvent(self, event) -> None:
        """Espera o worker ativo antes de destruir a sessão."""
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(10000)
        event.accept()


__all__ = ["RetroArchHomeTab"]
