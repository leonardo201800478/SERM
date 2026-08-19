"""Aba Reconstrução de ROMs baseada exclusivamente no current_scan.jsonl."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QComboBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget

from app.config.app_config import AppConfig
from app.gui.widgets.log_panel import LogPanel
from app.gui.widgets.reconstruction_tree_widget import ReconstructionTreeWidget
from app.mame.reconstruction_engine import ReconstructionEngine
from app.mame.rom_repair_engine import SingleRomRepairEngine

logger = logging.getLogger(__name__)


class ReconstructionWorker(QThread):
    """Executa a reconstrução fora da thread principal do Qt."""
    progress = Signal(int, int, str)
    log = Signal(str)
    finished_result = Signal(object)
    failed = Signal(str)

    def __init__(self, manifest: Path, source_paths: list[Path], destination: Path, set_type: str, copy_perfect: bool, repair: bool, residual: Path) -> None:
        super().__init__()
        self.manifest = manifest
        self.source_paths = source_paths
        self.destination = destination
        self.set_type = set_type
        self.copy_perfect = copy_perfect
        self.repair = repair
        self.residual = residual
        self.service: ReconstructionEngine | None = None

    def run(self) -> None:
        try:
            self.log.emit(f"Carregando manifesto físico v2: {self.manifest}")
            header = ReconstructionEngine.load_manifest_header(self.manifest)
            machines = ReconstructionEngine.load_manifest(self.manifest)
            manifest_sources = [Path(p) for p in header.get("source_paths", []) if p]
            if manifest_sources:
                self.source_paths = manifest_sources
            self.log.emit(f"Manifesto carregado: {len(machines)} machines | origem(ns): {len(self.source_paths)}")
            self.log.emit("A reconstrução NÃO executará novo scan. As fontes serão consultadas somente pelas localizações registradas no manifesto.")
            self.service = ReconstructionEngine(
                self.source_paths,
                self.destination,
                progress_callback=lambda c, t, m: self.progress.emit(c, t, m),
                log_callback=self.log.emit,
            )
            result = self.service.reconstruct(
                machines,
                set_type=self.set_type,
                copy_perfect=self.copy_perfect,
                repair=self.repair,
            )
            residual_path = self.service.write_residual_manifest(
                self.residual,
                result.unresolved,
                source_manifest=self.manifest,
                set_type=self.set_type,
            )
            self.log.emit(f"Manifesto residual gravado: {residual_path}")
            self.finished_result.emit(result)
        except InterruptedError as exc:
            self.log.emit(str(exc))
            self.finished_result.emit(None)
        except Exception as exc:
            logger.exception("Falha na reconstrução")
            self.failed.emit(str(exc))

    def cancel(self) -> None:
        """Solicita cancelamento cooperativo sem destruir a thread à força."""
        if self.service is not None:
            self.service.request_cancel()
        self.requestInterruption()


class ReconstructionTab(QWidget):
    """Interface de cópia/reparo do set atual."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.parent_widget = parent
        self.config = AppConfig()
        self.manifest_path = AppConfig.SCAN_DIR / "current_scan.jsonl"
        self.worker: ReconstructionWorker | None = None
        self.machines = []
        self._build_ui()
        self._load_manifest()

    def _scan_dir(self) -> Path:
        """Retorna o diretório canônico dos manifests de scan."""
        AppConfig.SCAN_DIR.mkdir(parents=True, exist_ok=True)
        return AppConfig.SCAN_DIR

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
        self.set_combo.addItem("Split", ReconstructionEngine.SET_SPLIT)
        self.set_combo.addItem("Merged", ReconstructionEngine.SET_MERGED)
        self.set_combo.addItem("Non-Merged", ReconstructionEngine.SET_NON_MERGED)
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
        """Carrega o current_scan.jsonl físico v2 da pasta canônica de scan."""
        try:
            self.manifest_path = self._scan_dir() / "current_scan.jsonl"
            if not self.manifest_path.is_file():
                self.manifest_label.setText(f"Manifesto: {self.manifest_path} — não encontrado")
                self.tree.clear()
                self.machines = []
                return
            header = ReconstructionEngine.load_manifest_header(self.manifest_path)
            self.machines = ReconstructionEngine.load_manifest(self.manifest_path)
            source_paths = header.get("source_paths", [])
            rom_count = sum(len(machine.roms) for machine in self.machines)
            self.tree.set_data(self.machines)
            self.manifest_label.setText(
                f"Manifesto físico v{header.get('schema_version', '?')}: {self.manifest_path} | "
                f"Machines: {len(self.machines)} | ROMs: {rom_count} | Origem: {', '.join(source_paths) or 'não informada'}"
            )
        except Exception as exc:
            logger.exception("Falha ao carregar current_scan.jsonl")
            self.manifest_label.setText(f"Erro ao carregar manifesto: {exc}")
            self.tree.clear()
            self.machines = []

    def refresh(self) -> None:
        """Recarrega o manifesto corrente após um novo scan."""
        if self.worker is None or not self.worker.isRunning():
            self._load_manifest()

    def _source_paths(self) -> list[Path]:
        """Retorna as fontes gravadas no header do scan, não as do destino."""
        try:
            header = ReconstructionEngine.load_manifest_header(self.manifest_path)
            paths = [Path(p) for p in header.get("source_paths", []) if p]
            if paths:
                return paths
        except Exception:
            logger.exception("Não foi possível obter source_paths do manifesto")
        return [Path(p) for p in (getattr(self.config, "source_dirs", []) or [])]

    def _destination(self) -> Path:
        """Retorna somente o diretório configurado para o set reconstruído."""
        value = getattr(self.config, "destination_dir", None)
        if not value:
            raise RuntimeError("Diretório de destino não configurado na aba Scan Roms.")
        return Path(value)

    def _start(self, *, copy_perfect: bool, repair: bool) -> None:
        """Inicia uma reconstrução baseada no manifesto atual, sem novo scan."""
        if self.worker and self.worker.isRunning():
            return
        self._load_manifest()
        if not self.manifest_path.is_file() or not self.machines:
            QMessageBox.warning(self, "Reconstrução", "current_scan.jsonl não foi encontrado ou não contém machines.")
            return
        try:
            destination = self._destination()
            source_paths = self._source_paths()
            if not source_paths:
                raise RuntimeError("O header do current_scan.jsonl não informa source_paths válidos.")
        except Exception as exc:
            QMessageBox.warning(self, "Reconstrução", str(exc))
            return
        residual = self._scan_dir() / "current_reconstruction.jsonl"
        self.progress.setValue(0)
        self.count_label.setText("Copiadas: 0 | Reparadas: 0 | Externas: 0 | Pendentes: 0")
        self.progress_label.setText("Iniciando...")
        self._set_running(True)
        self.log_panel._clear()
        self.worker = ReconstructionWorker(
            self.manifest_path,
            source_paths,
            destination,
            self.set_combo.currentData(),
            copy_perfect,
            repair,
            residual,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._append_log)
        self.worker.finished_result.connect(self._finished)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(lambda: self._set_running(False))
        self.worker.start()

    def _context_action(self, data: dict) -> None:
        """Executa reparo individual ou exibe detalhes da ROM selecionada."""
        if data.get("action") == "details":
            rom = data.get("rom")
            if rom:
                QMessageBox.information(self, "ROM", f"{rom.rom_name}\nCRC: {rom.expected_crc}\nTamanho: {rom.expected_size}\nEstado: {rom.status}\nOrigem: {rom.source_archive}!{rom.source_member}")
            return
        machine = data.get("machine")
        rom = data.get("rom")
        if not machine or not rom:
            return
        try:
            destination = self._destination()
            source_paths = self._source_paths()
            self.progress.setValue(0)
            self.progress_label.setText(f"Reparando {machine.name} -> {rom.rom_name}...")
            self.log_panel._clear()
            repairer = SingleRomRepairEngine(source_paths, destination, log_callback=self._append_log)
            repairer.repair(machine, rom)
            self.progress.setValue(100)
            self.progress_label.setText(f"ROM reparada e verificada: {rom.rom_name}")
            self._append_log(f"Reparo individual concluído: {machine.name} -> {rom.rom_name}")
        except Exception as exc:
            logger.exception("Falha no reparo individual")
            self.progress_label.setText("Falha no reparo individual.")
            QMessageBox.warning(self, "Reparo da ROM", str(exc))

    def _on_progress(self, current: int, total: int, message: str) -> None:
        percent = int((current / total) * 100) if total else 100
        self.progress.setValue(max(0, min(100, percent)))
        self.progress_label.setText(message)

    def _append_log(self, message: str) -> None:
        """Envia mensagens do worker para o logger observado pelo LogPanel."""
        logging.getLogger("app.mame.reconstruction_service").info(message)

    def _finished(self, result) -> None:
        if result is None:
            self.progress_label.setText("Reconstrução cancelada.")
            return
        self.count_label.setText(
            f"Copiadas: {result.copied} | Reparadas: {result.repaired} | "
            f"Externas: {result.external} | Pendentes: {len(result.unresolved)}"
        )
        self.progress.setValue(100)
        self.progress_label.setText("Reconstrução concluída; manifesto residual gerado.")
        self._load_manifest()

    def _failed(self, message: str) -> None:
        self.progress_label.setText("Reconstrução interrompida por erro.")
        QMessageBox.critical(self, "Reconstrução", message)

    def _cancel(self) -> None:
        """Solicita cancelamento seguro e aguarda a operação corrente."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.progress_label.setText("Cancelamento solicitado; aguardando o bloco atual terminar...")

    def _set_running(self, running: bool) -> None:
        """Bloqueia comandos concorrentes enquanto o worker estiver ativo."""
        for button in (self.copy_button, self.repair_button, self.all_button):
            button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
