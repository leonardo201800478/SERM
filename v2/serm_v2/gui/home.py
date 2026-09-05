"""Home V2 baseada nos componentes funcionais originais do SERM."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .emulator_home import EmulatorHomePage, _Worker


class HomePage(EmulatorHomePage):
    """Expose a Home completa e preserva o contrato funcional da V1."""
    CORE_MAX_ATTEMPTS = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._core_current_filename: str | None = None
        self._core_destination: Path | None = None
        self._core_queue_with_channels: list[tuple[str, str]] = []
        self._retro_continuation = None
        self._retro_operation_ok = False
        self._core_catalog_cache = None

    def _retroarch_tab(self) -> QWidget:
        """Adiciona filtros locais ao catálogo sem alterar o canal do RetroArch."""
        page = super()._retroarch_tab()
        layout = page.layout()
        if not isinstance(layout, QVBoxLayout):
            return page
        filters = QGroupBox("Filtro do catálogo de cores")
        row = QHBoxLayout(filters)
        self.core_include_beta = QCheckBox("Incluir Beta / Nightly")
        self.core_current_only = QCheckBox("Somente cores atuais")
        self.core_hide_games = QCheckBox("Ocultar jogos / game engines")
        self.core_current_only.setChecked(True)
        self.core_hide_games.setChecked(True)
        for widget in (self.core_include_beta, self.core_current_only, self.core_hide_games):
            row.addWidget(widget)
            widget.stateChanged.connect(self._core_filters_changed)
        row.addStretch()
        layout.insertWidget(7, filters)
        return page

    def _core_filters_changed(self, _state: int) -> None:
        """Aplica filtros somente ao catálogo já carregado; não faz requisição HTTP."""
        if self.worker is not None:
            return
        if self._core_catalog_cache is None:
            self._append_retro_log("FILTRO | catálogo ainda não carregado; use 'Buscar cores' para consultar o Buildbot.")
            return
        self._render_core_catalog(self._filtered_cached_cores())

    def _filtered_cached_cores(self):
        """Filtra em memória o último catálogo obtido do Buildbot."""
        cores = tuple(self._core_catalog_cache or ())
        manager = self.retroarch
        return manager.filter_cores(
            cores,
            current_only=self.core_current_only.isChecked(),
            hide_games=self.core_hide_games.isChecked(),
        )

    def refresh_cores(self) -> None:
        """Consulta o catálogo e somente depois aplica os filtros selecionados."""
        if self.worker is not None:
            self._append_retro_log("CATÁLOGO | operação RetroArch já em execução.")
            return
        try:
            # O canal do frontend (Stable/Nightly) NÃO é alterado pelos filtros.
            # Stable e Beta/Nightly são tratados como fontes independentes pelo serviço.
            cores = self.retroarch.list_filtered_cores(
                include_beta=self.core_include_beta.isChecked(),
                current_only=False,
                hide_games=False,
            )
            self._core_catalog_cache = tuple(cores)
            self._render_core_catalog(self._filtered_cached_cores())
            source = "Stable + Beta/Nightly" if self.core_include_beta.isChecked() else "Stable"
            self._append_retro_log(
                f"CATÁLOGO | fonte={source} | atuais={self.core_current_only.isChecked()} | "
                f"sem jogos/engines={self.core_hide_games.isChecked()} | cores={len(self._core_catalog_cache)}"
            )
        except Exception as exc:  # noqa: BLE001
            self._append_retro_log(f"ERRO CORES | {type(exc).__name__}: {exc}")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "RetroArch", str(exc))

    def _render_core_catalog(self, cores) -> None:
        """Renderiza uma coleção de CoreInfo e compara com os cores instalados."""
        _, _, destination = self.retroarch.discover()
        installed = self.retroarch.installed_cores(destination) if destination else ()
        comparisons = self.retroarch.compare_installed_cores(cores, destination) if destination and destination.is_dir() else []
        state_map = {path.name.casefold(): state for path, _, state in comparisons}
        installed_names = {path.name.casefold() for path in installed}
        self.core_list.blockSignals(True)
        self.core_list.clear()
        self.core_items.clear()
        installed_count = update_count = 0
        for core in cores:
            key = core.filename.removesuffix(".zip").casefold()
            state = state_map.get(key, "new")
            installed_count += key in installed_names
            update_count += state == "update"
            marker = "[ATUALIZADO]" if state == "current" else "[ATUALIZAÇÃO]" if state == "update" else "[NOVO]"
            beta = " | BETA/NIGHTLY" if core.channel == "nightly" else ""
            item = QListWidgetItem(f"{marker}{beta} {core.core_name} | {core.date} | CRC {core.crc32}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, core.filename)
            item.setData(Qt.ItemDataRole.UserRole + 1, state)
            item.setData(Qt.ItemDataRole.UserRole + 2, core.channel)
            self.core_list.addItem(item)
            self.core_items[core.filename] = item
        self.core_list.blockSignals(False)
        new_count = len(cores) - installed_count
        self.core_summary.setText(
            f"{len(cores)} publicados • {installed_count} instalados • "
            f"{update_count} atualizações • {new_count} novos"
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
            QMessageBox.information(self, "RetroArch", "Configure o diretório do RetroArch primeiro.")
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
        filename, channel = self._core_queue_with_channels.pop(0)
        self._core_current_filename = filename
        self._append_retro_log(
            f"FILA | iniciando {filename} | canal={channel} | "
            f"restantes={len(self._core_queue_with_channels)} | máximo={self.CORE_MAX_ATTEMPTS} tentativas"
        )
        self._start_retro(
            lambda progress, log, f=filename, d=destination, c=channel: self._install_core_with_retries(
                f, d, c, progress, log
            ),
            continuation=lambda f=filename: self._finish_core_queue_item(f, destination),
        )

    def _install_core_with_retries(self, filename: str, destination: Path, channel: str, progress, log):
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
        """Limpa o console de instalação."""
        self.log_view.clear()

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
