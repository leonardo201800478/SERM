"""GUI para instalar e validar o suporte MAME do progetto-SNAPS."""
from __future__ import annotations

import logging
import os
import webbrowser
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QProgressBar, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from ..services.arcade.download_manager import DownloadManager
from ..services.arcade.progetto_snaps_provider import ProgettoSnapsProvider

LOGGER = logging.getLogger(__name__)
SNAPS_HOME = "https://www.progettosnaps.net/"


class _WorkerSignals(QObject):
    finished = Signal(object)
    error = Signal(str)


class _SyncWorker(QRunnable):
    def __init__(self, operation) -> None:
        super().__init__()
        self.operation = operation
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            self.signals.finished.emit(self.operation())
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Falha na sincronizacao do progetto-SNAPS")
            self.signals.error.emit(str(exc))


class ProgettoSnapsPage(QWidget):
    """Gerencia MAME/dats, MAME/folders e MAME/samples."""

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
        title = QLabel("progetto-SNAPS — MAME Support Files")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Instale os arquivos oficiais de suporte do MAME em dats, folders e samples.")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        location = QGroupBox("Instalação do MAME")
        location_layout = QHBoxLayout(location)
        self.root_edit = QLineEdit()
        self.root_edit.setPlaceholderText("Pasta que contém mame.exe")
        browse = QPushButton("Selecionar…")
        browse.clicked.connect(self._choose_root)
        scan = QPushButton("Verificar")
        scan.clicked.connect(self._scan_local)
        location_layout.addWidget(self.root_edit, 1)
        location_layout.addWidget(browse)
        location_layout.addWidget(scan)
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
        self.table.setHorizontalHeaderLabels(("Arquivo / recurso", "Tipo", "Descrição", "Status local"))
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

    def _normalized_root(self) -> Path | None:
        raw = self.root_edit.text().strip()
        if not raw:
            return None
        root = Path(os.path.expandvars(os.path.expanduser(raw))).resolve()
        return root if root.is_dir() else None

    def _choose_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Selecionar pasta do MAME")
        if selected:
            self.root_edit.setText(selected)
            self._scan_local()

    def _scan_local(self) -> None:
        root = self._normalized_root()
        if root is None:
            self.status_label.setText("Status: selecione uma pasta válida do MAME")
            for row in range(self.table.rowCount()):
                self.table.item(row, 3).setText("—")
            return
        exe_status = "OK" if (root / "mame.exe").is_file() else "não encontrado"
        present = 0
        for row, (relative, _kind, _description) in enumerate(self.EXPECTED_SUPPORT):
            exists = (root / relative).is_file()
            present += int(exists)
            self.table.item(row, 3).setText("Instalado" if exists else "Ausente")
        sample_dir = root / "samples"
        sample_count = sum(1 for item in sample_dir.glob("*.zip") if item.is_file()) if sample_dir.is_dir() else 0
        sample_row = len(self.EXPECTED_SUPPORT)
        self.table.item(sample_row, 3).setText(f"{sample_count} ZIP(s)" if sample_count else "Ausente")
        self.status_label.setText(f"MAME.exe: {exe_status} | Suporte: {present}/{len(self.EXPECTED_SUPPORT)} | Samples: {sample_count} ZIP(s)")

    def _resource(self, name: str):
        return next(item for item in self._provider.resources() if item.name == name)

    def _sync_support(self) -> None:
        root = self._normalized_root()
        if root is None:
            QMessageBox.warning(self, "MAME não configurado", "Selecione primeiro a pasta que contém mame.exe.")
            return
        resource = self._resource("support-files")
        self._start_busy("Baixando e instalando SupportFiles…")
        worker = _SyncWorker(lambda: self._manager.install_members(resource, self._manager.acquire(resource), root, replace_existing=True))
        worker.signals.finished.connect(self._sync_finished)
        worker.signals.error.connect(self._sync_error)
        self._pool.start(worker)

    def _sync_samples(self) -> None:
        root = self._normalized_root()
        if root is None:
            QMessageBox.warning(self, "MAME não configurado", "Selecione primeiro a pasta que contém mame.exe.")
            return
        resource = self._resource("samples-fullpack")
        self._start_busy("Baixando e instalando Samples FullPack 0.289…")
        worker = _SyncWorker(lambda: self._manager.install_tree(self._manager.acquire(resource), root / "samples", replace_existing=True, flatten=True))
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
        self.status_label.setText(f"Sincronização concluída: {count} arquivo(s) processado(s).")
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
