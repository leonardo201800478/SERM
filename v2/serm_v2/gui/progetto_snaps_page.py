"""GUI para instalar e validar o suporte MAME do projeto-SNAPS."""
from __future__ import annotations

import json
import logging
import os
import webbrowser
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root
from ..services.arcade.download_manager import DownloadManager
from ..services.arcade.projeto_snaps_provider import ProgettoSnapsProvider

LOGGER = logging.getLogger(__name__)
SNAPS_HOME = "https://www.progettosnaps.net/"
MAME_NOT_CONFIGURED = "MAME não configurado"


class _WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)


class _SyncWorker(QRunnable):
    def __init__(self, operation: Callable[[], object]) -> None:
        super().__init__()
        self.operation = operation
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            self.signals.finished.emit(self.operation())
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Falha na sincronizacao do projeto-SNAPS")
            self.signals.error.emit(str(exc))


class ProgettoSnapsPage(QWidget):
    """Gerencia MAME/dats, MAME/folders e MAME/samples."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    EXPECTED_SUPPORT = (
        ("dats/command.dat", "DAT", "Comandos"),
        ("dats/gameinit.dat", "DAT", "Inicializacao"),
        ("folders/bestgames.ini", "INI", "Melhores jogos"),
        ("folders/catlist.ini", "INI", "Categorias"),
        ("folders/genre.ini", "INI", "Generos"),
        ("folders/languages.ini", "INI", "Idiomas"),
        ("folders/series.ini", "INI", "Series"),
        ("folders/gameinit.ini", "INI", "Inicializacao"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._provider = ProgettoSnapsProvider()
        self._manager = DownloadManager(Path.home() / ".serm" / "cache")
        self._build_ui()
        self._scan_local()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel("projeto-SNAPS — MAME Support Files")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Instale os arquivos oficiais de suporte do MAME em dats, folders e samples. "
            "O SERM utiliza o executável MAME já configurado em Diretórios."
        )
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        location = QGroupBox("MAME configurado no SERM")
        location_layout = QHBoxLayout(location)
        self.location_label = QLabel(MAME_NOT_CONFIGURED)
        self.location_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        location_layout.addWidget(self.location_label, 1)
        refresh = QPushButton("Atualizar")
        refresh.clicked.connect(self._scan_local)
        location_layout.addWidget(refresh)
        root.addWidget(location)

        actions = QHBoxLayout()
        self.update_button = QPushButton("Baixar / Atualizar suporte")
        self.update_button.clicked.connect(self._sync_support)
        self.samples_button = QPushButton("Baixar Samples FullPack")
        self.samples_button.clicked.connect(self._sync_samples)
        open_folder = QPushButton("Abrir pasta MAME")
        open_folder.clicked.connect(self._open_root)
        open_site = QPushButton("Site oficial")
        open_site.clicked.connect(lambda: webbrowser.open(SNAPS_HOME))
        for button in (self.update_button, self.samples_button, open_folder, open_site):
            actions.addWidget(button)
        root.addLayout(actions)

        self.status_label = QLabel("Status: não verificado")
        root.addWidget(self.status_label)
        self.table = QTableWidget(len(self.EXPECTED_SUPPORT) + 1, 4)
        self.table.setHorizontalHeaderLabels(
            ("Arquivo / recurso", "Tipo", "Descrição", "Status local")
        )
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        for row, (relative, kind, description) in enumerate(self.EXPECTED_SUPPORT):
            self.table.setItem(row, 0, QTableWidgetItem(relative))
            self.table.setItem(row, 1, QTableWidgetItem(kind))
            self.table.setItem(row, 2, QTableWidgetItem(description))
            self.table.setItem(row, 3, QTableWidgetItem("—"))

        sample_row = len(self.EXPECTED_SUPPORT)
        self.table.setItem(sample_row, 0, QTableWidgetItem("samples/*.zip"))
        self.table.setItem(sample_row, 1, QTableWidgetItem("SAMPLES"))
        self.table.setItem(sample_row, 2, QTableWidgetItem("MAME Samples FullPack 0.289"))
        self.table.setItem(sample_row, 3, QTableWidgetItem("—"))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        root.addWidget(self.progress)

    def _mapped_executable(self) -> Path | None:
        """Read the single MAME executable already persisted by SERM."""
        try:
            value = json.loads(self.PATHS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        if not isinstance(value, dict):
            return None
        raw = value.get("mame_executable")
        if not isinstance(raw, str) or not raw.strip():
            return None
        executable = Path(os.path.expandvars(os.path.expanduser(raw))).resolve()
        return executable if executable.is_file() else None

    def _normalized_root(self) -> Path | None:
        executable = self._mapped_executable()
        return executable.parent if executable is not None else None

    def _scan_local(self) -> None:
        executable = self._mapped_executable()
        if executable is None:
            self._clear_local_status()
            return
        root = executable.parent
        self.location_label.setText(str(executable))
        present = self._scan_support_files(root)
        sample_count = self._sample_count(root)
        self._set_scan_status(present, sample_count)

    def _clear_local_status(self) -> None:
        self.location_label.setText(
            f"{MAME_NOT_CONFIGURED} — use Diretórios → MAME"
        )
        self.status_label.setText(
            "Status: nenhum executável MAME válido está configurado"
        )
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 3)
            if item is not None:
                item.setText("—")

    def _scan_support_files(self, root: Path) -> int:
        present = 0
        for row, (relative, _kind, _description) in enumerate(self.EXPECTED_SUPPORT):
            exists = (root / relative).is_file()
            present += int(exists)
            item = self.table.item(row, 3)
            if item is not None:
                item.setText("Instalado" if exists else "Ausente")
        return present

    @staticmethod
    def _sample_count(root: Path) -> int:
        sample_dir = root / "samples"
        if not sample_dir.is_dir():
            return 0
        return sum(1 for item in sample_dir.glob("*.zip") if item.is_file())

    def _set_scan_status(self, present: int, sample_count: int) -> None:
        sample_row = len(self.EXPECTED_SUPPORT)
        item = self.table.item(sample_row, 3)
        if item is not None:
            item.setText(f"{sample_count} ZIP(s)" if sample_count else "Ausente")
        self.status_label.setText(
            f"MAME.exe: OK | Suporte: {present}/{len(self.EXPECTED_SUPPORT)} | "
            f"Samples: {sample_count} ZIP(s)"
        )

    def _resource(self, name: str):
        """Resolve um recurso e produz erro diagnóstico quando ausente."""
        resources = self._provider.resources()
        for resource in resources:
            if resource.name == name or resource.resource_id == f"mame-{name}":
                return resource
        available = ", ".join(resource.name for resource in resources) or "nenhum"
        raise LookupError(
            f"Recurso progetto-SNAPS '{name}' não encontrado. Disponíveis: {available}"
        )

    def _sync_support(self) -> None:
        root = self._normalized_root()
        if root is None:
            self._show_mame_warning()
            return
        resource = self._resource("support-files")
        self._start_busy("Baixando e instalando SupportFiles…")
        worker = _SyncWorker(
            lambda: self._manager.install_members(
                resource,
                self._manager.acquire(resource),
                root,
                replace_existing=True,
            )
        )
        self._connect_worker(worker)

    def _sync_samples(self) -> None:
        root = self._normalized_root()
        if root is None:
            self._show_mame_warning()
            return
        resource = self._resource("samples-fullpack")
        self._start_busy("Baixando e instalando Samples FullPack 0.289…")
        worker = _SyncWorker(
            lambda: self._manager.install_tree(
                self._manager.acquire(resource),
                root / "samples",
                replace_existing=True,
                flatten=True,
            )
        )
        self._connect_worker(worker)

    def _show_mame_warning(self) -> None:
        QMessageBox.warning(
            self,
            MAME_NOT_CONFIGURED,
            "Configure primeiro o executável do MAME em Diretórios → MAME.",
        )

    def _connect_worker(self, worker: _SyncWorker) -> None:
        worker.signals.finished.connect(self._sync_finished)
        worker.signals.error.connect(self._sync_error)
        self._pool.start(worker)

    def _start_busy(self, message: str) -> None:
        self.status_label.setText(message)
        self.progress.show()
        self.update_button.setEnabled(False)
        self.samples_button.setEnabled(False)

    def _sync_finished(self, result: object) -> None:
        self.progress.hide()
        self.update_button.setEnabled(True)
        self.samples_button.setEnabled(True)
        count = len(result) if isinstance(result, tuple) else 0
        self.status_label.setText(
            f"Sincronização concluída: {count} arquivo(s) processado(s)."
        )
        self._scan_local()

    def _sync_error(self, message: str) -> None:
        self.progress.hide()
        self.update_button.setEnabled(True)
        self.samples_button.setEnabled(True)
        self.status_label.setText("Falha na sincronização")
        QMessageBox.critical(self, "progetto-SNAPS", message)

    def _open_root(self) -> None:
        root = self._normalized_root()
        if root is not None:
            os.startfile(root)  # type: ignore[attr-defined]


__all__ = ["ProgettoSnapsPage"]
