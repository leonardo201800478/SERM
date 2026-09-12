"""Home V2 baseada nos componentes funcionais originais do SERM."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QListWidgetItem,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from ..services.retroarch_catalog_service import RetroArchCatalogService
from .emulator_home import EmulatorHomePage, _Worker


class HomePage(EmulatorHomePage):
    """Expose uma Home completa, compacta e sem consoles duplicados."""

    CORE_MAX_ATTEMPTS = 3
    CORE_SETTINGS = ("SERM", "SERM V2")

    def __init__(self, parent: QWidget | None = None) -> None:
        self._core_filter_state = self._load_core_filter_state()
        self._core_current_filename: str | None = None
        self._core_destination: Path | None = None
        self._core_queue_with_channels: list[tuple[str, str]] = []
        self._retro_continuation = None
        self._retro_operation_ok = False
        self._core_catalog_cache = None
        self._core_catalog_source = ""
        super().__init__(parent)
        self._modernize_home_ui()

    @staticmethod
    def _settings() -> QSettings:
        """Retorna o armazenamento persistente das preferências da Home."""
        return QSettings(*HomePage.CORE_SETTINGS)

    @classmethod
    def _load_core_filter_state(cls) -> dict[str, bool]:
        """Restaura os filtros do catálogo entre execuções do SERM."""
        settings = cls._settings()
        return {
            "include_beta": settings.value("retroarch/catalog/include_nightly", False, type=bool),
            "current_only": settings.value("retroarch/catalog/current_only", True, type=bool),
            "hide_games": settings.value("retroarch/catalog/hide_games", True, type=bool),
        }

    def _persist_core_filter_state(self) -> None:
        """Persiste os filtros imediatamente, sem depender do encerramento do processo."""
        settings = self._settings()
        settings.setValue("retroarch/catalog/include_nightly", self.core_include_beta.isChecked())
        settings.setValue("retroarch/catalog/current_only", self.core_current_only.isChecked())
        settings.setValue("retroarch/catalog/hide_games", self.core_hide_games.isChecked())
        settings.sync()
        self._core_filter_state = {
            "include_beta": self.core_include_beta.isChecked(),
            "current_only": self.core_current_only.isChecked(),
            "hide_games": self.core_hide_games.isChecked(),
        }

    def _retroarch_tab(self) -> QWidget:
        """Adiciona filtros persistentes e uma listagem mais limpa ao catálogo."""
        page = super()._retroarch_tab()
        layout = page.layout()
        if isinstance(layout, QVBoxLayout):
            filters = QGroupBox("Catálogo de cores")
            row = QHBoxLayout(filters)
            row.setContentsMargins(8, 7, 8, 7)
            row.setSpacing(12)
            self.core_include_beta = QCheckBox("Incluir Nightly adicionais")
            self.core_current_only = QCheckBox("Somente cores atuais")
            self.core_hide_games = QCheckBox("Ocultar jogos / engines")

            self.core_include_beta.setChecked(self._core_filter_state["include_beta"])
            self.core_current_only.setChecked(self._core_filter_state["current_only"])
            self.core_hide_games.setChecked(self._core_filter_state["hide_games"])

            for widget in (self.core_include_beta, self.core_current_only, self.core_hide_games):
                row.addWidget(widget)
                widget.stateChanged.connect(self._core_filters_changed)
            row.addStretch()
            layout.insertWidget(7, filters)
        return page

    def _modernize_home_ui(self) -> None:
        """Remove redundâncias visuais e aplica a densidade moderna da Home."""
        for widget_name in ("log_view", "retro_log"):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.hide()
                widget.setMaximumHeight(0)

        for label in self.findChildren(type(self.seven_zip)):
            if label.text() in {"Log detalhado da instalação", "Log RetroArch"}:
                label.hide()

        for button in self.findChildren(QPushButton):
            if button.text().strip() == "📁 Configurar diretórios":
                button.hide()

        for progress in self.findChildren(QProgressBar):
            progress.setTextVisible(False)
            progress.setFixedHeight(8)

        for frame in self.findChildren(QFrame):
            frame.setStyleSheet(
                "QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                "stop:0 #111827,stop:1 #0d1422);border:1px solid #26344e;"
                "border-radius:10px;}"
            )

        if hasattr(self, "core_list"):
            self.core_list.setObjectName("coreList")
            self.core_list.setUniformItemSizes(True)
            self.core_list.setSpacing(1)
            self.core_list.setAlternatingRowColors(True)
            self.core_list.setStyleSheet(
                "QListWidget#coreList{background:#0b1220;border:1px solid #24324a;"
                "border-radius:9px;padding:4px;}"
                "QListWidget#coreList::item{padding:7px 10px;border:0;"
                "border-bottom:1px solid #1b2639;min-height:30px;}"
                "QListWidget#coreList::item:hover{background:#131f32;}"
                "QListWidget#coreList::item:selected{background:#193047;"
                "border-left:3px solid #5bc0eb;color:#eef7ff;}"
            )

    def _save_core_filter_state(self) -> None:
        """Compatibilidade: persiste as últimas seleções."""
        self._persist_core_filter_state()

    def _core_filters_changed(self, _state: int) -> None:
        """Aplica os filtros em memória sem nova requisição HTTP."""
        self._persist_core_filter_state()
        if self.worker is not None:
            return
        if self._core_catalog_cache is None:
            self._append_retro_log(
                "FILTRO | catálogo ainda não carregado; use 'Buscar cores' para consultar o Buildbot."
            )
            return
        self._render_core_catalog(self._filtered_cached_cores())

    def _filtered_cached_cores(self):
        """Filtra o snapshot já obtido pelo serviço de catálogo."""
        cores = tuple(self._core_catalog_cache or ())
        return RetroArchCatalogService.filter_snapshot(
            cores,
            current_only=self.core_current_only.isChecked(),
            hide_games=self.core_hide_games.isChecked(),
        )

    def refresh_cores(self) -> None:
        """Consulta um snapshot coerente e aplica os filtros somente depois."""
        if self.worker is not None:
            self._append_retro_log("CATÁLOGO | operação RetroArch já em execução.")
            return
        self._save_core_filter_state()
        try:
            snapshot, source = RetroArchCatalogService.fetch(
                self.retroarch,
                include_nightly=self.core_include_beta.isChecked(),
            )
            self._core_catalog_cache = tuple(snapshot)
            self._core_catalog_source = source
            self._render_core_catalog(self._filtered_cached_cores())
            self._append_retro_log(
                f"CATÁLOGO | fonte={source} | atuais={self.core_current_only.isChecked()} | "
                f"sem jogos/engines={self.core_hide_games.isChecked()} | cores={len(snapshot)}"
            )
        except Exception as exc:  # noqa: BLE001
            self._append_retro_log(f"ERRO CORES | {type(exc).__name__}: {exc}")
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "RetroArch", str(exc))

    def _render_core_catalog(self, cores) -> None:
        """Renderiza cores com estado, canal e metadados em uma lista limpa."""
        _, _, destination = self.retroarch.discover()
        comparisons = (
            self.retroarch.compare_installed_cores(cores, destination)
            if destination and destination.is_dir()
            else []
        )
        state_map = {path.name.casefold(): state for path, _, state in comparisons}
        installed_names = {path.name.casefold() for path, _, _ in comparisons}
        self.core_list.blockSignals(True)
        self.core_list.clear()
        self.core_items.clear()
        installed_count = update_count = 0
        for core in cores:
            key = core.filename.removesuffix(".zip").casefold()
            state = state_map.get(key, "new")
            installed_count += key in installed_names
            update_count += state == "update"
            status = {
                "current": "Atualizado",
                "update": "Atualização disponível",
                "new": "Não instalado",
                "unknown": "Fora do catálogo",
            }.get(state, "Não instalado")
            channel = "Stable" if core.channel.casefold() == "stable" else "Nightly"
            item = QListWidgetItem(
                f"{core.core_name}   ·   {status}   ·   {channel}   ·   {core.date}   ·   CRC {core.crc32}"
            )
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, core.filename)
            item.setData(Qt.ItemDataRole.UserRole + 1, state)
            item.setData(Qt.ItemDataRole.UserRole + 2, core.channel)
            item.setToolTip(
                f"{core.core_name}\nCanal: {channel}\nData: {core.date}\nCRC32: {core.crc32}\n"
                f"Arquivo: {core.filename}"
            )
            if state == "current":
                item.setForeground(QBrush(QColor("#9ad7b5")))
            elif state == "update":
                item.setForeground(QBrush(QColor("#f0cf8b")))
            else:
                item.setForeground(QBrush(QColor("#cbd5e1")))
            self.core_list.addItem(item)
            self.core_items[core.filename] = item
        self.core_list.blockSignals(False)
        new_count = len(cores) - installed_count
        self.core_summary.setText(
            f"{len(cores)} cores · {installed_count} instalados · "
            f"{update_count} atualizações · {new_count} novos"
        )
        self._update_core_summary()

    def install_selected_cores(self) -> None:
        """Enfileira cores e processa cada item sequencialmente, com até três tentativas."""
        if self.worker:
            self._append_retro_log("FILA | já existe uma operação RetroArch em execução.")
            return
        _, _, destination = self.retroarch.discover()
        if destination is None:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(
                self, "RetroArch", "Configure o diretório do RetroArch primeiro."
            )
            return
        selected = [
            (
                str(self.core_list.item(i).data(Qt.ItemDataRole.UserRole)),
                str(self.core_list.item(i).data(Qt.ItemDataRole.UserRole + 2) or "stable"),
            )
            for i in range(self.core_list.count())
            if self.core_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        if not selected:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(self, "RetroArch", "Nenhum core foi selecionado.")
            return
        self._core_queue_with_channels = selected
        self._core_destination = Path(destination).resolve()
        self._core_current_filename = None
        self.core_list.setEnabled(False)
        self._append_retro_log(
            f"FILA | {len(self._core_queue_with_channels)} core(s) | processamento sequencial iniciado"
        )
        self._install_next_core(self._core_destination)

    def _install_next_core(self, destination: Path) -> None:
        """Retira o próximo core da fila e inicia suas tentativas."""
        if not self._core_queue_with_channels:
            self._core_current_filename = None
            self._core_destination = None
            self.core_list.setEnabled(True)
            self._append_retro_log("FILA | todos os cores selecionados foram processados")
            self._update_core_summary()
            self.refresh()
            return
        filename, catalog_channel = self._core_queue_with_channels.pop(0)
        self._core_current_filename = filename
        download_channel = "nightly" if catalog_channel.casefold() == "stable" else catalog_channel
        self._append_retro_log(
            f"FILA | iniciando {filename} | catálogo={catalog_channel} | download={download_channel} | "
            f"restantes={len(self._core_queue_with_channels)} | máximo={self.CORE_MAX_ATTEMPTS} tentativas"
        )
        self._start_retro(
            lambda progress, log, f=filename, d=destination, c=download_channel: (
                self._install_core_with_retries(f, d, c, progress, log)
            ),
            continuation=lambda f=filename: self._finish_core_queue_item(f, destination),
        )

    def _install_core_with_retries(
        self, filename: str, destination: Path, channel: str, progress, log
    ):
        """Tenta baixar, validar e instalar um core até três vezes."""
        last_error: Exception | None = None
        for attempt in range(1, self.CORE_MAX_ATTEMPTS + 1):
            try:
                log(f"CORE | {filename} | canal={channel} | tentativa={attempt}/{self.CORE_MAX_ATTEMPTS}")
                return self.retroarch.install_core(
                    filename, destination, channel=channel, progress=progress, log=log
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                log(
                    f"CORE ERRO | {filename} | tentativa={attempt}/{self.CORE_MAX_ATTEMPTS} | "
                    f"{type(exc).__name__}: {exc}"
                )
                if attempt < self.CORE_MAX_ATTEMPTS:
                    log(f"CORE | {filename} | repetindo operação completa")
        assert last_error is not None
        raise last_error

    def _finish_core_queue_item(self, filename: str, destination: Path) -> None:
        """Desmarca o item processado, inclusive após as três tentativas falharem."""
        item = self._find_core_item(filename)
        if item is not None:
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole + 1, "processed")
        self._append_retro_log(
            f"FILA | {filename} | processado | seleção removida | próximos={len(self._core_queue_with_channels)}"
        )
        self._update_core_summary()
        self._install_next_core(destination)

    def _find_core_item(self, filename: str) -> QListWidgetItem | None:
        """Localiza um core na lista pelo nome do arquivo."""
        for index in range(self.core_list.count()):
            item = self.core_list.item(index)
            if str(item.data(Qt.ItemDataRole.UserRole) or "").casefold() == filename.casefold():
                return item
        return None

    def _start_retro(self, operation, continuation=None) -> None:
        """Executa uma operação RetroArch e aguarda o encerramento da thread."""
        if self.worker:
            return
        self.retro_progress.show()
        self._retro_continuation = continuation
        self._retro_operation_ok = False
        self.worker = _Worker(operation, self)
        self.worker.progress.connect(self._retro_progress)
        self.worker.log.connect(self._append_retro_log)
        self.worker.done.connect(self._retro_done)
        self.worker.error.connect(self._retro_error)
        self.worker.finished.connect(self._retro_worker_finished)
        self.worker.start()

    def _retro_done(self, result) -> None:
        """Registra sucesso da operação."""
        self._retro_operation_ok = True
        self._append_retro_log(f"OK | {result}")

    def _retro_error(self, message: str) -> None:
        """Registra a falha final da operação."""
        self._retro_operation_ok = False
        self._append_retro_log(f"ERRO | {message}")

    def _retro_worker_finished(self) -> None:
        """Libera o worker e inicia o próximo item da fila somente depois do término."""
        continuation = self._retro_continuation
        ok = self._retro_operation_ok
        self._retro_continuation = None
        self.worker = None
        self.retro_progress.hide()
        self.refresh()
        if continuation:
            continuation()
        elif not ok:
            self._append_retro_log("RETROARCH | operação encerrada com erro")

    def configure(self, key: str) -> None:
        """Seleciona somente o diretório de instalação."""
        selected = QFileDialog.getExistingDirectory(
            self, f"Diretório de instalação — {self.LABELS[key]}", str(Path.home())
        )
        if not selected:
            return
        paths = self._load_paths()
        paths[key] = Path(selected).resolve()
        self._save_paths(paths)
        self.manager.roots = paths
        self.refresh()

    def refresh_status(self) -> None:
        """Compatibility entry point preservado da V1."""
        self.refresh()

    def update_all_emulators(self) -> None:
        """Compatibility entry point para atualização em lote."""
        self.update_all()

    def install_emulator(self, emulator: str) -> None:
        """Compatibility entry point para instalar um emulador."""
        self.install(emulator)

    def clear_install_log(self) -> None:
        """Limpa o console de instalação; o histórico principal fica no dock global."""
        log_view = getattr(self, "log_view", None)
        if log_view is not None:
            log_view.clear()

    def open_official_site(self, key: str) -> None:
        """Abre o repositório oficial do emulador."""
        import webbrowser

        url = self.SITES.get(key)
        if url:
            webbrowser.open(url)

    def _done(self, key: str, result, continuation=None) -> None:
        """Persiste instalação, executável e versão separadamente."""
        paths = self._load_paths()
        installation = paths.get(key)
        if installation is None:
            installation = Path(result.executable).parent
            paths[key] = installation
        paths[f"{key}_exe"] = Path(result.executable).resolve()
        paths[f"{key}_version"] = Path(str(result.version))
        self._save_paths(paths)
        self._append_log(
            f"SUCESSO | {self.LABELS[key]} | versão={result.version} | "
            f"instalação={installation} | exe={result.executable}"
        )
        self.refresh()
        if continuation:
            continuation()


__all__ = ["HomePage"]
