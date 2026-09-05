"""Scraper unificado de DATs do SERM V2."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NotRequired, TypedDict, cast

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..integrations.launchbox import LaunchBoxIntegration
from ..integrations.launchbox_provider import LaunchBoxProvider
from ..services.c64_data_service import C64DataError, C64DataService, C64ScanResult
from ..services.mame_catalog_service import MameCatalogError, MameCatalogService
from ..services.mame_classification_service import (
    MameClassificationError,
    MameClassificationService,
)
from ..services.mame_resolution_service import MameResolutionError, MameResolutionService
from ..services.mame_vsync_service import MameVsyncError, MameVsyncService
from ..services.whloader_data_service import (
    WHLoaderDataError,
    WHLoaderDataService,
    WHLoaderScanResult,
)
from ..sources.acquisition.no_intro_archive import NoIntroArchiveProvider
from ..sources.acquisition.redump import RedumpProvider

logger = logging.getLogger(__name__)


class _MameCatalogResult(TypedDict):
    """Estrutura conhecida retornada pela ingestão do catálogo MAME."""

    import_id: int
    mame_build: str | None
    machine_count: int
    display_count: int
    rom_count: int
    disk_count: int
    raw_xml: object
    xml_path: object
    database: object
    source_hash: str
    elapsed_seconds: float
    deduplicated: bool
    lossless: bool
    catalog_complete: bool
    profiles_generated: int
    run_id: str
    force: NotRequired[bool]
    ini_results: NotRequired[list[tuple[str, dict[str, object]]]]


@dataclass(frozen=True, slots=True)
class _Row:
    """Representa um sistema exibido e seu objeto de aquisição."""

    name: str
    entry: object
    state: str


class _BatchWorker(QThread):
    """Executa downloads em lote fora da thread da interface."""

    progress = Signal(int, int, str)
    message = Signal(str)
    done = Signal(int, int)
    error = Signal(str)

    def __init__(self, operation, entries: list[_Row], parent=None) -> None:
        super().__init__(parent)
        self.operation = operation
        self.entries = entries

    def run(self) -> None:
        ok = failed = 0
        try:
            total = len(self.entries)
            for index, row in enumerate(self.entries, 1):
                self.progress.emit(index - 1, total, row.name)
                try:
                    self.operation(row.entry)
                    ok += 1
                    self.message.emit(f"OK | {row.name}")
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    self.message.emit(f"ERRO | {row.name} | {type(exc).__name__}: {exc}")
            self.progress.emit(total, total, "concluído")
            self.done.emit(ok, failed)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(f"{type(exc).__name__}: {exc}")


class _MameCatalogWorker(QThread):
    """Executa a ingestão do ListXML sem bloquear o Qt."""

    completed = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        try:
            self.completed.emit(MameCatalogService().ingest())
        except MameCatalogError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _MameIniWorker(QThread):
    """Executa a fila de INIs MAME em ordem."""

    message = Signal(str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, database_path, mame_root, parent=None) -> None:
        super().__init__(parent)
        self.database_path = database_path
        self.mame_root = mame_root

    def run(self) -> None:
        results = []
        stages = (
            ("CATLIST", MameClassificationService),
            ("RESOLUTION", MameResolutionService),
            ("VSYNC", MameVsyncService),
        )
        try:
            for index, (name, service_class) in enumerate(stages, 1):
                self.message.emit(f"MAME | INIS | QUEUE | {index}/3 | {name}")
                service = service_class(self.database_path, self.mame_root)
                results.append((name, service.ingest(logger=self.message.emit)))
            self.completed.emit(results)
        except (MameClassificationError, MameResolutionError, MameVsyncError) as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _WHLoaderScanWorker(QThread):
    """Atualiza a base Amiberry WHDLoad fora da thread da interface."""

    completed = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        try:
            self.completed.emit(WHLoaderDataService().scan())
        except WHLoaderDataError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _C64ScanWorker(QThread):
    """Atualiza o manifesto TOSEC de jogos C64 fora da thread da interface."""

    completed = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        try:
            self.completed.emit(C64DataService().scan())
        except C64DataError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class DatSourceTab(QWidget):
    """Aba genérica com seleção individual de sistemas e operações em lote."""

    def __init__(self, title: str, loader, installer, status_checker, parent=None) -> None:
        super().__init__(parent)
        self.title = title
        self.loader = loader
        self.installer = installer
        self.status_checker = status_checker
        self.rows: list[_Row] = []
        self.worker: _BatchWorker | None = None
        self._checks: list[QCheckBox] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.title))
        self.summary = QLabel("Nenhum sistema carregado")
        layout.addWidget(self.summary)
        actions = QHBoxLayout()
        for text, slot, attr in (
            ("BUSCAR DATS", self.search, "search_button"),
            ("INSTALAR SELECIONADOS", self.install_selected, "install_button"),
            ("VERIFICAR ATUALIZAÇÕES", self.check_updates, "update_button"),
            ("SELECIONAR TODOS", self.select_all, "select_button"),
            ("LIMPAR SELEÇÃO", self.clear_selection, "clear_button"),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            setattr(self, attr, button)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.container = QWidget()
        self.rows_layout = QVBoxLayout(self.container)
        self.rows_layout.addStretch()
        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area, 1)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        layout.addWidget(self.log, 1)

    def _append(self, text: str) -> None:
        self.log.appendPlainText(text)
        logger.info("[%s] %s", self.title, text)

    @staticmethod
    def _entry_name(entry) -> str:
        return str(getattr(entry, "name", entry))

    def _entry_state(self, entry) -> str:
        try:
            return str(getattr(self.status_checker(entry), "state", "unknown"))
        except Exception:  # noqa: BLE001
            return "unknown"

    def search(self) -> None:
        self._set_busy(True)
        try:
            entries = tuple(self.loader())
            self.rows = [_Row(self._entry_name(entry), entry, self._entry_state(entry)) for entry in entries]
            self._rebuild_rows()
            self.summary.setText(f"{len(self.rows)} sistemas encontrados")
            self._append(f"BUSCAR | sistemas={len(self.rows)}")
        except Exception as exc:  # noqa: BLE001
            self.rows = []
            self._rebuild_rows()
            self.summary.setText(f"Erro: {exc}")
            self._append(f"ERRO | {type(exc).__name__}: {exc}")
        finally:
            self._set_busy(False)

    def _rebuild_rows(self) -> None:
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self._checks = []
        for row in self.rows:
            check = QCheckBox(f"{self._prefix(row.state)} {row.name}")
            check.setProperty("entry_name", row.name)
            self._checks.append(check)
            self.rows_layout.addWidget(check)
        self.rows_layout.addStretch()

    @staticmethod
    def _prefix(state: str) -> str:
        return {"current": "[OK]", "missing": "[AUSENTE]", "outdated": "[ATUALIZAR]", "unknown": "[?]"}.get(state, "[?]")

    def _selected(self) -> list[_Row]:
        names = {check.property("entry_name") for check in self._checks if check.isChecked()}
        return [row for row in self.rows if row.name in names]

    def select_all(self) -> None:
        for check in self._checks:
            check.setChecked(True)

    def clear_selection(self) -> None:
        for check in self._checks:
            check.setChecked(False)

    def install_selected(self) -> None:
        selected = self._selected()
        if not selected:
            QMessageBox.information(self, self.title, "Selecione pelo menos um sistema.")
            return
        self._start_worker(selected, self.installer)

    def check_updates(self) -> None:
        if not self.rows:
            self.search()
        if not self.rows:
            return
        self.rows = [_Row(row.name, row.entry, self._entry_state(row.entry)) for row in self.rows]
        self._rebuild_rows()
        for check, row in zip(self._checks, self.rows, strict=True):
            check.setChecked(row.state in {"missing", "outdated", "unknown"})
        pending = sum(row.state in {"missing", "outdated", "unknown"} for row in self.rows)
        self.summary.setText(f"{len(self.rows)} sistemas | {pending} precisam de instalação/atualização")
        self._append(f"ATUALIZAÇÕES | candidatos={pending}")

    def _start_worker(self, selected, operation) -> None:
        if self.worker and self.worker.isRunning():
            return
        self._set_busy(True)
        self.worker = _BatchWorker(operation, selected, self)
        self.worker.progress.connect(self._progress)
        self.worker.message.connect(self._append)
        self.worker.done.connect(self._done)
        self.worker.error.connect(lambda msg: self._append(f"ERRO WORKER | {msg}"))
        self.worker.finished.connect(lambda: self._set_busy(False))
        self.worker.start()

    def _progress(self, done: int, total: int, name: str) -> None:
        self.progress.setValue(int(done * 100 / total) if total else 100)
        self.summary.setText(f"Processando {done}/{total} | {name}")

    def _done(self, ok: int, failed: int) -> None:
        self.progress.setValue(100)
        self._append(f"CONCLUÍDO | OK={ok} | FALHAS={failed}")
        self.search()

    def _set_busy(self, busy: bool) -> None:
        for button in (self.search_button, self.install_button, self.update_button, self.select_button, self.clear_button):
            button.setEnabled(not busy)


class _WHLoaderTab(QWidget):
    """Sessão WHLoader integrada ao Scraper de DATs."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.worker: _WHLoaderScanWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("WHLoader — Base WHDLoad"))
        layout.addWidget(QLabel("Fonte: Amiberry Game DB (db.amiberry.com)"))
        actions = QHBoxLayout()
        self.scan_button = QPushButton("ATUALIZAR / SCAN DATA")
        self.scan_button.setToolTip("Baixa, valida e indexa a base WHDLoad do Amiberry.")
        self.scan_button.clicked.connect(self.scan_data)
        actions.addWidget(self.scan_button)
        actions.addStretch()
        layout.addLayout(actions)
        self.status = QLabel("Base WHDLoad ainda não sincronizada nesta sessão.")
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1000)
        layout.addWidget(self.log, 1)

    def _append(self, message: str) -> None:
        self.log.appendPlainText(message)
        logger.info("[WHLoader] %s", message)

    def scan_data(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        self.scan_button.setEnabled(False)
        self.progress.setVisible(True)
        self.status.setText("Baixando e indexando a base WHDLoad…")
        self._append("SCAN | iniciando atualização da base Amiberry")
        self.worker = _WHLoaderScanWorker(self)
        self.worker.completed.connect(self._completed)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _completed(self, result: WHLoaderScanResult) -> None:
        self.status.setText(f"{result.games:,} jogos | {result.slaves:,} slaves | schema {result.schema_version or '—'}")
        self._append(f"OK | jogos={result.games} | slaves={result.slaves}")
        self._append(f"SHA256 | {result.source_hash}")
        self._append(f"RAW | {Path(result.raw_path)}")
        self._append(f"TEMPO | {result.elapsed_seconds:.2f}s")

    def _failed(self, message: str) -> None:
        self.status.setText(f"Erro: {message}")
        self._append(f"ERRO | {message}")

    def _finished(self) -> None:
        self.progress.setVisible(False)
        self.scan_button.setEnabled(True)


class _C64Tab(QWidget):
    """Scan Data do catálogo C64 focado exclusivamente em jogos."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.worker: _C64ScanWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Commodore C64 — GAMES / DAT"))
        layout.addWidget(QLabel("Fonte: TOSEC | escopo exclusivo: Commodore C64 - Games"))
        layout.addWidget(QLabel("Política: jogos em uma única mídia são priorizados; software não-jogo não entra no catálogo."))

        actions = QHBoxLayout()
        self.scan_button = QPushButton("SCAN DATA")
        self.scan_button.setToolTip("Baixa o índice da release TOSEC e registra somente os DATs de jogos C64.")
        self.scan_button.clicked.connect(self.scan_data)
        actions.addWidget(self.scan_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.status = QLabel("Catálogo C64 ainda não sincronizado.")
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1500)
        layout.addWidget(self.log, 1)

    def _append(self, message: str) -> None:
        self.log.appendPlainText(message)
        logger.info("[C64 DAT] %s", message)

    def scan_data(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        self.scan_button.setEnabled(False)
        self.progress.setVisible(True)
        self.status.setText("Consultando release TOSEC e indexando DATs de jogos C64…")
        self._append("SCAN | iniciando catálogo C64")
        self._append("ESCOPO | Commodore C64 - Games")
        self._append("POLÍTICA | single-media priority")
        self.worker = _C64ScanWorker(self)
        self.worker.completed.connect(self._completed)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _completed(self, result: C64ScanResult) -> None:
        self.status.setText(
            f"TOSEC {result.release} | {result.dat_count:,} DATs de jogos | "
            f"{result.game_categories:,} categorias"
        )
        self._append(f"OK | release={result.release}")
        self._append(f"OK | DATs de jogos={result.dat_count:,}")
        self._append(f"OK | categorias={result.game_categories:,}")
        self._append(f"SHA256 | {result.source_hash}")
        self._append(f"RAW | {Path(result.raw_path)}")
        self._append(f"MANIFEST | {Path(result.manifest_path)}")
        self._append(f"TEMPO | {result.elapsed_seconds:.2f}s")

    def _failed(self, message: str) -> None:
        self.status.setText(f"Erro: {message}")
        self._append(f"ERRO | {message}")

    def _finished(self) -> None:
        self.progress.setVisible(False)
        self.scan_button.setEnabled(True)


class _MameTab(QWidget):
    """Sessão MAME do Scraper de DATs."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.service = MameCatalogService()
        self.worker: _MameCatalogWorker | None = None
        self.ini_worker: _MameIniWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("MAME — DAT / Catálogo"))
        self.executable = QLabel("Executável configurado: —")
        layout.addWidget(self.executable)
        self.status = QLabel("Nenhuma operação executada.")
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        self.run_button = QPushButton("OBTER LISTXML (-listxml)")
        self.run_button.clicked.connect(self.ingest)
        actions.addWidget(self.run_button)
        self.ini_button = QPushButton("IMPORTAR INIs")
        self.ini_button.clicked.connect(self.ingest_inis)
        actions.addWidget(self.ini_button)
        self.refresh_button = QPushButton("ATUALIZAR EXECUTÁVEL")
        self.refresh_button.clicked.connect(self.refresh)
        actions.addWidget(self.refresh_button)
        actions.addStretch()
        layout.addLayout(actions)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(3000)
        layout.addWidget(self.log, 1)
        self.refresh()

    def _log(self, level: str, message: str) -> None:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        line = f"{timestamp} | {level:<7} | {message}"
        self.log.appendPlainText(line)
        logger.info("[MAME Scraper] %s", line)

    def refresh(self) -> None:
        try:
            executable = self.service.configured_executable()
            self.executable.setText(f"Executável configurado: {executable}")
            self.run_button.setEnabled(True)
            self.ini_button.setEnabled(True)
            self._log("INFO", f"Executável validado: {executable}")
        except MameCatalogError as exc:
            self.executable.setText("Executável configurado: não definido")
            self.status.setText(str(exc))
            self.run_button.setEnabled(False)
            self.ini_button.setEnabled(False)
            self._log("WARN", str(exc))

    def _set_mame_busy(self, busy: bool) -> None:
        self.run_button.setEnabled(not busy)
        self.ini_button.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy)
        self.progress.setVisible(busy)

    def ingest(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        self.refresh()
        if not self.run_button.isEnabled():
            return
        self._set_mame_busy(True)
        self.status.setText("Executando MAME -listxml…")
        self._log("START", "Iniciando captura do ListXML pelo executável configurado")
        self.worker = _MameCatalogWorker(self)
        self.worker.completed.connect(self._completed)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def ingest_inis(self) -> None:
        if self.ini_worker and self.ini_worker.isRunning():
            return
        try:
            executable = self.service.configured_executable()
        except MameCatalogError as exc:
            self._log("ERROR", str(exc))
            return
        self._set_mame_busy(True)
        self.status.setText("Importando INIs MAME…")
        self._log("START", "Iniciando fila de INIs MAME")
        self._log("INFO", f"Raiz MAME para fontes: {executable.parent}")
        self._log("QUEUE", "1/3 CATLIST → 2/3 RESOLUTION → 3/3 VSYNC")
        self.ini_worker = _MameIniWorker(self.service.DB_FILE, executable.parent, self)
        self.ini_worker.message.connect(lambda msg: self._log("INFO", msg))
        self.ini_worker.completed.connect(self._inis_completed)
        self.ini_worker.failed.connect(self._inis_failed)
        self.ini_worker.finished.connect(self._inis_finished)
        self.ini_worker.start()

    def _inis_completed(self, results: list[tuple[str, dict[str, Any]]]) -> None:
        self.status.setText("Importação dos INIs concluída")
        for name, data in results:
            self._log("OK", f"{name} | entradas={data['entries']:,}")
            self._log("OK", f"{name} | resolvidas={data['resolved']:,}")
            self._log("OK", f"{name} | não resolvidas={data['unresolved']:,}")
            if "duplicates" in data:
                self._log("OK", f"{name} | duplicadas={data['duplicates']:,}")
            self._log("OK", f"{name} | source_id={data['source_id']}")
        self._log("DONE", "Fila de INIs MAME concluída com sucesso")

    def _inis_failed(self, message: str) -> None:
        self.status.setText("Falha na fila de INIs")
        self._log("ERROR", message)
        self._log("DONE", "Fila encerrada; fontes concluídas anteriormente permanecem preservadas")

    def _inis_finished(self) -> None:
        self._set_mame_busy(False)
        self.refresh()

    def _completed(self, result: object) -> None:
        data = cast(_MameCatalogResult, result)
        build = data.get("mame_build") or "não informado"
        source_hash = data.get("source_hash") or "não informado"
        elapsed = float(data.get("elapsed_seconds") or 0.0)
        mode = "REUTILIZADA (mesmo SHA-256)" if data.get("deduplicated") else "NOVA IMPORTAÇÃO"
        if data.get("force"):
            mode = "FORÇADA"
        self.status.setText(f"Concluído | MAME {build} | {data['machine_count']:,} máquinas | {data['display_count']:,} displays | {elapsed:.2f}s")
        self._log("OK", f"Versão/build: {build}")
        self._log("OK", f"Máquinas: {data['machine_count']:,}")
        self._log("OK", f"Displays normalizados: {data['display_count']:,}")
        self._log("OK", f"SHA-256 do ListXML: {source_hash}")
        self._log("OK", f"Política de importação: {mode}")
        self._log("OK", f"XML lossless: {data['xml_path']}")
        self._log("OK", f"Cópia compatível: {data['raw_xml']}")
        self._log("OK", f"Banco: {data['database']}")
        self._log("OK", f"Tempo total: {elapsed:.2f}s")
        self._log("DONE", "Ingestão finalizada com sucesso")

    def _failed(self, message: str) -> None:
        self.status.setText("Falha na ingestão")
        self._log("ERROR", message)
        self._log("DONE", "Ingestão encerrada com erro; dados anteriores foram preservados")

    def _finished(self) -> None:
        self._set_mame_busy(False)
        self.refresh()


class DatScraperPage(QWidget):
    """Agrupa todas as sessões de DAT do SERM V2."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.launchbox = LaunchBoxIntegration()
        self.launchbox_provider = LaunchBoxProvider(self.launchbox)
        self.no_intro = NoIntroArchiveProvider()
        self.redump = RedumpProvider()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._no_intro_tab(), "No-Intro")
        self.tabs.addTab(self._redump_tab(), "Redump")
        self.tabs.addTab(_WHLoaderTab(self), "WHLoader")
        self.tabs.addTab(_C64Tab(self), "C64")
        self.tabs.addTab(_MameTab(self), "MAME")
        layout.addWidget(self.tabs)

    def _no_intro_tab(self) -> DatSourceTab:
        def load():
            entries = self.no_intro.fetch_catalog()
            names = tuple(platform.name for platform in self.launchbox_provider.iter_platforms())
            return self.no_intro.match(names, entries)
        return DatSourceTab("No-Intro — DATs", load, self.no_intro.download, self.no_intro.status, self)

    def _redump_tab(self) -> DatSourceTab:
        def load():
            entries = self.redump.fetch_catalog()
            names = tuple(platform.name for platform in self.launchbox_provider.iter_platforms())
            return self.redump.match(names, entries)
        return DatSourceTab("Redump — DATs", load, self.redump.download, self.redump.status, self)


__all__ = ["DatScraperPage", "DatSourceTab"]
