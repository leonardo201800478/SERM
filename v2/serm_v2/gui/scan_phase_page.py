"""Fase 1 do pipeline: auditoria completa das fontes contra DAT/catalogo."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QListWidget, QMessageBox, QProgressBar, QPushButton, QTabWidget,
    QVBoxLayout, QWidget,
)

from ..runtime.paths import data_root, database_path
from ..services.mame_scan_settings_service import MameScanSettingsService
from ..services.no_intro_scan_service import NoIntroScanService
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
                result = self.service.scan(self.profile)
            else:
                self.service = RomScanService(progress_callback=self.progress.emit, log_callback=self._log)
                result = self.service.scan(self.profile, database=database_path())
            ScanRepository(database_path()).save(result, dat_path=self.target.dat_path)
            self.completed.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def _log(self, level: str, message: str) -> None:
        self.message.emit(f"{level}: {message}")

    def cancel(self) -> None:
        if self.service is not None and hasattr(self.service, "cancel"):
            self.service.cancel()


class _SystemScanTab(QWidget):
    """Editor comum para uma fonte de scan."""

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
            "Esta etapa audita o catálogo completo. Filtros, 1G1R, regiões, traduções, "
            "hacks e seleção de set não participam do scan."
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
        self.source_list.setMinimumHeight(80)
        source_layout.addWidget(self.source_list)
        buttons = QHBoxLayout()
        add = QPushButton("+ ADICIONAR")
        remove = QPushButton("REMOVER")
        add.clicked.connect(self._add_source)
        remove.clicked.connect(self._remove_source)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch()
        source_layout.addLayout(buttons)
        layout.addWidget(source_box)

        actions = QHBoxLayout()
        self.scan_button = QPushButton("INICIAR SCAN COMPLETO")
        self.cancel_button = QPushButton("CANCELAR")
        self.cancel_button.setEnabled(False)
        self.scan_button.clicked.connect(self.start_scan)
        self.cancel_button.clicked.connect(self.cancel_scan)
        actions.addWidget(self.scan_button)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        layout.addLayout(actions)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.status = QLabel("Nenhum scan executado.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.log = QListWidget()
        self.log.setMinimumHeight(120)
        layout.addWidget(self.log, 1)

    def refresh(self) -> None:
        if self.source == "No-Intro":
            self._refresh_no_intro()
        elif self.source == "MAME":
            self.system_combo.clear()
            self.system_combo.addItem("MAME")
        else:
            self.system_combo.clear()
            self.system_combo.addItem(self.source)

    def _refresh_no_intro(self) -> None:
        dat_root = data_root() / "sources" / "no_intro" / "dats"
        files = sorted(dat_root.glob("*.dat"), key=lambda p: p.name.casefold()) if dat_root.is_dir() else []
        self.dat_combo.blockSignals(True)
        self.dat_combo.clear()
        systems: list[str] = []
        for path in files:
            self.dat_combo.addItem(path.name, str(path))
            systems.append(self._system_from_dat(path.name))
        self.dat_combo.blockSignals(False)
        self.system_combo.clear()
        for system in sorted(set(systems), key=str.casefold):
            self.system_combo.addItem(system)
        try:
            self.dat_combo.currentIndexChanged.disconnect(self._dat_changed)
        except (TypeError, RuntimeError):
            pass
        self.dat_combo.currentIndexChanged.connect(self._dat_changed)
        self._dat_changed()

    @staticmethod
    def _system_from_dat(name: str) -> str:
        text = Path(name).stem
        import re
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

    def _add_source(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Selecionar diretório de ROMs")
        if path and not self.source_list.findItems(path, 0) and self.source_list.count() < 3:
            self.source_list.addItem(path)

    def _remove_source(self) -> None:
        row = self.source_list.currentRow()
        if row >= 0:
            self.source_list.takeItem(row)

    def _profile(self) -> Any:
        target = ScanTarget(
            source=self.source,
            system=self.system_combo.currentText().strip(),
            dat_path=self.dat_combo.currentData() if self.source == "No-Intro" else None,
            scan_type=str(self.scan_type.currentData()) if self.source == "MAME" else "full",
        )
        from .filter_profiles_page import FilterProfileData
        profile = FilterProfileData(
            source=target.source,
            system=target.system,
            dat_path=str(target.dat_path) if target.dat_path else None,
            profile_id=f"scan-{target.source.casefold()}-{target.system.casefold().replace(' ', '-')}",
            name=f"SCAN — {target.source} — {target.system}",
            source_directories=[self.source_list.item(i).text() for i in range(self.source_list.count())],
        )
        if self.source == "MAME":
            profile.mame_set_type = "split"
            profile.mame_clone_policy = "with_clones"
            profile.mame_include_bios = True
            profile.mame_include_devices = True
            profile.mame_include_chd = True
            profile.mame_include_optional = True
            profile.mame_working_only = False
            MameScanSettingsService.save(profile.profile_id, target.scan_type)
        return profile

    def start_scan(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        if self.source_list.count() == 0:
            QMessageBox.information(self, "Scan", "Adicione pelo menos um diretório de origem.")
            return
        if self.source == "No-Intro" and self.dat_combo.currentData() is None:
            QMessageBox.information(self, "Scan", "Selecione um DAT No-Intro.")
            return
        profile = self._profile()
        target = ScanTarget(self.source, profile.system, profile.dat_path, str(self.scan_type.currentData()) if self.source == "MAME" else "full")
        self.worker = _PhaseScanWorker(target, profile, self)
        self.scan_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setValue(0)
        self.log.clear()
        self.log.addItem(f"SCAN COMPLETO iniciado — filtros desativados | tipo={target.scan_type}")
        self.worker.progress.connect(self._progress)
        self.worker.message.connect(self.log_message)
        self.worker.completed.connect(self._completed)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _progress(self, done: int, total: int) -> None:
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(done)
        self.status.setText(f"Processando {done:,}/{total:,} itens do catálogo…")

    def log_message(self, message: str) -> None:
        self.log.addItem(message)
        self.log.scrollToBottom()

    def _completed(self, result: object) -> None:
        self.progress.setValue(self.progress.maximum())
        counts = getattr(result, "status_counts", {})
        self.status.setText(f"SCAN CONCLUÍDO | {getattr(result, 'catalog_label', 'catálogo')} | CURRENT={counts.get('CURRENT', 0):,} | MISSING={counts.get('MISSING', 0):,} | WRONG={counts.get('WRONG', 0):,}")
        self.log_message(f"ARQUIVO DE SCAN | {ScanRepository(database_path()).raw_file(getattr(result, 'scan_id', ''))}")

    def _failed(self, message: str) -> None:
        self.status.setText(f"Falha: {message}")
        self.log_message(f"ERRO | {message}")

    def _finished(self) -> None:
        self.scan_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

    def cancel_scan(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.cancel()


class ScanPhasePage(QWidget):
    """Container da primeira fase, separada por família de catálogo."""

    SYSTEMS = ("MAME", "No-Intro", "Redump", "WHLoader", "C64")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("1 — SCAN | AUDITORIA COMPLETA")
        title.setProperty("role", "title")
        layout.addWidget(title)
        description = QLabel("O scan confronta o DAT/catalogo completo com os diretórios de origem e gera um snapshot bruto. Este arquivo é a entrada oficial da fase de filtragem.")
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
            if hasattr(widget, "refresh"):
                widget.refresh()


__all__ = ["ScanPhasePage", "ScanTarget"]
