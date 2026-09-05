"""Scraper unificado de DATs do SERM V2."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
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
from ..services.mame_catalog_service import MameCatalogError, MameCatalogService
from ..services.mame_classification_service import (
    MameClassificationError,
    MameClassificationService,
)
from ..services.mame_resolution_service import MameResolutionError, MameResolutionService
from ..services.mame_vsync_service import MameVsyncError, MameVsyncService
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
        """Processa os sistemas selecionados e publica progresso incremental."""
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
    """Executa a ingestão do ListXML pelo MAME configurado sem bloquear o Qt."""

    completed = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        """Executa ``mame.exe -listxml`` e persiste o catálogo na V2."""
        try:
            self.completed.emit(MameCatalogService().ingest())
        except MameCatalogError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _MameIniWorker(QThread):
    """Executa a fila de INIs MAME em ordem, sem bloquear a interface."""

    message = Signal(str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, database_path, mame_root, parent=None) -> None:
        super().__init__(parent)
        self.database_path = database_path
        self.mame_root = mame_root

    def _log(self, message: str) -> None:
        """Publica uma mensagem de uma etapa da fila."""
        self.message.emit(message)

    def run(self) -> None:
        """Importa CATLIST, Resolution e Vsync como fontes independentes."""
        results = []
        stages = (
            ("CATLIST", MameClassificationService),
            ("RESOLUTION", MameResolutionService),
            ("VSYNC", MameVsyncService),
        )
        try:
            total = len(stages)
            for index, (name, service_class) in enumerate(stages, 1):
                self._log(f"MAME | INIS | QUEUE | {index}/{total} | {name}")
                service = service_class(self.database_path, self.mame_root)
                result = service.ingest(logger=self._log)
                results.append((name, result))
            self.completed.emit(results)
        except (MameClassificationError, MameResolutionError, MameVsyncError) as exc:
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
        self.search_button: QPushButton
        self.install_button: QPushButton
        self.update_button: QPushButton
        self.select_button: QPushButton
        self.clear_button: QPushButton
        self._build_ui()

    def _build_ui(self) -> None:
        """Monta busca, seleção, atualização, progresso e log."""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.title))
        self.summary = QLabel("Nenhum sistema carregado")
        layout.addWidget(self.summary)
        actions = QHBoxLayout()
        actions_config = (
            ("BUSCAR DATS", self.search, "search_button"),
            ("INSTALAR SELECIONADOS", self.install_selected, "install_button"),
            ("VERIFICAR ATUALIZAÇÕES", self.check_updates, "update_button"),
            ("SELECIONAR TODOS", self.select_all, "select_button"),
            ("LIMPAR SELEÇÃO", self.clear_selection, "clear_button"),
        )
        for text, slot, attr in actions_config:
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
        """Registra uma mensagem na interface e no logger."""
        self.log.appendPlainText(text)
        logger.info("[%s] %s", self.title, text)

    @staticmethod
    def _entry_name(entry) -> str:
        """Obtém o nome do sistema de qualquer modelo de catálogo."""
        return str(getattr(entry, "name", entry))

    def _entry_state(self, entry) -> str:
        """Consulta o estado local do DAT."""
        try:
            return str(getattr(self.status_checker(entry), "state", "unknown"))
        except Exception:  # noqa: BLE001
            return "unknown"

    def search(self) -> None:
        """Busca o catálogo e cruza seus sistemas com as plataformas do LaunchBox."""
        self._set_busy(True)
        try:
            entries = tuple(self.loader())
            self.rows = [
                _Row(self._entry_name(entry), entry, self._entry_state(entry)) for entry in entries
            ]
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
        """Reconstrói a lista de sistemas com um check por sistema."""
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
        """Formata o estado do DAT na lista."""
        return {
            "current": "[OK]",
            "missing": "[AUSENTE]",
            "outdated": "[ATUALIZAR]",
            "unknown": "[?]",
        }.get(state, "[?]")

    def _selected(self) -> list[_Row]:
        """Retorna somente os sistemas marcados."""
        names = {check.property("entry_name") for check in self._checks if check.isChecked()}
        return [row for row in self.rows if row.name in names]

    def select_all(self) -> None:
        """Marca todos os sistemas."""
        for check in self._checks:
            check.setChecked(True)

    def clear_selection(self) -> None:
        """Limpa toda a seleção."""
        for check in self._checks:
            check.setChecked(False)

    def install_selected(self) -> None:
        """Instala os DATs selecionados em lote."""
        selected = self._selected()
        if not selected:
            QMessageBox.information(self, self.title, "Selecione pelo menos um sistema.")
            return
        self._start_worker(selected, self.installer)

    def check_updates(self) -> None:
        """Recalcula os estados locais e seleciona os que requerem ação."""
        if not self.rows:
            self.search()
        if not self.rows:
            return
        self.rows = [_Row(row.name, row.entry, self._entry_state(row.entry)) for row in self.rows]
        self._rebuild_rows()
        for check, row in zip(self._checks, self.rows, strict=True):
            check.setChecked(row.state in {"missing", "outdated", "unknown"})
        pending = sum(row.state in {"missing", "outdated", "unknown"} for row in self.rows)
        self.summary.setText(
            f"{len(self.rows)} sistemas | {pending} precisam de instalação/atualização"
        )
        self._append(f"ATUALIZAÇÕES | candidatos={pending}")

    def _start_worker(self, selected, operation) -> None:
        """Executa a operação em background para não bloquear o Qt."""
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
        """Atualiza progresso e descrição do lote."""
        self.progress.setValue(int(done * 100 / total) if total else 100)
        self.summary.setText(f"Processando {done}/{total} | {name}")

    def _done(self, ok: int, failed: int) -> None:
        """Atualiza o catálogo após terminar o lote."""
        self.progress.setValue(100)
        self._append(f"CONCLUÍDO | OK={ok} | FALHAS={failed}")
        self.search()

    def _set_busy(self, busy: bool) -> None:
        """Bloqueia ações conflitantes durante uma operação."""
        for button in (
            self.search_button,
            self.install_button,
            self.update_button,
            self.select_button,
            self.clear_button,
        ):
            button.setEnabled(not busy)


class _MameCatalogWorker(QThread):
    """Executa a ingestão do ListXML pelo MAME configurado sem bloquear o Qt."""

    completed = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        """Executa ``mame.exe -listxml`` e persiste o catálogo na V2."""
        try:
            self.completed.emit(MameCatalogService().ingest())
        except MameCatalogError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _MameIniWorker(QThread):
    """Executa a fila de INIs MAME em ordem, sem bloquear a interface."""

    message = Signal(str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, database_path, mame_root, parent=None) -> None:
        super().__init__(parent)
        self.database_path = database_path
        self.mame_root = mame_root

    def _log(self, message: str) -> None:
        """Publica uma mensagem de uma etapa da fila."""
        self.message.emit(message)

    def run(self) -> None:
        """Importa CATLIST, Resolution e Vsync como fontes independentes."""
        results = []
        stages = (
            ("CATLIST", MameClassificationService),
            ("RESOLUTION", MameResolutionService),
            ("VSYNC", MameVsyncService),
        )
        try:
            total = len(stages)
            for index, (name, service_class) in enumerate(stages, 1):
                self._log(f"MAME | INIS | QUEUE | {index}/{total} | {name}")
                service = service_class(self.database_path, self.mame_root)
                result = service.ingest(logger=self._log)
                results.append((name, result))
            self.completed.emit(results)
        except (MameClassificationError, MameResolutionError, MameVsyncError) as exc:
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
        self.search_button: QPushButton
        self.install_button: QPushButton
        self.update_button: QPushButton
        self.select_button: QPushButton
        self.clear_button: QPushButton
        self._build_ui()

    def _build_ui(self) -> None:
        """Monta busca, seleção, atualização, progresso e log."""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.title))
        self.summary = QLabel("Nenhum sistema carregado")
        layout.addWidget(self.summary)
        actions = QHBoxLayout()
        actions_config = (
            ("BUSCAR DATS", self.search, "search_button"),
            ("INSTALAR SELECIONADOS", self.install_selected, "install_button"),
            ("VERIFICAR ATUALIZAÇÕES", self.check_updates, "update_button"),
            ("SELECIONAR TODOS", self.select_all, "select_button"),
            ("LIMPAR SELEÇÃO", self.clear_selection, "clear_button"),
        )
        for text, slot, attr in actions_config:
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
        """Registra uma mensagem na interface e no logger."""
        self.log.appendPlainText(text)
        logger.info("[%s] %s", self.title, text)

    @staticmethod
    def _entry_name(entry) -> str:
        """Obtém o nome do sistema de qualquer modelo de catálogo."""
        return str(getattr(entry, "name", entry))

    def _entry_state(self, entry) -> str:
        """Consulta o estado local do DAT."""
        try:
            return str(getattr(self.status_checker(entry), "state", "unknown"))
        except Exception:  # noqa: BLE001
            return "unknown"

    def search(self) -> None:
        """Busca o catálogo e cruza seus sistemas com as plataformas do LaunchBox."""
        self._set_busy(True)
        try:
            entries = tuple(self.loader())
            self.rows = [
                _Row(self._entry_name(entry), entry, self._entry_state(entry)) for entry in entries
            ]
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
        """Reconstrói a lista de sistemas com um check por sistema."""
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
        """Formata o estado do DAT na lista."""
        return {
            "current": "[OK]",
            "missing": "[AUSENTE]",
            "outdated": "[ATUALIZAR]",
            "unknown": "[?]",
        }.get(state, "[?]")

    def _selected(self) -> list[_Row]:
        """Retorna somente os sistemas marcados."""
        names = {check.property("entry_name") for check in self._checks if check.isChecked()}
        return [row for row in self.rows if row.name in names]

    def select_all(self) -> None:
        """Marca todos os sistemas."""
        for check in self._checks:
            check.setChecked(True)

    def clear_selection(self) -> None:
        """Limpa toda a seleção."""
        for check in self._checks:
            check.setChecked(False)

    def install_selected(self) -> None:
        """Instala os DATs selecionados em lote."""
        selected = self._selected()
        if not selected:
            QMessageBox.information(self, self.title, "Selecione pelo menos um sistema.")
            return
        self._start_worker(selected, self.installer)

    def check_updates(self) -> None:
        """Recalcula os estados locais e seleciona os que requerem ação."""
        if not self.rows:
            self.search()
        if not self.rows:
            return
        self.rows = [_Row(row.name, row.entry, self._entry_state(row.entry)) for row in self.rows]
        self._rebuild_rows()
        for check, row in zip(self._checks, self.rows, strict=True):
            check.setChecked(row.state in {"missing", "outdated", "unknown"})
        pending = sum(row.state in {"missing", "outdated", "unknown"} for row in self.rows)
        self.summary.setText(
            f"{len(self.rows)} sistemas | {pending} precisam de instalação/atualização"
        )
        self._append(f"ATUALIZAÇÕES | candidatos={pending}")

    def _start_worker(self, selected, operation) -> None:
        """Executa a operação em background para não bloquear o Qt."""
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
        """Atualiza progresso e descrição do lote."""
        self.progress.setValue(int(done * 100 / total) if total else 100)
        self.summary.setText(f"Processando {done}/{total} | {name}")

    def _done(self, ok: int, failed: int) -> None:
        """Atualiza o catálogo após terminar o lote."""
        self.progress.setValue(100)
        self._append(f"CONCLUÍDO | OK={ok} | FALHAS={failed}")
        self.search()

    def _set_busy(self, busy: bool) -> None:
        """Bloqueia ações conflitantes durante uma operação."""
        for button in (
            self.search_button,
            self.install_button,
            self.update_button,
            self.select_button,
            self.clear_button,
        ):
            button.setEnabled(not busy)


class _MameCatalogWorker(QThread):
    """Executa a ingestão do ListXML pelo MAME configurado sem bloquear o Qt."""

    completed = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        """Executa ``mame.exe -listxml`` e persiste o catálogo na V2."""
        try:
            self.completed.emit(MameCatalogService().ingest())
        except MameCatalogError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _MameIniWorker(QThread):
    """Executa a fila de INIs MAME em ordem, sem bloquear a interface."""

    message = Signal(str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, database_path, mame_root, parent=None) -> None:
        super().__init__(parent)
        self.database_path = database_path
        self.mame_root = mame_root

    def _log(self, message: str) -> None:
        """Publica uma mensagem de uma etapa da fila."""
        self.message.emit(message)

    def run(self) -> None:
        """Importa CATLIST, Resolution e Vsync como fontes independentes."""
        results = []
        stages = (
            ("CATLIST", MameClassificationService),
            ("RESOLUTION", MameResolutionService),
            ("VSYNC", MameVsyncService),
        )
        try:
            total = len(stages)
            for index, (name, service_class) in enumerate(stages, 1):
                self._log(f"MAME | INIS | QUEUE | {index}/{total} | {name}")
                service = service_class(self.database_path, self.mame_root)
                result = service.ingest(logger=self._log)
                results.append((name, result))
            self.completed.emit(results)
        except (MameClassificationError, MameResolutionError, MameVsyncError) as exc:
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
        self.search_button: QPushButton
        self.install_button: QPushButton
        self.update_button: QPushButton
        self.select_button: QPushButton
        self.clear_button: QPushButton
        self._build_ui()

    def _build_ui(self) -> None:
        """Monta busca, seleção, atualização, progresso e log."""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.title))
        self.summary = QLabel("Nenhum sistema carregado")
        layout.addWidget(self.summary)
        actions = QHBoxLayout()
        actions_config = (
            ("BUSCAR DATS", self.search, "search_button"),
            ("INSTALAR SELECIONADOS", self.install_selected, "install_button"),
            ("VERIFICAR ATUALIZAÇÕES", self.check_updates, "update_button"),
            ("SELECIONAR TODOS", self.select_all, "select_button"),
            ("LIMPAR SELEÇÃO", self.clear_selection, "clear_button"),
        )
        for text, slot, attr in actions_config:
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
        """Registra uma mensagem na interface e no logger."""
        self.log.appendPlainText(text)
        logger.info("[%s] %s", self.title, text)

    @staticmethod
    def _entry_name(entry) -> str:
        """Obtém o nome do sistema de qualquer modelo de catálogo."""
        return str(getattr(entry, "name", entry))

    def _entry_state(self, entry) -> str:
        """Consulta o estado local do DAT."""
        try:
            return str(getattr(self.status_checker(entry), "state", "unknown"))
        except Exception:  # noqa: BLE001
            return "unknown"

    def search(self) -> None:
        """Busca o catálogo e cruza seus sistemas com as plataformas do LaunchBox."""
        self._set_busy(True)
        try:
            entries = tuple(self.loader())
            self.rows = [
                _Row(self._entry_name(entry), entry, self._entry_state(entry)) for entry in entries
            ]
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
        """Reconstrói a lista de sistemas com um check por sistema."""
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
        """Formata o estado do DAT na lista."""
        return {
            "current": "[OK]",
            "missing": "[AUSENTE]",
            "outdated": "[ATUALIZAR]",
            "unknown": "[?]",
        }.get(state, "[?]")

    def _selected(self) -> list[_Row]:
        """Retorna somente os sistemas marcados."""
        names = {check.property("entry_name") for check in self._checks if check.isChecked()}
        return [row for row in self.rows if row.name in names]

    def select_all(self) -> None:
        """Marca todos os sistemas."""
        for check in self._checks:
            check.setChecked(True)

    def clear_selection(self) -> None:
        """Limpa toda a seleção."""
        for check in self._checks:
            check.setChecked(False)

    def install_selected(self) -> None:
        """Instala os DATs selecionados em lote."""
        selected = self._selected()
        if not selected:
            QMessageBox.information(self, self.title, "Selecione pelo menos um sistema.")
            return
        self._start_worker(selected, self.installer)

    def check_updates(self) -> None:
        """Recalcula os estados locais e seleciona os que requerem ação."""
        if not self.rows:
            self.search()
        if not self.rows:
            return
        self.rows = [_Row(row.name, row.entry, self._entry_state(row.entry)) for row in self.rows]
        self._rebuild_rows()
        for check, row in zip(self._checks, self.rows, strict=True):
            check.setChecked(row.state in {"missing", "outdated", "unknown"})
        pending = sum(row.state in {"missing", "outdated", "unknown"} for row in self.rows)
        self.summary.setText(
            f"{len(self.rows)} sistemas | {pending} precisam de instalação/atualização"
        )
        self._append(f"ATUALIZAÇÕES | candidatos={pending}")

    def _start_worker(self, selected, operation) -> None:
        """Executa a operação em background para não bloquear o Qt."""
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
        """Atualiza progresso e descrição do lote."""
        self.progress.setValue(int(done * 100 / total) if total else 100)
        self.summary.setText(f"Processando {done}/{total} | {name}")

    def _done(self, ok: int, failed: int) -> None:
        """Atualiza o catálogo após terminar o lote."""
        self.progress.setValue(100)
        self._append(f"CONCLUÍDO | OK={ok} | FALHAS={failed}")
        self.search()

    def _set_busy(self, busy: bool) -> None:
        """Bloqueia ações conflitantes durante uma operação."""
        for button in (
            self.search_button,
            self.install_button,
            self.update_button,
            self.select_button,
            self.clear_button,
        ):
            button.setEnabled(not busy)


class _MameCatalogWorker(QThread):
    """Executa a ingestão do ListXML pelo MAME configurado sem bloquear o Qt."""

    completed = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        """Executa ``mame.exe -listxml`` e persiste o catálogo na V2."""
        try:
            self.completed.emit(MameCatalogService().ingest())
        except MameCatalogError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _MameIniWorker(QThread):
    """Executa a fila de INIs MAME em ordem, sem bloquear a interface."""

    message = Signal(str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, database_path, mame_root, parent=None) -> None:
        super().__init__(parent)
        self.database_path = database_path
        self.mame_root = mame_root

    def _log(self, message: str) -> None:
        """Publica uma mensagem de uma etapa da fila."""
        self.message.emit(message)

    def run(self) -> None:
        """Importa CATLIST, Resolution e Vsync como fontes independentes."""
        results = []
        stages = (
            ("CATLIST", MameClassificationService),
            ("RESOLUTION", MameResolutionService),
            ("VSYNC", MameVsyncService),
        )
        try:
            total = len(stages)
            for index, (name, service_class) in enumerate(stages, 1):
                self._log(f"MAME | INIS | QUEUE | {index}/{total} | {name}")
                service = service_class(self.database_path, self.mame_root)
                result = service.ingest(logger=self._log)
                results.append((name, result))
            self.completed.emit(results)
        except (MameClassificationError, MameResolutionError, MameVsyncError) as exc:
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
        self.search_button: QPushButton
        self.install_button: QPushButton
        self.update_button: QPushButton
        self.select_button: QPushButton
        self.clear_button: QPushButton
        self._build_ui()

    def _build_ui(self) -> None:
        """Monta busca, seleção, atualização, progresso e log."""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.title))
        self.summary = QLabel("Nenhum sistema carregado")
        layout.addWidget(self.summary)
        actions = QHBoxLayout()
        actions_config = (
            ("BUSCAR DATS", self.search, "search_button"),
            ("INSTALAR SELECIONADOS", self.install_selected, "install_button"),
            ("VERIFICAR ATUALIZAÇÕES", self.check_updates, "update_button"),
            ("SELECIONAR TODOS", self.select_all, "select_button"),
            ("LIMPAR SELEÇÃO", self.clear_selection, "clear_button"),
        )
        for text, slot, attr in actions_config:
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
        """Registra uma mensagem na interface e no logger."""
        self.log.appendPlainText(text)
        logger.info("[%s] %s", self.title, text)

    @staticmethod
    def _entry_name(entry) -> str:
        """Obtém o nome do sistema de qualquer modelo de catálogo."""
        return str(getattr(entry, "name", entry))

    def _entry_state(self, entry) -> str:
        """Consulta o estado local do DAT."""
        try:
            return str(getattr(self.status_checker(entry), "state", "unknown"))
        except Exception:  # noqa: BLE001
            return "unknown"

    def search(self) -> None:
        """Busca o catálogo e cruza seus sistemas com as plataformas do LaunchBox."""
        self._set_busy(True)
        try:
            entries = tuple(self.loader())
            self.rows = [
                _Row(self._entry_name(entry), entry, self._entry_state(entry)) for entry in entries
            ]
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
        """Reconstrói a lista de sistemas com um check por sistema."""
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
        """Formata o estado do DAT na lista."""
        return {
            "current": "[OK]",
            "missing": "[AUSENTE]",
            "outdated": "[ATUALIZAR]",
            "unknown": "[?]",
        }.get(state, "[?]")

    def _selected(self) -> list[_Row]:
        """Retorna somente os sistemas marcados."""
        names = {check.property("entry_name") for check in self._checks if check.isChecked()}
        return [row for row in self.rows if row.name in names]

    def select_all(self) -> None:
        """Marca todos os sistemas."""
        for check in self._checks:
            check.setChecked(True)

    def clear_selection(self) -> None:
        """Limpa toda a seleção."""
        for check in self._checks:
            check.setChecked(False)

    def install_selected(self) -> None:
        """Instala os DATs selecionados em lote."""
        selected = self._selected()
        if not selected:
            QMessageBox.information(self, self.title, "Selecione pelo menos um sistema.")
            return
        self._start_worker(selected, self.installer)

    def check_updates(self) -> None:
        """Recalcula os estados locais e seleciona os que requerem ação."""
        if not self.rows:
            self.search()
        if not self.rows:
            return
        self.rows = [_Row(row.name, row.entry, self._entry_state(row.entry)) for row in self.rows]
        self._rebuild_rows()
        for check, row in zip(self._checks, self.rows, strict=True):
            check.setChecked(row.state in {"missing", "outdated", "unknown"})
        pending = sum(row.state in {"missing", "outdated", "unknown"} for row in self.rows)
        self.summary.setText(
            f"{len(self.rows)} sistemas | {pending} precisam de instalação/atualização"
        )
        self._append(f"ATUALIZAÇÕES | candidatos={pending}")

    def _start_worker(self, selected, operation) -> None:
        """Executa a operação em background para não bloquear o Qt."""
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
        """Atualiza progresso e descrição do lote."""
        self.progress.setValue(int(done * 100 / total) if total else 100)
        self.summary.setText(f"Processando {done}/{total} | {name}")

    def _done(self, ok: int, failed: int) -> None:
        """Atualiza o catálogo após terminar o lote."""
        self.progress.setValue(100)
        self._append(f"CONCLUÍDO | OK={ok} | FALHAS={failed}")
        self.search()

    def _set_busy(self, busy: bool) -> None:
        """Bloqueia ações conflitantes durante uma operação."""
        for button in (
            self.search_button,
            self.install_button,
            self.update_button,
            self.select_button,
            self.clear_button,
        ):
            button.setEnabled(not busy)


class _MameTab(QWidget):
    """Sessão MAME do Scraper de DATs com fila única de importação de INIs."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.service = MameCatalogService()
        self.worker: _MameCatalogWorker | None = None
        self.ini_worker: _MameIniWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        """Monta a sessão MAME com ListXML e a fila de INIs."""
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
        self.ini_button.setToolTip("Processa CATLIST, Resolution e Vsync em fila independente.")
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
        """Adiciona uma entrada operacional padronizada com timestamp UTC."""
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        line = f"{timestamp} | {level:<7} | {message}"
        self.log.appendPlainText(line)
        logger.info("[MAME Scraper] %s", line)

    def refresh(self) -> None:
        """Mostra o executável MAME atualmente selecionado em Diretórios."""
        try:
            executable = self.service.configured_executable()
            self.executable.setText(f"Executável configurado: {executable}")
        except MameCatalogError as exc:
            self.executable.setText(f"Executável configurado: {exc}")

    def ingest(self) -> None:
        """Inicia a captura assíncrona do ListXML."""
        if self.worker and self.worker.isRunning():
            return
        self._set_mame_busy(True)
        self.status.setText("Capturando ListXML do MAME…")
        self._log("START", "Iniciando aquisição do catálogo ListXML")
        self.worker = _MameCatalogWorker(self)
        self.worker.completed.connect(self._completed)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def ingest_inis(self) -> None:
        """Inicia a fila independente de CATLIST, Resolution e Vsync."""
        if self.ini_worker and self.ini_worker.isRunning():
            return
        try:
            executable = self.service.configured_executable()
        except MameCatalogError as exc:
            self._failed(str(exc))
            return
        self._set_mame_busy(True)
        self.status.setText("Importando INIs MAME…")
        self._log("START", "Iniciando fila de INIs MAME")
        self.ini_worker = _MameIniWorker(self.service.DB_FILE, executable.parent, self)
        self.ini_worker.message.connect(lambda message: self._log("INFO", message))
        self.ini_worker.completed.connect(self._inis_completed)
        self.ini_worker.failed.connect(self._inis_failed)
        self.ini_worker.finished.connect(self._inis_finished)
        self.ini_worker.start()

    def _set_mame_busy(self, busy: bool) -> None:
        """Bloqueia ações do painel MAME durante uma operação."""
        self.run_button.setEnabled(not busy)
        self.ini_button.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy)
        self.progress.setVisible(busy)

    def _inis_completed(self, results: object) -> None:
        """Registra o resultado agregado de cada etapa da fila de INIs."""
        if not isinstance(results, list):
            self._inis_failed("Resultado inesperado da fila de INIs.")
            return
        for item in results:
            if not isinstance(item, tuple) or len(item) != 2:
                self._inis_failed("Resultado inválido retornado pela fila de INIs.")
                return
            name, result = item
            if not isinstance(name, str) or not isinstance(result, dict):
                self._inis_failed("Resultado inválido retornado pela fila de INIs.")
                return
            data = result
            self._log("OK", f"{name} | lidos={data['read']:,}")
            self._log("OK", f"{name} | atualizados={data['upserted']:,}")
            self._log("OK", f"{name} | ignorados={data['skipped']:,}")
            self._log("OK", f"{name} | inválidos={data['invalid']:,}")
            self._log("OK", f"{name} | duplicadas={data['duplicates']:,}")
            self._log("OK", f"{name} | source_id={data['source_id']}")
            self._log("DONE", f"Fonte {name} concluída")
        self._log("DONE", "Fila de INIs MAME concluída com sucesso")

    def _inis_failed(self, message: str) -> None:
        """Registra a falha da fila sem esconder qual etapa falhou."""
        self.status.setText("Falha na fila de INIs")
        self._log("ERROR", message)
        self._log("DONE", "Fila encerrada; fontes concluídas anteriormente permanecem preservadas")

    def _inis_finished(self) -> None:
        """Libera os controles após terminar a fila de INIs."""
        self._set_mame_busy(False)
        self.refresh()

    def _completed(self, result: object) -> None:
        """Exibe métricas, proveniência e política de deduplicação da ingestão."""
        data = cast(_MameCatalogResult, result)
        build = data.get("mame_build") or "não informado"
        source_hash = data.get("source_hash") or "não informado"
        elapsed = float(data.get("elapsed_seconds") or 0.0)
        mode = "REUTILIZADA (mesmo SHA-256)" if data.get("deduplicated") else "NOVA IMPORTAÇÃO"
        if data.get("force"):
            mode = "FORÇADA"
        self.status.setText(
            f"Concluído | MAME {build} | {data['machine_count']:,} máquinas | {data['display_count']:,} displays | {elapsed:.2f}s"
        )
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
        """Exibe a falha sem ocultar a causa original."""
        self.status.setText("Falha na ingestão")
        self._log("ERROR", message)
        self._log("DONE", "Ingestão encerrada com erro; dados anteriores foram preservados")

    def _finished(self) -> None:
        """Libera os controles após a thread terminar."""
        self._set_mame_busy(False)
        self.refresh()


