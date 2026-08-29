"""Complete emulator-management Home for SERM V2."""
from __future__ import annotations

import json
import logging
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root
from ..services.emulator_manager import EmulatorManager, RetroArchManager

logger = logging.getLogger(__name__)


class _Worker(QThread):
    """Run a blocking installation operation outside the Qt GUI thread."""

    progress = Signal(int, int)
    log = Signal(str)
    done = Signal(object)
    error = Signal(str)

    def __init__(self, operation, parent=None) -> None:
        super().__init__(parent)
        self.operation = operation

    def run(self) -> None:
        """Execute the supplied operation and emit its result."""
        try:
            result = self.operation(
                progress=lambda received, total: self.progress.emit(received, total),
                log=lambda message: self.log.emit(str(message)),
            )
            self.done.emit(result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[HOME][WORKER] operação falhou")
            self.error.emit(f"{type(exc).__name__}: {exc}")


class EmulatorHomePage(QWidget):
    """Home for standalone emulators and the complete RetroArch installer workflow."""

    EMULATORS = ("mame", "flycast", "supermodel", "fbneo")
    LABELS = EmulatorManager.LABELS
    SITES = {
        "mame": "https://github.com/mamedev/mame",
        "flycast": "https://github.com/flyinghead/flycast",
        "supermodel": "https://github.com/trzy/supermodel",
        "fbneo": "https://github.com/finalburnneo/FBNeo",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.manager = EmulatorManager(self._load_paths())
        self.retroarch = RetroArchManager(self.manager.roots.get("retroarch"))
        self.worker: _Worker | None = None
        self.cards: dict[str, tuple[QLabel, QLabel, QLabel, QProgressBar, QPushButton]] = {}
        self.core_items: dict[str, QListWidgetItem] = {}
        self._core_queue: list[str] = []
        self._build_ui()
        self.refresh()

    @property
    def paths_file(self) -> Path:
        """Return the shared V2 emulator-path registry."""
        return data_root() / "emulator_paths.json"

    def _load_paths(self) -> dict[str, Path | None]:
        """Load persisted emulator and RetroArch directories."""
        try:
            data = json.loads(self.paths_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {
            str(key): Path(str(value)).expanduser() if value else None
            for key, value in data.items()
        }

    def _save_paths(self, paths: dict[str, Path | None]) -> None:
        """Persist emulator and RetroArch directories."""
        self.paths_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {key: str(value) if value else None for key, value in paths.items()}
        self.paths_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _build_ui(self) -> None:
        """Build the Home tabs."""
        layout = QVBoxLayout(self)
        title = QLabel("SERM — Home")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:26px;font-weight:700;")
        layout.addWidget(title)
        tabs = QTabWidget()
        tabs.addTab(self._arcade_tab(), "Arcade / Emuladores")
        tabs.addTab(self._retroarch_tab(), "RetroArch")
        layout.addWidget(tabs, 1)

    def _arcade_tab(self) -> QWidget:
        """Build standalone emulator cards and bulk update controls."""
        page = QWidget()
        layout = QVBoxLayout(page)
        grid_frame = QFrame()
        grid = QGridLayout(grid_frame)
        grid_frame.setStyleSheet(
            "QFrame{background:#151515;border:1px solid #3d3d3d;border-radius:8px;}"
            "QLabel#name{font-size:15px;font-weight:bold;}"
            "QLabel#detail{color:#b8b8b8;}"
        )
        for index, key in enumerate(self.EMULATORS):
            card = QFrame()
            box = QVBoxLayout(card)
            name = QLabel(self.LABELS[key])
            name.setObjectName("name")
            status = QLabel("Verificando…")
            status.setObjectName("detail")
            version = QLabel("Versão: —")
            version.setObjectName("detail")
            path = QLabel("Instalação: —")
            path.setObjectName("detail")
            path.setWordWrap(True)
            progress = QProgressBar()
            progress.hide()
            install = QPushButton("⬇ Baixar / atualizar")
            install.clicked.connect(lambda _=False, k=key: self.install(k))
            configure = QPushButton("📁 Diretório")
            configure.clicked.connect(lambda _=False, k=key: self.configure(k))
            site = QPushButton("🌐 Repositório")
            site.clicked.connect(lambda _=False, k=key: webbrowser.open(self.SITES[k]))
            row = QHBoxLayout()
            row.addWidget(install)
            row.addWidget(configure)
            row.addWidget(site)
            for widget in (name, status, version, path, progress):
                box.addWidget(widget)
            box.addLayout(row)
            self.cards[key] = (status, version, path, progress, install)
            grid.addWidget(card, index // 2, index % 2)
        layout.addWidget(grid_frame)
        actions = QHBoxLayout()
        update_all = QPushButton("🔄 Atualizar todos os emuladores")
        update_all.clicked.connect(self.update_all)
        actions.addWidget(update_all)
        directories = QPushButton("📁 Configurar diretórios")
        directories.clicked.connect(self.open_emulator_directories)
        actions.addWidget(directories)
        self.seven_zip = QLabel()
        actions.addWidget(self.seven_zip, 1)
        layout.addLayout(actions)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(3000)
        self.log_view.setStyleSheet(
            "QPlainTextEdit{background:#0b0b0b;color:#d7d7d7;font-family:Consolas;font-size:10px;}"
        )
        layout.addWidget(QLabel("Log detalhado da instalação"))
        layout.addWidget(self.log_view, 1)
        return page

    def _retroarch_tab(self) -> QWidget:
        """Build the full RetroArch installation and core selection interface."""
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("RetroArch — Buildbot oficial")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:22px;font-weight:bold;")
        layout.addWidget(title)
        self.retro_status = QLabel()
        self.retro_path = QLabel()
        self.retro_cores = QLabel()
        for label in (self.retro_status, self.retro_path, self.retro_cores):
            label.setWordWrap(True)
            layout.addWidget(label)
        top = QHBoxLayout()
        for text, slot in (
            ("⬇ Nova instalação", self.install_retroarch),
            ("📁 Diretório", self.configure_retroarch),
            ("🔄 Buscar cores", self.refresh_cores),
            ("🔎 Verificar atualizações", self.verify_core_updates),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            top.addWidget(button)
        layout.addLayout(top)
        selection = QHBoxLayout()
        for text, slot in (
            ("☑ Selecionar todos", self.select_all_cores),
            ("☐ Limpar seleção", self.clear_core_selection),
            ("⬇ Instalar selecionados", self.install_selected_cores),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            selection.addWidget(button)
        selection.addStretch()
        self.core_summary = QLabel("0 selecionado(s)")
        selection.addWidget(self.core_summary)
        layout.addLayout(selection)
        self.core_list = QListWidget()
        self.core_list.itemChanged.connect(self._core_selection_changed)
        layout.addWidget(self.core_list, 1)
        self.retro_progress = QProgressBar()
        self.retro_progress.hide()
        layout.addWidget(self.retro_progress)
        return page

    def refresh(self) -> None:
        """Refresh emulator, RetroArch and 7-Zip discovery without downloads."""
        self.manager.roots = self._load_paths()
        self.retroarch = RetroArchManager(self.manager.roots.get("retroarch"))
        for key, status in self.manager.discover().items():
            card = self.cards[key]
            color = "#55d66b" if status.state == "ready" else "#e5c454" if status.state == "configured" else "#999"
            card[0].setText(f"● {status.state}")
            card[0].setStyleSheet(f"color:{color};font-weight:bold;")
            card[1].setText(f"Versão: {status.version or '—'}")
            card[2].setText(f"Instalação: {status.root or 'não configurada'}")
            card[4].setEnabled(self.worker is None)
        self.seven_zip.setText(f"7-Zip: {self.manager.find_7zip() or 'não encontrado'}")
        executable, root, cores = self.retroarch.discover()
        self.retro_status.setText(f"● {'Pronto' if executable else 'Não configurado'}")
        self.retro_status.setStyleSheet(
            "color:#55d66b;font-weight:bold;" if executable else "color:#e5c454;font-weight:bold;"
        )
        self.retro_path.setText(f"Instalação: {root or 'não configurada'}")
        self.retro_cores.setText(f"Cores: {cores or 'não configurado'}")
        logger.info("[HOME][DISCOVERY] 7zip=%s retroarch=%s", self.manager.find_7zip(), executable)

    def configure(self, key: str) -> None:
        """Select an emulator executable and persist its installation root."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Selecionar {self.LABELS[key]}",
            str(Path.home()),
            f"{self.LABELS[key]} (*.exe);;Executáveis (*.exe)",
        )
        if not path:
            return
        paths = self._load_paths()
        paths[key] = Path(path).resolve().parent
        self._save_paths(paths)
        self.refresh()

    def install(self, key: str) -> None:
        """Install or update one standalone emulator."""
        destination = self.manager.roots.get(key)
        if not destination:
            selected = QFileDialog.getExistingDirectory(self, f"Diretório do {self.LABELS[key]}", str(Path.home()))
            if not selected:
                return
            destination = Path(selected).resolve()
            paths = self._load_paths()
            paths[key] = destination
            self._save_paths(paths)
            self.manager.roots = paths
        self._start(
            lambda progress, log: self.manager.install(key, destination, progress=progress, log=log),
            key,
        )

    def update_all(self) -> None:
        """Update all configured standalone emulators sequentially."""
        queue = list(self.EMULATORS)

        def next_one() -> None:
            if not queue:
                self.refresh()
                return
            key = queue.pop(0)
            destination = self.manager.roots.get(key)
            if not destination:
                self._append_log(f"IGNORADO | {self.LABELS[key]} | diretório não configurado")
                next_one()
                return
            self._start(
                lambda progress, log, k=key, d=destination: self.manager.install(k, d, progress=progress, log=log),
                key,
                next_one,
            )

        next_one()

    def _start(self, operation, key: str, continuation=None) -> None:
        """Start a standalone-emulator worker."""
        if self.worker:
            return
        self.worker = _Worker(operation, self)
        self.worker.progress.connect(lambda received, total, k=key: self._progress(k, received, total))
        self.worker.log.connect(self._append_log)
        self.worker.done.connect(lambda result, k=key, c=continuation: self._done(k, result, c))
        self.worker.error.connect(lambda message, k=key, c=continuation: self._error(k, message, c))
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _progress(self, key: str, received: int, total: int) -> None:
        """Update a standalone emulator progress bar."""
        bar = self.cards[key][3]
        bar.show()
        bar.setRange(0, 100 if total else 0)
        bar.setValue(min(100, int(received * 100 / total)) if total else 0)

    def _append_log(self, message: str) -> None:
        """Append worker diagnostics to the Home log."""
        self.log_view.appendPlainText(str(message))
        logger.info("[HOME] %s", message)

    def _done(self, key: str, result, continuation=None) -> None:
        """Persist a successful standalone installation."""
        paths = self._load_paths()
        paths[key] = Path(result.executable).parent
        self._save_paths(paths)
        self._append_log(f"SUCESSO | {self.LABELS[key]} | {result.version} | {result.executable}")
        self.refresh()
        if continuation:
            continuation()

    def _error(self, key: str, message: str, continuation=None) -> None:
        """Log an installation error without crashing the GUI."""
        self._append_log(f"ERRO | {self.LABELS[key]} | {message}")
        if continuation:
            continuation()

    def _worker_finished(self) -> None:
        """Release the worker reference after Qt finishes."""
        self.worker = None
        self.refresh()

    def open_emulator_directories(self) -> None:
        """Open the unified Directories page from MainWindow."""
        window = self.window()
        directories = getattr(window, "directories_tab", None)
        tabs = getattr(window, "tab_widget", None)
        if directories is not None and tabs is not None:
            tabs.setCurrentWidget(directories)
            directories.refresh()

    def configure_retroarch(self) -> None:
        """Select and persist the RetroArch installation root."""
        selected = QFileDialog.getExistingDirectory(self, "Diretório do RetroArch", str(Path.home()))
        if not selected:
            return
        paths = self._load_paths()
        paths["retroarch"] = Path(selected).resolve()
        self._save_paths(paths)
        self.refresh()

    def install_retroarch(self) -> None:
        """Download and extract the official portable RetroArch x64 build."""
        destination = self.manager.roots.get("retroarch")
        if not destination:
            selected = QFileDialog.getExistingDirectory(self, "Instalar RetroArch em", str(Path.home()))
            if not selected:
                return
            destination = Path(selected).resolve()
            paths = self._load_paths()
            paths["retroarch"] = destination
            self._save_paths(paths)
            self.manager.roots = paths
        self.retroarch = RetroArchManager(destination)
        self._start_retro(lambda progress, log: self.retroarch.install_retroarch(destination, progress=progress))

    def refresh_cores(self) -> None:
        """Fetch the current Windows x64 libretro core catalog."""
        try:
            cores = self.retroarch.list_cores()
        except Exception as exc:  # noqa: BLE001
            logger.exception("[RETROARCH][CORES] falha")
            QMessageBox.warning(self, "RetroArch", str(exc))
            return
        _, _, destination = self.retroarch.discover()
        installed = {path.name.casefold() for path in destination.glob("*_libretro.dll")} if destination and destination.is_dir() else set()
        self.core_list.blockSignals(True)
        self.core_list.clear()
        self.core_items.clear()
        for core in cores:
            item = QListWidgetItem()
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            filename = core.filename.removesuffix(".zip")
            state = "INSTALADO" if filename.casefold() in installed else "AUSENTE"
            item.setText(f"[{state}] {core.core_name}")
            item.setData(Qt.ItemDataRole.UserRole, core.filename)
            item.setData(Qt.ItemDataRole.UserRole + 1, state)
            self.core_list.addItem(item)
            self.core_items[core.filename] = item
        self.core_list.blockSignals(False)
        self._update_core_summary()
        logger.info("[RETROARCH][CORES] disponíveis=%d instalados=%d", len(cores), len(installed))

    def verify_core_updates(self) -> None:
        """Refresh the core catalog and report the update-detection limitation."""
        self.refresh_cores()
        if not self.core_items:
            return
        installed = sum(item.data(Qt.ItemDataRole.UserRole + 1) == "INSTALADO" for item in self.core_items.values())
        self._append_log(f"RETROARCH | verificação concluída | publicados={len(self.core_items)} | instalados={installed}")
        self._append_log("RETROARCH | o índice do Buildbot não fornece CRC/versionamento por core; a validação definitiva ocorre ao instalar o ZIP atual.")

    def select_all_cores(self) -> None:
        """Select every listed core."""
        self.core_list.blockSignals(True)
        for index in range(self.core_list.count()):
            self.core_list.item(index).setCheckState(Qt.CheckState.Checked)
        self.core_list.blockSignals(False)
        self._update_core_summary()

    def clear_core_selection(self) -> None:
        """Clear every core selection."""
        self.core_list.blockSignals(True)
        for index in range(self.core_list.count()):
            self.core_list.item(index).setCheckState(Qt.CheckState.Unchecked)
        self.core_list.blockSignals(False)
        self._update_core_summary()

    def _core_selection_changed(self, _item: QListWidgetItem) -> None:
        """Update the selected-core counter."""
        self._update_core_summary()

    def _update_core_summary(self) -> None:
        """Refresh the selected-core counter."""
        selected = sum(self.core_list.item(index).checkState() == Qt.CheckState.Checked for index in range(self.core_list.count()))
        self.core_summary.setText(f"{selected} selecionado(s)")

    def install_selected_cores(self) -> None:
        """Install all checked cores sequentially."""
        _, _, destination = self.retroarch.discover()
        if destination is None:
            QMessageBox.information(self, "RetroArch", "Configure o diretório do RetroArch primeiro.")
            return
        selected = [
            self.core_list.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self.core_list.count())
            if self.core_list.item(index).checkState() == Qt.CheckState.Checked
        ]
        if not selected:
            QMessageBox.information(self, "RetroArch", "Nenhum core foi selecionado.")
            return
        self._core_queue = list(selected)
        self._install_next_core(destination)

    def _install_next_core(self, destination: Path) -> None:
        """Install the next selected core from the queue."""
        if not self._core_queue:
            self._append_log("RETROARCH | instalação dos cores selecionados concluída")
            self.refresh_cores()
            return
        filename = self._core_queue.pop(0)
        self._append_log(f"RETROARCH | instalando core={filename} | restantes={len(self._core_queue)}")
        self._start_retro(
            lambda progress, log, f=filename, d=destination: self.retroarch.install_core(f, d, progress=progress),
            continuation=lambda: self._install_next_core(destination),
        )

    def install_core(self) -> None:
        """Install the selected item, retained as a compatibility action."""
        item = self.core_list.currentItem()
        if item is None:
            return
        item.setCheckState(Qt.CheckState.Checked)
        self.install_selected_cores()

    def _start_retro(self, operation, continuation=None) -> None:
        """Run a RetroArch operation through the background worker."""
        if self.worker:
            return
        self.retro_progress.show()
        self.worker = _Worker(operation, self)
        self.worker.progress.connect(self._retro_progress)
        self.worker.log.connect(self._append_log)
        self.worker.done.connect(lambda result, c=continuation: self._retro_done(result, c))
        self.worker.error.connect(lambda message, c=continuation: self._retro_error(message, c))
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _retro_done(self, result, continuation=None) -> None:
        """Log a successful RetroArch operation and continue queued work."""
        self._append_log(f"RETROARCH OK | {result}")
        if continuation:
            continuation()

    def _retro_error(self, message: str, continuation=None) -> None:
        """Log a failed RetroArch operation and continue queued work."""
        self._append_log(f"RETROARCH ERRO | {message}")
        if continuation:
            continuation()

    def _retro_progress(self, received: int, total: int) -> None:
        """Update RetroArch download progress."""
        self.retro_progress.setRange(0, 100 if total else 0)
        self.retro_progress.setValue(min(100, int(received * 100 / total)) if total else 0)


__all__ = ["EmulatorHomePage"]
