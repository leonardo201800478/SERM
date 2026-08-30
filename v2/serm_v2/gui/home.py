"""Home V2 baseada nos componentes funcionais originais do SERM."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QListWidgetItem, QWidget

from .emulator_home import EmulatorHomePage, _Worker


class HomePage(EmulatorHomePage):
    """Expose the complete emulator Home under the original V2 API."""

    CORE_MAX_ATTEMPTS = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._core_current_filename: str | None = None
        self._core_destination: Path | None = None
        self._retro_continuation = None
        self._retro_operation_ok = False

    def configure(self, key: str) -> None:
        """Select only the installation directory used by download/update."""
        selected = QFileDialog.getExistingDirectory(
            self,
            f"Diretório de instalação — {self.LABELS[key]}",
            str(Path.home()),
        )
        if not selected:
            return
        paths = self._load_paths()
        paths[key] = Path(selected).resolve()
        self._save_paths(paths)
        self.manager.roots = paths
        self.refresh()

    def refresh_status(self) -> None:
        """Compatibility entry point preserved from the V1 Home contract."""
        self.refresh()

    def update_all_emulators(self) -> None:
        """Compatibility entry point for the V1 bulk-update action."""
        self.update_all()

    def install_emulator(self, emulator: str) -> None:
        """Compatibility entry point for installing one standalone emulator."""
        self.install(emulator)

    def clear_install_log(self) -> None:
        """Clear the Home installation diagnostic console."""
        self.log_view.clear()

    def open_official_site(self, key: str) -> None:
        """Open the official emulator repository used by the Home card."""
        import webbrowser

        url = self.SITES.get(key)
        if url:
            webbrowser.open(url)

    def _done(self, key: str, result, continuation=None) -> None:
        """Persist the installation root and integration executable separately."""
        paths = self._load_paths()
        installation = paths.get(key)
        if installation is None:
            installation = Path(result.executable).parent
            paths[key] = installation
        paths[f"{key}_exe"] = Path(result.executable).resolve()
        paths[f"{key}_version"] = str(result.version)
        self._save_paths(paths)
        self._append_log(
            f"SUCESSO | {self.LABELS[key]} | versão={result.version} | instalação={installation} | exe={result.executable}"
        )
        self.refresh()
        if continuation:
            continuation()

    def install_selected_cores(self) -> None:
        """Enfileira os cores selecionados e processa um por vez."""
        if self.worker:
            self._append_retro_log("FILA | já existe uma operação RetroArch em execução.")
            return

        _, _, destination = self.retroarch.discover()
        if destination is None:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(self, "RetroArch", "Configure o diretório do RetroArch primeiro.")
            return

        selected = [
            str(self.core_list.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.core_list.count())
            if self.core_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        if not selected:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.information(self, "RetroArch", "Nenhum core foi selecionado.")
            return

        self._core_queue = selected
        self._core_destination = Path(destination).resolve()
        self._core_current_filename = None
        self.core_list.setEnabled(False)
        self._append_retro_log(
            f"FILA | {len(self._core_queue)} core(s) | processamento sequencial iniciado"
        )
        self._install_next_core(self._core_destination)

    def _install_next_core(self, destination: Path) -> None:
        """Retira o próximo core da fila e inicia suas três tentativas máximas."""
        if not self._core_queue:
            self._core_current_filename = None
            self._core_destination = None
            self.core_list.setEnabled(True)
            self._append_retro_log("FILA | todos os cores selecionados foram processados")
            self._update_core_summary()
            self.refresh_cores()
            return

        filename = self._core_queue.pop(0)
        self._core_current_filename = filename
        self._append_retro_log(
            f"FILA | iniciando {filename} | restantes={len(self._core_queue)} | máximo={self.CORE_MAX_ATTEMPTS} tentativas"
        )
        self._start_retro(
            lambda progress, log, f=filename, d=destination: self._install_core_with_retries(
                f, d, progress, log
            ),
            continuation=lambda f=filename: self._finish_core_queue_item(f, destination),
        )

    def _install_core_with_retries(self, filename: str, destination: Path, progress, log):
        """Tenta baixar, validar e instalar um core até três vezes."""
        last_error: Exception | None = None
        for attempt in range(1, self.CORE_MAX_ATTEMPTS + 1):
            try:
                log(f"CORE | {filename} | tentativa={attempt}/{self.CORE_MAX_ATTEMPTS}")
                return self.retroarch.install_core(
                    filename,
                    destination,
                    channel=self._retro_channel,
                    progress=progress,
                    log=log,
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
        """Desmarca o core concluído/falhado e avança somente após o worker terminar."""
        item = self._find_core_item(filename)
        if item is not None:
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole + 1, "processed")

        self._append_retro_log(
            f"FILA | {filename} | processado | seleção removida | próximos={len(self._core_queue)}"
        )
        self._update_core_summary()
        self._install_next_core(destination)

    def _find_core_item(self, filename: str) -> QListWidgetItem | None:
        """Localiza na lista o item correspondente ao nome do arquivo do core."""
        for index in range(self.core_list.count()):
            item = self.core_list.item(index)
            value = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if value.casefold() == filename.casefold():
                return item
        return None

    def _start_retro(self, operation, continuation=None) -> None:
        """Executa uma operação RetroArch e só libera a próxima após QThread.finished."""
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
        """Registra sucesso e aguarda o encerramento real da thread."""
        self._retro_operation_ok = True
        self._append_retro_log(f"OK | {result}")

    def _retro_error(self, message: str) -> None:
        """Registra falha após esgotar as tentativas da operação."""
        self._retro_operation_ok = False
        self._append_retro_log(f"ERRO | {message}")

    def _retro_worker_finished(self) -> None:
        """Libera o worker e somente então inicia o próximo item da fila."""
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


__all__ = ["HomePage"]
