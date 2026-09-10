"""GUI para instalar e validar o suporte MAME do projeto-SNAPS."""
from __future__ import annotations

import json
import logging
import os
import re
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
from ..services.arcade.local_version_detector import detect_local_version
from ..services.arcade.projeto_snaps_provider import ProgettoSnapsProvider

LOGGER = logging.getLogger(__name__)
SNAPS_HOME = "https://www.progettosnaps.net/"
MAME_DAT_INDEX = "https://www.progettosnaps.net/dats/MAME/"
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
    CACHE_DIR = Path.home() / ".serm" / "cache"
    EXPECTED_SUPPORT = (
        ("dats/command.dat", "DAT", "Comandos"),
        ("dats/gameinit.dat", "DAT", "Inicializacao"),
        ("dats/messinfo.dat", "DAT", "Sistemas nao-arcade"),
        ("folders/bestgames.ini", "INI", "Melhores jogos"),
        ("folders/catlist.ini", "INI", "Categorias"),
        ("folders/freeplay.ini", "INI", "Free Play"),
        ("folders/genre.ini", "INI", "Generos"),
        ("folders/languages.ini", "INI", "Idiomas"),
        ("folders/monochrome.ini", "INI", "Monocromatico"),
        ("folders/nplayers.ini", "INI", "Numero de jogadores"),
        ("folders/resolution.ini", "INI", "Resolucao"),
        ("folders/screenless.ini", "INI", "Sem tela"),
        ("folders/series.ini", "INI", "Series"),
        ("folders/category.ini", "INI", "Categorias oficiais"),
        ("folders/version.ini", "INI", "Versoes oficiais"),
    )
    RESOURCE_BY_PATH = {
        "dats/command.dat": "support-files",
        "dats/gameinit.dat": "support-files",
        "dats/messinfo.dat": "messinfo",
        "folders/bestgames.ini": "support-files",
        "folders/catlist.ini": "support-files",
        "folders/freeplay.ini": "support-files",
        "folders/genre.ini": "support-files",
        "folders/languages.ini": "support-files",
        "folders/monochrome.ini": "support-files",
        "folders/nplayers.ini": "nplayers",
        "folders/resolution.ini": "support-files",
        "folders/screenless.ini": "support-files",
        "folders/series.ini": "support-files",
        "folders/category.ini": "category",
        "folders/version.ini": "version",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._provider = ProgettoSnapsProvider()
        self._manager = DownloadManager(self.CACHE_DIR)
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
        self.nplayers_button = QPushButton("Atualizar NPlayers")
        self.nplayers_button.clicked.connect(self._sync_nplayers)
        self.category_button = QPushButton("Atualizar Category")
        self.category_button.clicked.connect(lambda: self._sync_folder_pack("category"))
        self.version_button = QPushButton("Atualizar Version")
        self.version_button.clicked.connect(lambda: self._sync_folder_pack("version"))
        self.messinfo_button = QPushButton("Atualizar MESSINFO")
        self.messinfo_button.clicked.connect(self._sync_messinfo)
        self.samples_button = QPushButton("Baixar Samples FullPack")
        self.samples_button.clicked.connect(self._sync_samples)
        open_folder = QPushButton("Abrir pasta MAME")
        open_folder.clicked.connect(self._open_root)
        open_dat = QPushButton("MAME DAT")
        open_dat.clicked.connect(lambda: webbrowser.open(MAME_DAT_INDEX))
        open_site = QPushButton("Site oficial")
        open_site.clicked.connect(lambda: webbrowser.open(SNAPS_HOME))
        for button in (
            self.update_button,
            self.nplayers_button,
            self.category_button,
            self.version_button,
            self.messinfo_button,
            self.samples_button,
            open_folder,
            open_dat,
            open_site,
        ):
            actions.addWidget(button)
        root.addLayout(actions)

        self.status_label = QLabel("Status: não verificado")
        root.addWidget(self.status_label)
        self.table = QTableWidget(len(self.EXPECTED_SUPPORT) + 1, 5)
        self.table.setHorizontalHeaderLabels(
            ("Arquivo / recurso", "Tipo", "Descrição", "Versão detectada", "Status local")
        )
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        for row, (relative, kind, description) in enumerate(self.EXPECTED_SUPPORT):
            self.table.setItem(row, 0, QTableWidgetItem(relative))
            self.table.setItem(row, 1, QTableWidgetItem(kind))
            self.table.setItem(row, 2, QTableWidgetItem(description))
            self.table.setItem(row, 3, QTableWidgetItem("—"))
            self.table.setItem(row, 4, QTableWidgetItem("—"))

        sample_row = len(self.EXPECTED_SUPPORT)
        self.table.setItem(sample_row, 0, QTableWidgetItem("samples/*.zip"))
        self.table.setItem(sample_row, 1, QTableWidgetItem("SAMPLES"))
        self.table.setItem(sample_row, 2, QTableWidgetItem("MAME Samples FullPack"))
        self.table.setItem(sample_row, 3, QTableWidgetItem("—"))
        self.table.setItem(sample_row, 4, QTableWidgetItem("—"))
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
        self._set_scan_status(root, sample_count)
        self.status_label.setText(
            f"MAME.exe: OK | Suporte: {present}/{len(self.EXPECTED_SUPPORT)} | "
            f"Samples: {sample_count} ZIP(s)"
        )

    def _clear_local_status(self) -> None:
        self.location_label.setText(
            f"{MAME_NOT_CONFIGURED} — use Diretórios → MAME"
        )
        self.status_label.setText(
            "Status: nenhum executável MAME válido está configurado"
        )
        for row in range(self.table.rowCount()):
            for column in (3, 4):
                item = self.table.item(row, column)
                if item is not None:
                    item.setText("—")

    def _scan_support_files(self, root: Path) -> int:
        present = 0
        for row, (relative, _kind, _description) in enumerate(self.EXPECTED_SUPPORT):
            path = root / relative
            exists = path.is_file()
            present += int(exists)
            version_item = self.table.item(row, 3)
            status_item = self.table.item(row, 4)
            if version_item is not None:
                version_item.setText(
                    self._local_version(path, relative) if exists else "—"
                )
            if status_item is not None:
                status_item.setText("Instalado" if exists else "Ausente")
        return present

    def _local_version(self, path: Path, relative: str) -> str:
        """Detecta a versão no recurso instalado e usa o cache somente como fallback."""
        detected = detect_local_version(path)
        if detected is not None:
            return detected
        resource_name = self.RESOURCE_BY_PATH.get(relative)
        return self._downloaded_version(resource_name) if resource_name else "—"

    def _downloaded_version(self, resource_name: str) -> str:
        """Retorna a versão do pacote presente no cache do SERM."""
        resource_dir = self.CACHE_DIR / "progetto-snaps" / "mame" / resource_name
        if not resource_dir.is_dir():
            return "—"
        candidates: list[tuple[tuple[int, ...], str]] = []
        for version_dir in resource_dir.iterdir():
            if not version_dir.is_dir():
                continue
            # O cache normalmente usa ``<resource>.zip``. Também aceitamos
            # qualquer arquivo regular na pasta de versão para manter a
            # detecção compatível com archives publicados com outro nome.
            if not any(path.is_file() for path in version_dir.iterdir()):
                continue
            key = tuple(int(part) for part in re.findall(r"\d+", version_dir.name))
            candidates.append((key or (0,), version_dir.name))
        if not candidates:
            return "—"
        return max(candidates, key=lambda item: item[0])[1]

    @staticmethod
    def _sample_count(root: Path) -> int:
        sample_dir = root / "samples"
        if not sample_dir.is_dir():
            return 0
        return sum(1 for item in sample_dir.glob("*.zip") if item.is_file())

    def _set_scan_status(self, root: Path, sample_count: int) -> None:
        sample_row = len(self.EXPECTED_SUPPORT)
        version_item = self.table.item(sample_row, 3)
        status_item = self.table.item(sample_row, 4)
        if version_item is not None:
            version = "—"
            if sample_count:
                sample_files = sorted(
                    path for path in (root / "samples").glob("*.zip") if path.is_file()
                )
                for sample_file in sample_files:
                    detected = detect_local_version(sample_file)
                    if detected is not None:
                        version = detected
                        break
                if version == "—":
                    version = self._downloaded_version("samples-fullpack")
            version_item.setText(version)
        if status_item is not None:
            status_item.setText(f"{sample_count} ZIP(s)" if sample_count else "Ausente")

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

    def _sync_nplayers(self) -> None:
        root = self._normalized_root()
        if root is None:
            self._show_mame_warning()
            return
        resource = self._resource("nplayers")
        self._start_busy("Baixando e instalando NPlayers…")
        worker = _SyncWorker(
            lambda: self._manager.install_members(
                resource,
                self._manager.acquire(resource),
                root,
                replace_existing=True,
            )
        )
        self._connect_worker(worker)

    def _sync_folder_pack(self, name: str) -> None:
        root = self._normalized_root()
        if root is None:
            self._show_mame_warning()
            return
        resource = self._resource(name)
        self._start_busy(f"Baixando e instalando {name.title()}…")
        worker = _SyncWorker(
            lambda: self._manager.install_tree(
                self._manager.acquire(resource),
                root / "folders",
                replace_existing=True,
                flatten=True,
            )
        )
        self._connect_worker(worker)

    def _sync_messinfo(self) -> None:
        root = self._normalized_root()
        if root is None:
            self._show_mame_warning()
            return
        resource = self._resource("messinfo")
        self._start_busy("Baixando e instalando MESSINFO…")
        worker = _SyncWorker(
            lambda: self._manager.install_tree(
                self._manager.acquire(resource),
                root / "dats",
                replace_existing=True,
                flatten=True,
            )
        )
        self._connect_worker(worker)

    def _sync_samples(self) -> None:
        root = self._normalized_root()
        if root is None:
            self._show_mame_warning()
            return
        resource = self._resource("samples-fullpack")
        self._start_busy("Baixando e instalando Samples FullPack…")
        worker = _SyncWorker(
            lambda: self._manager.install_tree(
                self._manager.acquire(resource),
                root / "samples",
                replace_existing=True,
                flatten=True,
            )
        )
        self._connect_worker(worker)

    def _connect_worker(self, worker: _SyncWorker) -> None:
        worker.signals.finished.connect(self._sync_finished)
        worker.signals.error.connect(self._sync_error)
        self._pool.start(worker)

    def _start_busy(self, message: str) -> None:
        self.status_label.setText(message)
        self.progress.show()
        for button in (
            self.update_button,
            self.nplayers_button,
            self.category_button,
            self.version_button,
            self.messinfo_button,
            self.samples_button,
        ):
            button.setEnabled(False)

    def _finish_busy(self) -> None:
        self.progress.hide()
        for button in (
            self.update_button,
            self.nplayers_button,
            self.category_button,
            self.version_button,
            self.messinfo_button,
            self.samples_button,
        ):
            button.setEnabled(True)

    def _sync_finished(self, _result: object) -> None:
        self._finish_busy()
        self._scan_local()

    def _sync_error(self, message: str) -> None:
        self._finish_busy()
        QMessageBox.critical(self, "Projeto-SNAPS", message)
        self._scan_local()

    def _show_mame_warning(self) -> None:
        QMessageBox.warning(
            self,
            "MAME não configurado",
            "Configure primeiro o executável MAME em Diretórios → MAME.",
        )

    def _open_root(self) -> None:
        root = self._normalized_root()
        if root is not None:
            os.startfile(root)  # type: ignore[attr-defined]


__all__ = ["ProgettoSnapsPage"]
