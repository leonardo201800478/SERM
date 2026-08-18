"""Aba Reconstrução de ROMs."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QComboBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget

from app.config.app_config import AppConfig
from app.gui.widgets.log_panel import LogPanel
from app.gui.widgets.reconstruction_tree_widget import ReconstructionTreeWidget
from app.mame.reconstruction_service import ReconstructionService

logger = logging.getLogger(__name__)


class ReconstructionWorker(QThread):
    """Executa a reconstrução fora da thread principal do Qt."""
    progress = Signal(int, int, str)
    log = Signal(str)
    finished_result = Signal(object)
    failed = Signal(str)

    def __init__(self, manifest: Path, source_paths: list[Path], destination: Path,
                 set_type: str, copy_perfect: bool, repair: bool, residual: Path) -> None:
        super().__init__()
        self.manifest = manifest
        self.source_paths = source_paths
        self.destination = destination
        self.set_type = set_type
        self.copy_perfect = copy_perfect
        self.repair = repair
        self.residual = residual

    def run(self) -> None:
        try:
            machines = ReconstructionService.load_manifest(self.manifest)
            service = ReconstructionService(self.source_paths, self.destination,
                                            progress_callback=lambda c, t, m: self.progress.emit(c, t, m),
                                            log_callback=self.log.emit)
            result = service.reconstruct(machines, set_type=self.set_type,
                                         copy_perfect=self.copy_perfect, repair=self.repair)
            service.write_residual_manifest(self.residual, result.unresolved,
                                            source_manifest=self.manifest, set_type=self.set_type)
            self.finished_result.emit(result)
        except Exception as exc:
            logger.exception("Falha na reconstrução")
            self.failed.emit(str(exc))


class ReconstructionTab(QWidget):
    """Interface de cópia/reparo do set atual."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.parent_widget = parent
        self.config = AppConfig()
        self.manifest_path = self._scan_dir() / "current_scan.jsonl"
        self.worker: ReconstructionWorker | None = None
        self.machines = []
        self._build_ui()
        self._load_manifest()

    def _scan_dir(self) -> Path:
        path = Path(__file__).resolve().parents[3] / "data" / "database" / "scan"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        controls = QGroupBox("Reconstrução do set")
        row = QHBoxLayout(controls)
        self.copy_button = QPushButton("Copiar ROMs perfeitas")
        self.repair_button = QPushButton("Reparar ROMs")
        self.all_button = QPushButton("Copiar + Reparar")
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setEnabled(False)
        self.set_combo = QComboBox()
        self.set_combo.addItem("Split", ReconstructionService.SET_SPLIT)
        self.set_combo.addItem("Merged", ReconstructionService.SET_MERGED)
        self.set_combo.addItem("Non-Merged", ReconstructionService.SET_NON_MERGED)
        self.manifest_label = QLabel()
        row.addWidget(self.copy_button)
        row.addWidget(self.repair_button)
        row.addWidget(self.all_button)
        row.addWidget(QLabel("Tipo:"))
        row.addWidget(self.set_combo)
        row.addWidget(self.cancel_button)
        row.addStretch()
        root.addWidget(controls)
        root.addWidget(self.manifest_label)
        self.tree = ReconstructionTreeWidget(self)
        self.tree.repair_requested.connect(self._context_action)
        root.addWidget(self.tree, 1)

        footer = QGroupBox("Execução")
        footer_layout = QVBoxLayout(footer)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress_label = QLabel("Pronto")
        self.count_label = QLabel("Copiadas: 0 | Reparadas: 0 | Externas: 0 | Pendentes: 0")
        footer_layout.addWidget(self.progress)
        footer_layout.addWidget(self.progress_label)
        footer_layout.addWidget(self.count_label)
        self.log_panel = LogPanel(self, logger_name="app.mame.reconstruction_service")
        footer_layout.addWidget(self.log_panel)
        root.addWidget(footer)

        self.copy_button.clicked.connect(lambda: self._start(copy_perfect=True, repair=False))
        self.repair_button.clicked.connect(lambda: self._start(copy_perfect=False, repair=True))
        self.all_button.clicked.connect(lambda: self._start(copy_perfect=True, repair=True))
        self.cancel_button.clicked.connect(self._cancel)

    def _load_manifest(self) -> None:
        """Carrega o manifesto corrente herdado da aba Scan Roms."""
        try:
            if not self.manifest_path.is_file():
                self.manifest_label.setText("Manifesto: current_scan.jsonl não encontrado")
                self.tree.clear()
                return
            self.machines = ReconstructionService.load_manifest(self.manifest_path)
            self.tree.set_data(self.machines)
            self.manifest_label.setText(f"Manifesto: {self.manifest_path} | Machines: {len(self.machines)}")
        except Exception as exc:
            self.manifest_label.setText(f"Erro ao carregar manifesto: {exc}")

    def refresh(self) -> None:
        """Recarrega o current_scan.jsonl após um novo scan."""
        if self.worker is None or not self.worker.isRunning():
            self.manifest_path = self._scan_dir() / "current_scan.jsonl"
            self._load_manifest()

    def _source_paths(self) -> list[Path]:
        return [Path(p) for p in (getattr(self.config, "source_dirs", []) or [])]

    def _destination(self) -> Path:
        value = getattr(self.config, "destination_dir", None)
        if not value:
            raise RuntimeError("Diretório de destino não configurado na aba Scan Roms.")
        return Path(value)

    def _start(self, *, copy_perfect: bool, repair: bool) -> None:
        if self.worker and self.worker.isRunning():
            return
        if not self.manifest_path.is_file():
            QMessageBox.warning(self, "Reconstrução", "Execute o Scan Roms antes da reconstrução.")
            return
        try:
            destination = self._destination()
        except Exception as exc:
            QMessageBox.warning(self, "Reconstrução", str(exc))
            return
        residual = self._scan_dir() / "current_reconstruction.jsonl"
        self.progress.setValue(0)
        self.count_label.setText("Copiadas: 0 | Reparadas: 0 | Externas: 0 | Pendentes: 0")
        self._set_running(True)
        self.worker = ReconstructionWorker(self.manifest_path, self._source_paths(), destination,
                                           self.set_combo.currentData(), copy_perfect, repair, residual)
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._append_log)
        self.worker.finished_result.connect(self._finished)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(lambda: self._set_running(False))
        self.worker.start()

    def _context_action(self, data: dict) -> None:
        """Executa reparo individual usando a mesma engine da reconstrução."""
        if data.get("action") == "details":
            rom = data.get("rom")
            QMessageBox.information(self, "ROM", f"{rom.rom_name}\nCRC: {rom.expected_crc}\nTamanho: {rom.expected_size}")
            return
        machine = data.get("machine")
        if not machine:
            return
        try:
            destination = self._destination()
            service = ReconstructionService(self._source_paths(), destination, log_callback=logger.info)
            result = service.reconstruct([machine], set_type=self.set_combo.currentData(), copy_perfect=False, repair=True)
            service.write_residual_manifest(self._scan_dir() / "current_reconstruction.jsonl", result.unresolved,
                                            source_manifest=self.manifest_path, set_type=self.set_combo.currentData())
            self._load_manifest()
        except Exception as exc:
            QMessageBox.warning(self, "Reparo", str(exc))

    def _on_progress(self, current: int, total: int, message: str) -> None:
        percent = int((current / total) * 100) if total else 100
        self.progress.setValue(max(0, min(100, percent)))
        self.progress_label.setText(message)

    def _append_log(self, message: str) -> None:
        logger.info(message)

    def _finished(self, result) -> None:
        self.count_label.setText(f"Copiadas: {result.copied} | Reparadas: {result.repaired} | Externas: {result.external} | Pendentes: {len(result.unresolved)}")
        self.progress.setValue(100)
        self.progress_label.setText("Reconstrução concluída; manifesto residual gerado.")
        self._load_manifest()

    def _failed(self, message: str) -> None:
        self.progress_label.setText("Reconstrução interrompida por erro.")
        QMessageBox.critical(self, "Reconstrução", message)

    def _cancel(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.progress_label.setText("Cancelamento solicitado; aguardando término seguro...")

    def _set_running(self, running: bool) -> None:
        for button in (self.copy_button, self.repair_button, self.all_button):
            button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
