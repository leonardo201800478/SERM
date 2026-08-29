"""Home do RetroArch: instalação, atualização e gerenciamento de cores."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from app.config.app_config import AppConfig
from app.core.services.retroarch_download_service import RetroArchDownloadService
from app.gui.widgets.retroarch_download_worker import RetroArchDownloadWorker


class RetroArchHomeTab(QWidget):
    """Gerencia RetroArch e cores libretro pelo Buildbot oficial."""

    _GREEN = QColor("#2e8b57")
    _YELLOW = QColor("#b8860b")
    _RED = QColor("#b22222")
    _MUTED = QColor("#777777")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = getattr(parent, "config", None) or AppConfig()
        self._thread: QThread | None = None
        self._worker: RetroArchDownloadWorker | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Monta a Home sem atalhos legados sem implementação."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("RetroArch")
        title.setObjectName("retroarchTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        status = QGroupBox("Estado da instalação")
        form = QFormLayout(status)
        self.status_label = QLabel()
        self.path_label = QLabel()
        self.config_label = QLabel()
        self.cores_label = QLabel()
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
        actions.addStretch()
        layout.addWidget(operations)

        cores_group = QGroupBox("Cores libretro")
        cores_layout = QVBoxLayout(cores_group)
        core_actions = QHBoxLayout()
        self.core_refresh_button = QPushButton("Atualizar lista")
        self.core_refresh_button.clicked.connect(self.refresh_cores)
        core_actions.addWidget(self.core_refresh_button)
        self.core_install_button = QPushButton("Instalar / atualizar selecionados")
        self.core_install_button.clicked.connect(self.install_selected_cores)
        core_actions.addWidget(self.core_install_button)
        self.core_update_installed_button = QPushButton("Verificar atualizações")
        self.core_update_installed_button.setToolTip("Compara CRC dos cores instalados com o Buildbot e seleciona somente os desatualizados.")
        self.core_update_installed_button.clicked.connect(self.update_installed_cores)
        core_actions.addWidget(self.core_update_installed_button)
        self.select_all_button = QPushButton("Selecionar tudo")
        self.select_all_button.clicked.connect(self.select_all_cores)
        core_actions.addWidget(self.select_all_button)
        self.clear_button = QPushButton("Limpar seleção")
        self.clear_button.clicked.connect(self.clear_core_selection)
        core_actions.addWidget(self.clear_button)
        core_actions.addStretch()
        cores_layout.addLayout(core_actions)

        self.core_summary = QLabel("Nenhuma lista carregada")
        self.core_summary.setObjectName("coreSummary")
        cores_layout.addWidget(self.core_summary)

        self.core_list = QListWidget()
        self.core_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.core_list.setAlternatingRowColors(True)
        cores_layout.addWidget(self.core_list, 1)
        layout.addWidget(cores_group, 1)

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        log_label = QLabel("Log do downloader")
        log_label.setObjectName("sectionLabel")
        layout.addWidget(log_label)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.log.setPlaceholderText("As operações do RetroArch aparecerão aqui…")
        layout.addWidget(self.log, 1)

        self.setStyleSheet(
            """
            #retroarchTitle { font-size: 22px; font-weight: 700; padding: 4px; }
            #coreSummary { font-weight: 600; padding: 2px 0; }
            #sectionLabel { font-weight: 600; }
            QGroupBox { font-weight: 600; }
            QPushButton { padding: 6px 10px; }
            QProgressBar { min-height: 18px; }
            QPlainTextEdit { font-family: Consolas; font-size: 10px; }
            """
        )

    def refresh(self) -> None:
        """Atualiza o diagnóstico local sem consultar a rede."""
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
            self.status_label.setStyleSheet("color:#2e8b57;font-weight:bold;")
        elif root:
            self.status_label.setText("● Diretório configurado; executável não localizado")
            self.status_label.setStyleSheet("color:#b8860b;font-weight:bold;")
        else:
            self.status_label.setText("● Não configurado")
            self.status_label.setStyleSheet("color:#777;font-weight:bold;")
        self._refresh_installed_markers()
        self._update_core_summary()
        self._update_busy_state()

    def _channel_changed(self, value: str) -> None:
        """Habilita Stable e consulta versões somente quando necessário."""
        is_stable = value.casefold() == "stable"
        self.stable_combo.setEnabled(is_stable)
        if is_stable and self.stable_combo.count() == 0:
            self.refresh_stable_versions()

    def refresh_stable_versions(self) -> None:
        """Consulta versões Stable diretamente no Buildbot oficial."""
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
        """Atualiza RetroArch preservando configuração, saves e states."""
        if not self.config.retroarch_dir:
            self._append_log("ERRO | selecione o retroarch.exe em Diretórios antes de atualizar.")
            return
        self._start_worker("update")

    def _installed_core_filenames(self) -> set[str]:
        """Retorna os nomes das DLLs libretro instaladas."""
        cores_dir = self.config.get_emulator_path("retroarch", "cores")
        if not cores_dir:
            return set()
        path = Path(cores_dir).expanduser()
        if not path.is_dir():
            return set()
        return {item.name.casefold() for item in path.glob("*_libretro.dll") if item.is_file()}

    def _refresh_installed_markers(self) -> None:
        """Atualiza o marcador de instalação sem consultar a rede."""
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

    def _add_core_item(self, text: str, filename: str, checked: bool, color: QColor | None = None) -> None:
        """Adiciona um core à lista com estado e destaque visual opcionais."""
        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        item.setData(Qt.ItemDataRole.UserRole, filename)
        if color is not None:
            item.setForeground(color)
        self.core_list.addItem(item)

    def refresh_cores(self) -> None:
        """Atualiza o índice oficial e exibe todos os cores publicados."""
        try:
            mode, version = self._channel()
            channel = RetroArchDownloadService.channel(mode, version)
            service = RetroArchDownloadService(log_callback=self._append_log)
            cores = service.list_cores(channel)
            installed = self._installed_core_filenames()
            self.core_list.clear()
            installed_count = 0
            new_count = 0
            for core in cores:
                dll_filename = core.filename.removesuffix(".zip")
                is_installed = dll_filename.casefold() in installed
                installed_count += int(is_installed)
                new_count += int(not is_installed)
                marker = "[INSTALADO] " if is_installed else "[NOVO] "
                self._add_core_item(
                    f"{marker}{core.core_name} | {core.filename} | {core.date} | CRC {core.crc32}",
                    core.filename,
                    False,
                    self._GREEN if is_installed else self._MUTED,
                )
            self.core_summary.setText(f"{len(cores)} publicados  •  {installed_count} instalados  •  {new_count} novos")
            self._append_log(f"CORES | índice carregado={len(cores)} | instalados={installed_count} | novos={new_count} | diretório={self.config.get_emulator_path('retroarch', 'cores') or 'não configurado'}")
        except Exception as exc:
            self._append_log(f"ERRO CORES | {type(exc).__name__}: {exc}")

    def update_installed_cores(self) -> None:
        """Lista somente cores instalados com CRC divergente e os seleciona."""
        try:
            cores_dir = self.config.get_emulator_path("retroarch", "cores")
            if not cores_dir or not Path(cores_dir).expanduser().is_dir():
                self._append_log("AVISO | diretório de cores do RetroArch não configurado ou inexistente.")
                return
            mode, version = self._channel()
            channel = RetroArchDownloadService.channel(mode, version)
            service = RetroArchDownloadService(log_callback=self._append_log)
            cores = service.list_cores(channel)
            comparison = service.compare_installed_cores(cores, Path(cores_dir).expanduser())
            by_filename = {core.filename.removesuffix(".zip").casefold(): core for core in cores}
            updates = [entry for entry in comparison if entry.needs_update and entry.path.name.casefold() in by_filename]
            current = sum(1 for entry in comparison if entry.is_current)
            unknown = sum(1 for entry in comparison if entry.remote_crc32 is None)

            self.core_list.clear()
            for entry in updates:
                remote = by_filename[entry.path.name.casefold()]
                self._add_core_item(
                    f"[ATUALIZAÇÃO] {remote.core_name} | CRC local {entry.local_crc32} → remoto {entry.remote_crc32}",
                    remote.filename,
                    True,
                    self._YELLOW,
                )
            self.core_summary.setText(f"{len(updates)} atualizações disponíveis  •  {current} atualizados  •  {unknown} sem correspondência")
            self._append_log(f"ATUALIZAÇÕES | instalados={len(comparison)} | atualizações={len(updates)} | atualizados={current} | sem correspondência={unknown}")
            if not updates:
                self._append_log("ATUALIZAÇÕES | nenhum core instalado necessita de atualização.")
        except Exception as exc:
            self._append_log(f"ERRO ATUALIZAÇÕES | {type(exc).__name__}: {exc}")

    def _checked_core_filenames(self) -> list[str]:
        """Retorna os arquivos de core atualmente marcados."""
        return [
            str(self.core_list.item(index).data(Qt.ItemDataRole.UserRole))
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
        self._start_worker("core", selected)

    def _start_worker(self, operation: str, selected_cores: list[str] | None = None) -> None:
        """Cria e gerencia um worker assíncrono por operação."""
        if self._thread is not None and self._thread.isRunning():
            self._append_log("AVISO | já existe uma operação em execução.")
            return
        mode, version = self._channel()
        self._thread = QThread(self)
        self._thread.setObjectName("RetroArchDownloadThread")
        self._worker = RetroArchDownloadWorker(
            operation=operation,
            destination=self._destination(),
            mode=mode,
            stable_version=version,
            core_filenames=selected_cores or [],
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.log_message.connect(self._append_log)
        self._worker.status.connect(self._on_status)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._on_worker_failed)
        self._worker.failed.connect(lambda _message: self._thread.quit())
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()
        self._update_busy_state()

    @Slot(str)
    def _on_status(self, message: str) -> None:
        """Exibe o estado corrente da operação."""
        self._append_log(f"STATUS | {message}")

    @Slot(str, str, str)
    def _on_worker_finished(self, operation: str, value: str, path: str) -> None:
        """Registra conclusão normal e prepara a GUI para nova operação."""
        self._append_log(f"RESULTADO | operação={operation} | valor={value} | caminho={path}")
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.status_label.setText("● Pronto")
        self.status_label.setStyleSheet("color:#2e8b57;font-weight:bold;")
        self._refresh_installed_markers()
        self._update_core_summary()

    @Slot(str)
    def _on_worker_failed(self, message: str) -> None:
        """Registra falha controlada sem deixar a GUI presa em execução."""
        self._append_log(f"ERRO WORKER | {message}")
        self.progress.setRange(0, 100)
        self.status_label.setText("● Pronto | última operação falhou")
        self.status_label.setStyleSheet("color:#b8860b;font-weight:bold;")

    @Slot()
    def _on_thread_finished(self) -> None:
        """Libera o worker/thread e restaura todos os controles."""
        thread = self._thread
        self._worker = None
        self._thread = None
        if thread is not None:
            thread.deleteLater()
        self._update_busy_state()

    @Slot(int, int)
    def _on_progress(self, current: int, total: int) -> None:
        """Atualiza a barra de progresso."""
        if total <= 0:
            self.progress.setRange(0, 0)
            return
        self.progress.setRange(0, total)
        self.progress.setValue(max(0, min(current, total)))

    def _update_core_summary(self) -> None:
        """Atualiza o contador visual com base na lista atualmente exibida."""
        if not hasattr(self, "core_list"):
            return
        count = self.core_list.count()
        checked = sum(
            self.core_list.item(index).checkState() == Qt.CheckState.Checked
            for index in range(count)
        )
        if count:
            self.core_summary.setText(f"{count} cores exibidos  •  {checked} selecionados")

    def _update_busy_state(self) -> None:
        """Bloqueia operações somente enquanto a thread realmente estiver ativa."""
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
        self.channel_combo.setEnabled(not busy)
        self.stable_combo.setEnabled(not busy and self.channel_combo.currentText().casefold() == "stable")

    def _append_log(self, message: str) -> None:
        """Adiciona uma linha ao log visual."""
        self.log.appendPlainText(str(message))