class DatScraperPage(QWidget):
    """Agrupa todas as sessões de DAT solicitadas pelo usuário."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(_MameTab(self), "MAME")
        tabs.addTab(self._build_no_intro_tab(), "No-Intro")
        tabs.addTab(self._build_redump_tab(), "Redump")
        tabs.addTab(self._build_historical_tab(), "Histórico")
        layout.addWidget(tabs)

    def _build_no_intro_tab(self) -> QWidget:
        """Cria a aba No-Intro com integração LaunchBox."""
        integration = NoIntroArchiveProvider()
        launchbox = LaunchBoxIntegration()
        provider = LaunchBoxProvider(launchbox)
        return DatSourceTab(
            "No-Intro — DATs por sistema",
            integration.list_systems,
            integration.install,
            integration.status,
            self,
        )

    def _build_redump_tab(self) -> QWidget:
        """Cria a aba Redump com integração LaunchBox."""
        integration = RedumpProvider()
        launchbox = LaunchBoxIntegration()
        provider = LaunchBoxProvider(launchbox)
        return DatSourceTab(
            "Redump — DATs por sistema",
            integration.list_systems,
            integration.install,
            integration.status,
            self,
        )

    def _build_historical_tab(self) -> QWidget:
        """Cria a aba histórica com provedores legados preservados."""
        return DatSourceTab(
            "Histórico — fontes legadas",
            lambda: (),
            lambda _entry: None,
            lambda _entry: type("Status", (), {"state": "unknown"})(),
            self,
        )


__all__ = ["DatScraperPage"]
