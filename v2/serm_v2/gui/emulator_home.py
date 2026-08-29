"""Complete emulator-management Home restored from the tested SERM workflow."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..services.emulator_manager import EmulatorManager, RetroArchManager

logger = logging.getLogger(__name__)


class _Worker(QThread):
    """Run a download/extraction operation without blocking Qt."""

    progress = Signal(int, int)
    log = Signal(str)
    done = Signal(object)
    error = Signal(str)

    def __init__(self, operation, parent=None) -> None:
        super().__init__(parent)
        self.operation = operation

    def run(self) -> None:
        """Execute the operation and publish its result."""
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
    """Home containing standalone emulator downloads and the RetroArch manager."""

    EMULATORS = ("mame", "flycast", "supermodel", "fbneo")
    LABELS = EmulatorManager.LABELS

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.manager = EmulatorManager(self._load_paths())
        self.retroarch = RetroArchManager(self._load_paths().get("retroarch"))
        self.worker: _Worker | None = None
        self.cards: dict[str, tuple[QLabel, QLabel, QLabel, QProgressBar, QPushButton]] = {}
        self._build_ui()
        self.refresh()

    @property
    def paths_file(self) -> Path:
        """Return the V2 persistent emulator-path registry."""
        return Path(__file__).resolve().parents[2] / "data" / "emulator_paths.json"

    def _load_paths(self) -> dict[str, Path | None]:
        """Load persisted emulator directories."""
        try:
            data = json.loads(self.paths_file.read_text(encoding="utf-8"))
            return {key: Path(value) if value else None for key, value in data.items()}
        except (OSError, ValueError):
            return {}

    def _save_paths(self, paths: dict[str, Path | None]) -> None:
        """Persist emulator directories."""
        self.paths_file.parent.mkdir(parents=True, exist_ok=True)
        self.paths_file.write_text(json.dumps({k: str(v) if v else None for k, v in paths.items()}, indent=2), encoding="utf-8")

    def _build_ui(self) -> None:
        """Build the complete Home with Arcade and RetroArch sub-tabs."""
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
        """Build the four tested standalone-emulator cards."""
        page = QWidget()
        layout = QVBoxLayout(page)
        grid_frame = QFrame()
        grid = QGridLayout(grid_frame)
        grid_frame.setStyleSheet("QFrame{background:#151515;border:1px solid #3d3d3d;border-radius:8px;} QLabel#name{font-size:15px;font-weight:bold;} QLabel#detail{color:#b8b8b8;}")
        for index, key in enumerate(self.EMULATORS):
            card = QFrame()
            card.setObjectName("card")
            box = QVBoxLayout(card)
            name = QLabel(self.LABELS[key]); name.setObjectName("name")
            status = QLabel("Verificando…"); status.setObjectName("detail")
            version = QLabel("Versão: —"); version.setObjectName("detail")
            path = QLabel("Instalação: —"); path.setObjectName("detail"); path.setWordWrap(True)
            progress = QProgressBar(); progress.hide()
            install = QPushButton("⬇ Baixar / atualizar")
            install.clicked.connect(lambda _=False, k=key: self.install(k))
            configure = QPushButton("📁 Diretório")
            configure.clicked.connect(lambda _=False, k=key: self.configure(k))
            row = QHBoxLayout(); row.addWidget(install); row.addWidget(configure)
            for widget in (name, status, version, path, progress): box.addWidget(widget)
            box.addLayout(row)
            self.cards[key] = (status, version, path, progress, install)
            grid.addWidget(card, index // 2, index % 2)
        layout.addWidget(grid_frame)
        actions = QHBoxLayout()
        update_all = QPushButton("🔄 Atualizar todos os emuladores")
        update_all.clicked.connect(self.update_all)
        actions.addWidget(update_all)
        self.seven_zip = QLabel(); actions.addWidget(self.seven_zip, 1)
        layout.addLayout(actions)
        self.log_view = QPlainTextEdit(); self.log_view.setReadOnly(True); self.log_view.setMaximumBlockCount(3000)
        self.log_view.setStyleSheet("QPlainTextEdit{background:#0b0b0b;color:#d7d7d7;font-family:Consolas;font-size:10px;}")
        layout.addWidget(QLabel("Log detalhado")); layout.addWidget(self.log_view, 1)
        return page

    def _retroarch_tab(self) -> QWidget:
        """Build RetroArch installation, detection and core-management controls."""
        page = QWidget(); layout = QVBoxLayout(page)
        title = QLabel("RetroArch — Buildbot oficial"); title.setAlignment(Qt.AlignmentFlag.AlignCenter); title.setStyleSheet("font-size:22px;font-weight:bold;"); layout.addWidget(title)
        self.retro_status = QLabel(); self.retro_path = QLabel(); self.retro_cores = QLabel()
        for label in (self.retro_status, self.retro_path, self.retro_cores): layout.addWidget(label)
        row = QHBoxLayout()
        install = QPushButton("⬇ Nova instalação"); install.clicked.connect(self.install_retroarch); row.addWidget(install)
        configure = QPushButton("📁 Diretório"); configure.clicked.connect(self.configure_retroarch); row.addWidget(configure)
        refresh = QPushButton("🔄 Atualizar cores"); refresh.clicked.connect(self.refresh_cores); row.addWidget(refresh)
        layout.addLayout(row)
        self.core_list = QListWidget(); layout.addWidget(self.core_list, 1)
        core_install = QPushButton("⬇ Instalar / atualizar core selecionado"); core_install.clicked.connect(self.install_core); layout.addWidget(core_install)
        self.retro_progress = QProgressBar(); self.retro_progress.hide(); layout.addWidget(self.retro_progress)
        return page

    def refresh(self) -> None:
        """Refresh all local emulator and 7-Zip detection."""
        self.manager.roots = self._load_paths()
        self.retroarch = RetroArchManager(self.manager.roots.get("retroarch"))
        for key, status in self.manager.discover().items():
            card = self.cards[key]
            color = "#55d66b" if status.state == "ready" else "#e5c454" if status.state == "configured" else "#999"
            card[0].setText(f"● {status.state}"); card[0].setStyleSheet(f"color:{color};font-weight:bold;")
            card[1].setText(f"Versão: {status.version or '—'}")
            card[2].setText(f"Instalação: {status.root or 'não configurada'}")
            card[4].setEnabled(self.worker is None)
        self.seven_zip.setText(f"7-Zip: {self.manager.find_7zip() or 'não encontrado'}")
        executable, root, cores = self.retroarch.discover()
        self.retro_status.setText(f"● {'Pronto' if executable else 'Não configurado'}")
        self.retro_path.setText(f"Instalação: {root or 'não configurada'}")
        self.retro_cores.setText(f"Cores: {cores or 'não configurado'}")
        logger.info("[HOME][DISCOVERY] 7zip=%s retroarch=%s", self.manager.find_7zip(), executable)

    def configure(self, key: str) -> None:
        """Select and persist an emulator directory."""
        path, _ = QFileDialog.getOpenFileName(self, f"Selecionar {self.LABELS[key]}", str(Path.home()), f"{self.LABELS[key]} executable (*.exe)")
        if not path: return
        paths = self._load_paths(); paths[key] = Path(path).parent; self._save_paths(paths); self.refresh()

    def install(self, key: str) -> None:
        """Install/update one emulator, prompting for a destination when necessary."""
        destination = self.manager.roots.get(key)
        if not destination:
            selected = QFileDialog.getExistingDirectory(self, f"Diretório do {self.LABELS[key]}", str(Path.home()))
            if not selected: return
            destination = Path(selected); paths = self._load_paths(); paths[key] = destination; self._save_paths(paths); self.manager.roots = paths
        self._start(lambda progress, log: self.manager.install(key, destination, progress=progress, log=log), key)

    def update_all(self) -> None:
        """Update all configured standalone emulators sequentially."""
        queue = list(self.EMULATORS)
        def next_one() -> None:
            if not queue: self.refresh(); return
            key = queue.pop(0); destination = self.manager.roots.get(key)
            if not destination:
                self.log_view.appendPlainText(f"IGNORADO | {self.LABELS[key]} | diretório não configurado"); next_one(); return
            self._start(lambda progress, log, k=key, d=destination: self.manager.install(k, d, progress=progress, log=log), key, next_one)
        next_one()

    def _start(self, operation, key: str, continuation=None) -> None:
        """Start a standalone-emulator worker."""
        if self.worker: return
        self.worker = _Worker(operation, self); self.worker.progress.connect(lambda a,b,k=key: self._progress(k,a,b)); self.worker.log.connect(self._append_log); self.worker.done.connect(lambda result,k=key,c=continuation: self._done(k,result,c)); self.worker.error.connect(lambda message,k=key,c=continuation: self._error(k,message,c)); self.worker.finished.connect(self._worker_finished); self.worker.start()

    def _progress(self, key: str, received: int, total: int) -> None:
        """Update an emulator progress bar."""
        bar = self.cards[key][3]; bar.show(); bar.setRange(0,100 if total else 0); bar.setValue(min(100, int(received*100/total)) if total else 0)

    def _append_log(self, message: str) -> None:
        """Append worker diagnostics to the Home log."""
        self.log_view.appendPlainText(str(message)); logger.info("[HOME] %s", message)

    def _done(self, key: str, result, continuation=None) -> None:
        """Persist successful installation and continue a batch."""
        paths = self._load_paths(); paths[key] = Path(result.executable).parent; self._save_paths(paths); self._append_log(f"SUCESSO | {self.LABELS[key]} | {result.version} | {result.executable}"); self.refresh()
        if continuation: continuation()

    def _error(self, key: str, message: str, continuation=None) -> None:
        """Log an installation error without crashing the GUI."""
        self._append_log(f"ERRO | {self.LABELS[key]} | {message}")
        if continuation: continuation()

    def _worker_finished(self) -> None:
        """Release the worker reference after Qt finishes the thread."""
        self.worker = None; self.refresh()

    def configure_retroarch(self) -> None:
        """Select and persist the RetroArch installation root."""
        selected = QFileDialog.getExistingDirectory(self, "Diretório do RetroArch", str(Path.home()))
        if not selected: return
        paths = self._load_paths(); paths["retroarch"] = Path(selected); self._save_paths(paths); self.refresh()

    def install_retroarch(self) -> None:
        """Download and extract the official portable RetroArch build."""
        destination = self.manager.roots.get("retroarch")
        if not destination:
            selected = QFileDialog.getExistingDirectory(self, "Instalar RetroArch em", str(Path.home()))
            if not selected: return
            destination = Path(selected); paths = self._load_paths(); paths["retroarch"] = destination; self._save_paths(paths)
        self.retroarch = RetroArchManager(destination)
        self._start_retro(lambda progress, log: self.retroarch.install_retroarch(destination, progress=progress))

    def refresh_cores(self) -> None:
        """Load all current Windows x64 libretro cores from Buildbot."""
        try:
            cores = self.retroarch.list_cores(); self.core_list.clear()
            for core in cores:
                self.core_list.addItem(f"{core.core_name} | {core.filename}"); self.core_list.item(self.core_list.count()-1).setData(Qt.ItemDataRole.UserRole, core.filename)
            logger.info("[RETROARCH][CORES] disponíveis=%d", len(cores))
        except Exception as exc:  # noqa: BLE001
            logger.exception("[RETROARCH][CORES] falha"); QMessageBox.warning(self, "RetroArch", str(exc))

    def install_core(self) -> None:
        """Download and install the selected official libretro core."""
        item = self.core_list.currentItem()
        _, _, cores = self.retroarch.discover()
        if item is None or cores is None:
            QMessageBox.information(self, "RetroArch", "Configure o RetroArch e selecione um core."); return
        filename = item.data(Qt.ItemDataRole.UserRole)
        self._start_retro(lambda progress, log: self.retroarch.install_core(filename, cores, progress=progress))

    def _start_retro(self, operation) -> None:
        """Run a RetroArch operation through the same background worker."""
        if self.worker: return
        self.retro_progress.show(); self.worker = _Worker(operation, self); self.worker.progress.connect(self._retro_progress); self.worker.log.connect(self._append_log); self.worker.done.connect(lambda result: self._append_log(f"RETROARCH OK | {result}")); self.worker.error.connect(lambda message: self._append_log(f"RETROARCH ERRO | {message}")); self.worker.finished.connect(self._worker_finished); self.worker.start()

    def _retro_progress(self, received: int, total: int) -> None:
        """Update RetroArch progress."""
        self.retro_progress.setRange(0,100 if total else 0); self.retro_progress.setValue(min(100, int(received*100/total)) if total else 0)
