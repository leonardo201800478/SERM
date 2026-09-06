"""Fase 1 do pipeline: auditoria completa das fontes contra DAT/catalogo."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root, database_path
from ..services.mame_scan_settings_service import MameScanSettingsService
from ..services.no_intro_scan_service import NoIntroScanService
from ..services.rom_scan_engine import StableRomScanService
from ..services.rom_scan_service import RomScanService
from ..services.scan_repository import ScanRepository


@dataclass(frozen=True, slots=True)
class ScanTarget:
    source: str
    system: str
    dat_path: str | None = None
    scan_type: str = "full"


class _PhaseScanWorker(QThread):
    progress = Signal(int, int)
    message = Signal(str)
    state_changed = Signal(str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, target: ScanTarget, profile: Any, parent=None) -> None:
        super().__init__(parent)
        self.target = target
        self.profile = profile
        self.service: Any | None = None

    def run(self) -> None:
        try:
            if self.target.source == "No-Intro":
                self.service = NoIntroScanService(progress_callback=self.progress.emit)
                self.state_changed.emit("running")
                result = self.service.scan(self.profile)
            elif self.target.source == "MAME":
                self.service = StableRomScanService(
                    progress_callback=self.progress.emit,
                    log_callback=self._log,
                )
                self.state_changed.emit("running")
                result = self.service.scan(self.profile, database=database_path())
            else:
                self.service = RomScanService(
                    progress_callback=self.progress.emit,
                    log_callback=self._log,
                )
                self.state_changed.emit("running")
                result = self.service.scan(self.profile, database=database_path())
            ScanRepository(database_path()).save(result, dat_path=self.target.dat_path)
            self.state_changed.emit("completed")
            self.completed.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.state_changed.emit("failed")
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def _log(self, level: str, message: str) -> None:
        self.message.emit(f"{level}: {message}")

    def pause(self) -> None:
        if isinstance(self.service, StableRomScanService):
            self.service.pause()
            self.state_changed.emit("paused")

    def resume(self) -> None:
        if isinstance(self.service, StableRomScanService):
            self.service.resume()
            self.state_changed.emit("running")

    def cancel(self) -> None:
        if self.service is not None and hasattr(self.service, "cancel"):
            self.service.cancel()
            self.state_changed.emit("cancelling")


class _SystemScanTab(QWidget):
    """Interface completa de uma fonte de scan, sem filtros."""

    MAX_SOURCES = 3

    def __init__(self, source: str, parent=None) -> None:
        super().__init__(parent)
        self.source = source
        self.worker: _PhaseScanWorker | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel(f"{self.source} — SCAN COMPLETO")
        title.setProperty("role", "title")
        layout.addWidget(title)
        explanation = QLabel(
            "Esta etapa audita o catálogo/DAT completo. Nenhum filtro, 1G1R, região, "
            "tradução, hack, clone ou seleção de set interfere no resultado."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        config = QGroupBox("Alvo do scan")
        form = QFormLayout(config)
        self.system_combo = QComboBox()
        form.addRow("Sistema:", self.system_combo)

        self.dat_combo = QComboBox()
        self.dat_combo.setVisible(self.source == "No-Intro")
        form.addRow("DAT:", self.dat_combo)

        self.scan_type = QComboBox()
        self.scan_type.addItem("Arcade", "arcade")
        self.scan_type.addItem("Software", "software")
        self.scan_type.addItem("Completa", "both")
        self.scan_type.setVisible(self.source == "MAME")
        form.addRow("Tipo:", self.scan_type)
        layout.addWidget(config)

        source_box = QGroupBox("Diretórios de origem")
        source_layout = QVBoxLayout(source_box)
        self.source_list = QListWidget()
        self.source_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.source_list.setMinimumHeight(90)
        source_layout.addWidget(self.source_list)

        buttons = QHBoxLayout()
        self.add_source_button = QPushButton("+ ADICIONAR DIRETÓRIO")
        self.remove_source_button = QPushButton("REMOVER DIRETÓRIO")
        self.clear_sources_button = QPushButton("LIMPAR")
        self.add_source_button.clicked.connect(self._add_source)
        self.remove_source_button.clicked.connect(self._remove_source)
        self.clear_sources_button.clicked.connect(self._clear_sources)
        buttons.addWidget(self.add_source_button)
        buttons.addWidget(self.remove_source_button)
        buttons.addWidget(self.clear_sources_button)
        buttons.addStretch()
        source_layout.addLayout(buttons)
        self.source_hint = QLabel(f"0/{self.MAX_SOURCES} diretórios configurados")
        source_layout.addWidget(self.source_hint)
        layout.addWidget(source_box)

        actions = QHBoxLayout()
        self.scan_button = QPushButton("INICIAR SCAN COMPLETO")
        self.pause_button = QPushButton("PAUSAR")
        self.resume_button = QPushButton("RETOMAR")
        self.cancel_button = QPushButton("CANCELAR")
        self.scan_button.clicked.connect(self.start_scan)
        self.pause_button.clicked.connect(self.pause_scan)
        self.resume_button.clicked.connect(self.resume_scan)
        self.cancel_button.clicked.connect(self.cancel_scan)
        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        actions.addWidget(self.scan_button)
        actions.addWidget(self.pause_button)
        actions.addWidget(self.resume_button)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)
        self.status = QLabel("Nenhum scan executado.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.log = QListWidget()
        self.log.setMinimumHeight(120)
        layout.addWidget(self.log, 1)

        self.system_combo.currentIndexChanged.connect(self._selection_changed)
        self.dat_combo.currentIndexChanged.connect(self._dat_changed)
        self.scan_type.currentIndexChanged.connect(self._scan_type_changed)

    def refresh(self) -> None:
        if self.source == "No-Intro":
            self._refresh_no_intro()
        elif self.source == "MAME":
            self.system_combo.blockSignals(True)
            self.system_combo.clear()
            self.system_combo.addItem("MAME")
            self.system_combo.blockSignals(False)
            self._restore_mame_scan_type()
        else:
            self.system_combo.blockSignals(True)
            self.system_combo.clear()
            self.system_combo.addItem(self.source)
            self.system_combo.blockSignals(False)
        self._update_source_controls()
        self._update_action_controls()

    def _refresh_no_intro(self) -> None:
        dat_root = data_root() / "sources" / "no_intro" / "dats"
        files = (
            sorted(dat_root.glob("*.dat"), key=lambda p: p.name.casefold())
            if dat_root.is_dir()
            else []
        )
        self.dat_combo.blockSignals(True)
        self.dat_combo.clear()
        systems: list[str] = []
        for path in files:
            self.dat_combo.addItem(path.name, str(path))
            systems.append(self._system_from_dat(path.name))
        self.dat_combo.blockSignals(False)

        self.system_combo.blockSignals(True)
        self.system_combo.clear()
        for system in sorted(set(systems), key=str.casefold):
            self.system_combo.addItem(system)
        self.system_combo.blockSignals(False)
        self._dat_changed()

    @staticmethod
    def _system_from_dat(name: str) -> str:
        text = Path(name).stem
        text = re.sub(r" \(Parent-Clone\)$", "", text)
        text = re.sub(r" \(\d{8}-\d{6}\)$", "", text)
        return text

    def _dat_changed(self, *_args) -> None:
        if self.source != "No-Intro":
            return
        index = self.dat_combo.currentIndex()
        if index < 0:
            return
        system = self._system_from_dat(self.dat_combo.itemText(index))
        match = self.system_combo.findText(system)
        if match >= 0:
            self.system_combo.setCurrentIndex(match)
        self._selection_changed()

    def _selection_changed(self, *_args) -> None:
        self._update_source_controls()

    def _scan_type_changed(self, *_args) -> None:
        if self.source == "MAME":
            value = str(self.scan_type.currentData() or "arcade")
            MameScanSettingsService.save(self._settings_profile_id(), value)
            self.status.setText(f"Tipo de scan MAME selecionado: {self.scan_type.currentText()}.")

    def _settings_profile_id(self) -> str:
        return "scan-mame-mame"

    def _restore_mame_scan_type(self) -> None:
        value = MameScanSettingsService.load(self._settings_profile_id())
        index = self.scan_type.findData(value)
        if index < 0:
            index = self.scan_type.findData("arcade")
        self.scan_type.blockSignals(True)
        self.scan_type.setCurrentIndex(max(index, 0))
        self.scan_type.blockSignals(False)

    def _update_source_controls(self) -> None:
        running = bool(self.worker and self.worker.isRunning())
        count = self.source_list.count()
        self.source_hint.setText(f"{count}/{self.MAX_SOURCES} diretórios configurados")
        enabled = not running
        self.add_source_button.setEnabled(count < self.MAX_SOURCES and enabled)
        self.remove_source_button.setEnabled(count > 0 and enabled)
        self.clear_sources_button.setEnabled(count > 0 and enabled)

    def _update_action_controls(self) -> None:
        running = bool(self.worker and self.worker.isRunning())
        mame = self.source == "MAME"
        paused = bool(
            mame
            and self.worker is not None
            and isinstance(self.worker.service, StableRomScanService)
            and self.worker.service.paused
        )
        self.scan_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.pause_button.setEnabled(running and mame and not paused)
        self.resume_button.setEnabled(running and mame and paused)

    def _add_source(self) -> None:
        if self.source_list.count() >= self.MAX_SOURCES:
            QMessageBox.information(
                self,
                "Diretórios",
                f"O limite é de {self.MAX_SOURCES} diretórios por scan.",
            )
            return
        path = QFileDialog.getExistingDirectory(self, "Selecionar diretório de ROMs")
        if not path:
            return
        path = str(Path(path).expanduser().resolve())
        for index in range(self.source_list.count()):
            if Path(self.source_list.item(index).text()).resolve() == Path(path):
                QMessageBox.information(
                    self,
                    "Diretórios",
                    "Esse diretório já está configurado.",
                )
                return
        self.source_list.addItem(path)
        self._update_source_controls()

    def _remove_source(self) -> None:
        row = self.source_list.currentRow()
        if row < 0:
            QMessageBox.information(
                self,
                "Diretórios",
                "Selecione um diretório para remover.",
            )
            return
        self.source_list.takeItem(row)
        self._update_source_controls()

    def _clear_sources(self) -> None:
        self.source_list.clear()
        self._update_source_controls()

    def _profile(self) -> Any:
        target = ScanTarget(
            source=self.source,
            system=self.system_combo.currentText().strip(),
            dat_path=self.dat_combo.currentData() if self.source == "No-Intro" else None,
            scan_type=(str(self.scan_type.currentData()) if self.source == "MAME" else "full"),
        )
        from .filter_profiles_page import FilterProfileData

        profile = FilterProfileData(
            source=target.source,
            system=target.system,
            dat_path=str(target.dat_path) if target.dat_path else None,
            profile_id=(
                f"scan-{target.source.casefold()}-{target.system.casefold().replace(' ', '-')}"
            ),
            name=f"SCAN — {target.source} — {target.system}",
            source_directories=[
                self.source_list.item(i).text() for i in range(self.source_list.count())
            ],
        )
        if self.source == "MAME":
            profile.mame_set_type = "split"
            profile.mame_clone_policy = "with_clones"
            profile.mame_include_bios = True
            profile.mame_include_devices = True
            profile.mame_include_chd = True
            profile.mame_include_optional = True
            profile.mame_working_only = False
        return profile

    def start_scan(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        if self.source_list.count() == 0:
            QMessageBox.information(
                self,
                "Scan",
                "Adicione pelo menos um diretório de origem.",
            )
            return
        if self.source == "No-Intro" and self.dat_combo.currentData() is None:
            QMessageBox.information(self, "Scan", "Selecione um DAT No-Intro.")
            return

        profile = self._profile()
        self.worker = _PhaseScanWorker(
            ScanTarget(
                self.source,
                profile.system,
                profile.dat_path,
                profile.scan_type,
            ),
            profile,
            self,
        )
        self.scan_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.pause_button.setEnabled(self.source == "MAME")
        self.resume_button.setEnabled(False)
        self.progress.setMaximum(0)
        self.progress.setValue(0)
        self.log.clear()
        self.log.addItem("SCAN COMPLETO iniciado — filtros desativados")
        self._update_source_controls()
        self.worker.progress.connect(self._progress)
        self.worker.message.connect(self.log_message)
        self.worker.state_changed.connect(self._worker_state_changed)
        self.worker.completed.connect(self._completed)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _progress(self, done: int, total: int) -> None:
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(min(done, max(total, 1)))
        self.status.setText(f"Processando {done:,}/{total:,} itens do catálogo…")

    def log_message(self, message: str) -> None:
        self.log.addItem(message)
        self.log.scrollToBottom()

    def _worker_state_changed(self, state: str) -> None:
        messages = {
            "paused": "SCAN PAUSADO — checkpoint cooperativo ativo.",
            "running": "SCAN EM EXECUÇÃO.",
            "cancelling": "CANCELAMENTO solicitado; aguardando encerramento seguro…",
        }
        if state in messages:
            self.status.setText(messages[state])
        self._update_action_controls()
        self._update_source_controls()

    def _completed(self, result: object) -> None:
        self.progress.setMaximum(max(self.progress.maximum(), 1))
        self.progress.setValue(self.progress.maximum())
        counts = getattr(result, "status_counts", {})
        self.status.setText(
            f"SCAN CONCLUÍDO | {getattr(result, 'catalog_label', 'catálogo')} | "
            f"CURRENT={counts.get('CURRENT', 0):,} | "
            f"MISSING={counts.get('MISSING', 0):,} | "
            f"WRONG={counts.get('WRONG', 0):,}"
        )
        completed_result = cast(Any, result)
        path = ScanRepository(database_path()).raw_file(completed_result.scan_id)
        self.log_message(f"ARQUIVO DE SCAN | {path or 'não localizado'}")

    def _failed(self, message: str) -> None:
        self.status.setText(f"Falha: {message}")
        self.log_message(f"ERRO | {message}")

    def _finished(self) -> None:
        self.scan_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(False)
        self._update_source_controls()

    def pause_scan(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.pause()

    def resume_scan(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.resume()

    def cancel_scan(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status.setText(
                "Cancelamento solicitado; aguardando o encerramento seguro do scanner…"
            )


class ScanPhasePage(QWidget):
    """Container da primeira fase, separada por família de catálogo."""

    SYSTEMS = ("MAME", "No-Intro", "Redump", "WHLoader", "C64")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("1 — SCAN | AUDITORIA COMPLETA")
        title.setProperty("role", "title")
        layout.addWidget(title)
        description = QLabel(
            "O scan confronta o DAT/catalogo completo com os diretórios de origem e gera "
            "um snapshot bruto. Este arquivo é a entrada oficial da fase de filtragem."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("scanSystemTabs")
        for source in self.SYSTEMS:
            self.tabs.addTab(_SystemScanTab(source, self), source)
        layout.addWidget(self.tabs, 1)

    def refresh(self) -> None:
        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            refresh = getattr(widget, "refresh", None) if widget is not None else None
            if callable(refresh):
                refresh()


__all__ = ["ScanPhasePage", "ScanTarget"]
