"""Aba Scan Roms.

Orquestra o LISTXML e utiliza o RomScanEngine para validar as ROMs e registrar
as origens físicas necessárias à reconstrução.
"""
from __future__ import annotations

import csv
import logging
import os
import re
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtWidgets import QFileDialog, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QSpinBox, QSplitter, QVBoxLayout, QWidget

from app.config.app_config import AppConfig
from app.core.models.filter_profile import FilterCriteria
from app.core.services.filter_service import FilterService
from app.core.services.listxml_export_service import ListxmlExportService
from app.database.database import Database
from app.gui.widgets import ScanControlWidget, ScanSummaryWidget, RomTreeWidget
from app.gui.widgets.log_panel import LogPanel
from app.gui.widgets.rom_tree_widget import value_of, as_int
from app.mame.rom_scan_engine import RomScanEngine
from app.mame.scan_manifest import ScanManifestReader

logger = logging.getLogger(__name__)
DEFAULT_LOG_HEIGHT = 220
MIN_LOG_HEIGHT = 80
MAX_LOG_HEIGHT = 900
DEFAULT_MAME_VERSION = "0.289"


class LoadManifestWorker(QThread):
    """Carrega current_scan.jsonl sem bloquear a interface."""
    progress = Signal(int, int, str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, manifest_path: Path):
        super().__init__()
        self.manifest_path = manifest_path

    def run(self) -> None:
        try:
            from app.core.models.scan_result import MachineScanResult, RomScanResult, ScanStatus
            descriptions: dict[str, str] = {}
            for record in ScanManifestReader(self.manifest_path).iter_records():
                if record.get("record_type") == "machine":
                    data = record.get("machine") or {}
                    if data.get("name"):
                        descriptions[data["name"]] = data.get("description", "")
            total = sum(1 for _ in ScanManifestReader(self.manifest_path).iter_roms())
            machines: dict[str, MachineScanResult] = {}
            for index, record in enumerate(ScanManifestReader(self.manifest_path).iter_roms(), 1):
                name = record.get("machine", "")
                if not name:
                    continue
                machine = machines.setdefault(name, MachineScanResult(machine_name=name, description=descriptions.get(name, "")))
                status = {"valid": ScanStatus.VALID, "missing": ScanStatus.MISSING, "corrupted": ScanStatus.INVALID, "invalid": ScanStatus.INVALID, "error": ScanStatus.ERROR, "cancelled": ScanStatus.CANCELLED, "ok": ScanStatus.VALID}.get(record.get("status", "missing"), ScanStatus.MISSING)
                source = record.get("source") or {}
                machine.roms.append(RomScanResult(machine_name=name, rom_name=record.get("rom_name", ""), expected_size=record.get("expected_size", 0), actual_size=record.get("actual_size") or 0, expected_crc=record.get("expected_crc", ""), actual_crc=record.get("actual_crc") or "", expected_sha1=record.get("expected_sha1") or "", actual_sha1=record.get("actual_sha1") or "", status=status, path=source.get("archive"), archive_path=source.get("archive"), archive_member=source.get("member"), merge=record.get("merge"), optional=record.get("optional", False), message=record.get("error") or "", error=record.get("error")))
                if index % 100 == 0:
                    self.progress.emit(index, total, f"Carregando {index}/{total} ROMs...")
            self.finished.emit(list(machines.values()))
        except Exception as exc:
            self.error.emit(str(exc))


class ScanRomsTab(QWidget):
    """Orquestra geração do XML, scan e persistência do manifesto."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.parent_widget = parent
        self.config = AppConfig()
        self.filtered_xml_path: Path | None = None
        self.scanning = False
        self.scanner: RomScanEngine | None = None
        self.scan_thread: threading.Thread | None = None
        self.scan_results: list[Any] = []
        self.scan_start_time: float | None = None
        self.progress_current = self.progress_total = self.total_machines = 0
        self.scan_stats = {"valid": 0, "missing": 0, "invalid": 0, "error": 0}
        self._filter_service: FilterService | None = None
        self._ensure_filter_service()
        self._build_ui()
        self._wire_signals()
        self._load_paths_from_config()
        self._load_profiles()
        self._update_ui_state()
        QTimer.singleShot(200, self._delayed_load_scan)

    def _ensure_filter_service(self) -> None:
        try:
            conn = self._get_db_connection()
            self._filter_service = FilterService(conn) if conn is not None else None
        except Exception:
            self._filter_service = None

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        content = QWidget()
        layout = QVBoxLayout(content)
        self.control_widget = ScanControlWidget()
        layout.addWidget(self.control_widget)
        self.summary_widget = ScanSummaryWidget()
        layout.addWidget(self.summary_widget)
        self.tree = RomTreeWidget()
        layout.addWidget(self.tree)
        self.main_splitter.addWidget(content)
        self.main_splitter.addWidget(self._build_log_group())
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([650, DEFAULT_LOG_HEIGHT])
        outer.addWidget(self.main_splitter)

    def _build_log_group(self) -> QGroupBox:
        group = QGroupBox("Log")
        layout = QVBoxLayout(group)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Altura:"))
        self.log_height_spin = QSpinBox()
        self.log_height_spin.setRange(MIN_LOG_HEIGHT, MAX_LOG_HEIGHT)
        self.log_height_spin.setValue(DEFAULT_LOG_HEIGHT)
        self.log_height_spin.valueChanged.connect(self._on_log_height_changed)
        toolbar.addWidget(self.log_height_spin)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        self.log_panel = LogPanel(self, logger_name="")
        layout.addWidget(self.log_panel)
        return group

    def _on_log_height_changed(self, value: int) -> None:
        total = self.main_splitter.height() or 650 + value
        self.main_splitter.setSizes([max(150, total - value), value])

    def _wire_signals(self) -> None:
        self.control_widget.generate_xml_requested.connect(self._generate_filtered_xml)
        self.control_widget.select_xml_requested.connect(self._select_existing_xml)
        self.control_widget.open_folder_requested.connect(self._open_scans_dir)
        self.control_widget.start_scan_requested.connect(self._start_scan)
        self.control_widget.stop_scan_requested.connect(self._stop_scan)
        self.control_widget.profile_changed.connect(self._on_profile_combo_changed)
        self.control_widget.export_report_requested.connect(self._export_report)
        self.tree.population_finished.connect(self._finish_tree_population)
        self.tree.repair_requested.connect(self._on_repair_requested)

    def _load_profiles(self) -> None:
        if self._filter_service is None:
            self.control_widget.load_profiles([])
            return
        profiles = self._filter_service.get_profiles()
        default = self._filter_service.get_default_profile()
        self.control_widget.load_profiles(profiles, default.id if default else None)
        self._update_profile_label()

    def _on_profile_combo_changed(self, index: int) -> None:
        self._update_profile_label()

    def _update_profile_label(self) -> None:
        self.summary_widget.set_profile_label(self.control_widget.current_profile_label())

    def refresh_profiles(self) -> None:
        self._ensure_filter_service()
        self._load_profiles()

    def _get_selected_criteria(self) -> FilterCriteria:
        self._ensure_filter_service()
        selected_id = self.control_widget.current_profile_id()
        if selected_id is not None and self._filter_service is not None:
            profile = self._filter_service.profile_repo.get_by_id(selected_id)
            if profile:
                return profile.criteria
        provider = getattr(self.parent_widget, "get_current_filter_criteria", None)
        if callable(provider):
            return provider() or FilterCriteria()
        return FilterCriteria()

    def _load_paths_from_config(self) -> None:
        self.control_widget.load_paths_from_config(getattr(self.config, "source_dirs", []) or [], getattr(self.config, "destination_dir", None))

    def _save_paths(self) -> None:
        paths, destination = self.control_widget.collect_paths_for_save()
        try:
            self.config.source_dirs = paths
            self.config.destination_dir = destination or None
            if callable(getattr(self.config, "save", None)):
                self.config.save()
        except Exception:
            logger.warning("Não foi possível persistir configurações.", exc_info=True)

    def _get_db_connection(self):
        main_db = getattr(self.parent_widget, "db", None)
        if main_db is not None and getattr(main_db, "conn", None) is not None:
            return main_db.conn
        db_path = getattr(self.config, "db_path", None)
        if db_path is None:
            raise RuntimeError("Caminho do banco não configurado.")
        db = Database(db_path)
        db.connect()
        return db.conn

    def _get_rom_paths(self) -> list[Path]:
        paths = []
        for edit in self.source_edits:
            value = edit.text().strip()
            if value and Path(value).expanduser().is_dir():
                paths.append(Path(value).expanduser())
        return paths

    def _scans_dir(self) -> Path:
        configured = getattr(self.config, "scans_dir", None)
        destination = getattr(self.config, "destination_dir", None)
        path = Path(configured) if configured else (Path(destination) / "scans" if destination else Path.cwd() / "data" / "scans")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _select_existing_xml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar LISTXML filtrado", str(self._scans_dir()), "XML (*.xml);;Todos os arquivos (*)")
        if path:
            self._set_active_xml(Path(path), "selecionado manualmente")

    def _set_active_xml(self, path: Path, origin: str) -> None:
        if not path.is_file():
            QMessageBox.warning(self, "XML inválido", f"O arquivo não existe:\n{path}")
            return
        self.filtered_xml_path = path
        self.xml_label.setText(str(path))
        self.xml_label.setToolTip(str(path))
        self.status_label.setText(f"XML ativo ({origin}): {path.name}")
        self._update_ui_state()

    def _open_scans_dir(self) -> None:
        path = self._scans_dir()
        try:
            if os.name == "nt":
                os.startfile(str(path))
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            QMessageBox.warning(self, "Erro", str(exc))

    def _generate_filtered_xml(self) -> None:
        if self.scanning:
            return
        self.btn_generate.setEnabled(False)
        try:
            service = ListxmlExportService(getattr(self.config, "db_path", None), getattr(self.config, "mame_path", None))
            machine_ids = service.get_machine_ids_from_db(self._get_selected_criteria())
            if not machine_ids:
                QMessageBox.warning(self, "Nenhuma máquina", "Nenhuma máquina foi encontrada com os filtros atuais.")
                return
            version = self._get_mame_version()
            output = self._scans_dir() / f"mame_{version}_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
            service.generate_filtered_xml(machine_ids, output)
            self._set_active_xml(output, "recém-gerado")
        except Exception as exc:
            logger.exception("Erro gerando LISTXML filtrado.")
            QMessageBox.critical(self, "Erro", str(exc))
        finally:
            self.btn_generate.setEnabled(True)

    def _get_mame_version(self) -> str:
        mame_path = Path(getattr(self.config, "mame_path", "")) if getattr(self.config, "mame_path", None) else None
        if not mame_path or not mame_path.is_file():
            return DEFAULT_MAME_VERSION
        try:
            result = subprocess.run([str(mame_path), "-help"], capture_output=True, text=True, timeout=5, check=False)
            match = re.search(r"\bv?(\d+\.\d+)\b", result.stdout or result.stderr or "")
            return match.group(1) if match else DEFAULT_MAME_VERSION
        except Exception:
            return DEFAULT_MAME_VERSION

    def _start_scan(self) -> None:
        if self.scanning:
            return
        if self.filtered_xml_path is None or not self.filtered_xml_path.is_file():
            QMessageBox.warning(self, "XML necessário", "Selecione ou gere primeiro um LISTXML filtrado.")
            return
        if not self._get_rom_paths() and QMessageBox.question(self, "Nenhuma origem", "Nenhuma origem válida foi configurada. Continuar?") != QMessageBox.StandardButton.Yes:
            return
        self._save_paths()
        self.scanning = True
        self.scan_results = []
        self.scan_stats = {"valid": 0, "missing": 0, "invalid": 0, "error": 0}
        self.progress_current = self.progress_total = 0
        self.tree.clear()
        self._reset_summary()
        self._update_ui_state()
        self.scan_thread = threading.Thread(target=self._do_scan, name="mame-rom-scan", daemon=True)
        self.scan_thread.start()

    def _stop_scan(self) -> None:
        if self.scanner:
            self.scanner.cancel()
            self.status_label.setText("Solicitando cancelamento...")

    def _do_scan(self) -> None:
        try:
            machines = self._load_machines_from_xml(self.filtered_xml_path)
            total = sum(len(m.get("roms", [])) for m in machines)
            self.progress_total = total
            self.total_machines = len(machines)
            self._queue_summary(machines=len(machines), total=total)
            self.scanner = RomScanEngine(rom_paths=self._get_rom_paths(), max_workers=self.worker_count(), progress_callback=self._on_rom_progress, machine_callback=self._on_machine_complete, log_callback=self._on_scanner_log, enable_alternate_search=self.alternate_search_enabled(), include_chds=False, manifest_directory=self._scans_dir())
            self.scan_results = self.scanner.scan(machines, mame_version=self._get_mame_version(), xml_path=self.filtered_xml_path)
            if self.scanner.cancelled:
                self._queue_ui(lambda: self._finish_scan(cancelled=True))
            else:
                self._queue_ui(self._populate_tree)
        except Exception as exc:
            logger.exception("Erro geral durante o scan.")
            self._queue_ui(lambda: self._show_scan_error(str(exc)))

    def _load_machines_from_xml(self, xml_path: Path) -> list[dict[str, Any]]:
        root = ET.parse(xml_path).getroot()
        machines = []
        for element in root.findall("machine"):
            name = element.get("name", "")
            if not name:
                continue
            roms = [{"name": r.get("name", ""), "size": _as_int(r.get("size", 0)), "crc": (r.get("crc", "") or "").lower(), "sha1": (r.get("sha1", "") or "").lower(), "merge": r.get("merge"), "optional": r.get("optional")} for r in element.findall("rom")]
            machines.append({"name": name, "description": (element.findtext("description") or "").strip(), "cloneof": element.get("cloneof"), "roms": roms, "disks": []})
        return machines

    def _on_rom_progress(self, current: int, total: int, result: Any) -> None:
        self.progress_current, self.progress_total = current, total
        status = str(value_of(result, "status", "")).lower()
        if status in self.scan_stats:
            self.scan_stats[status] += 1
        self._queue_ui(lambda: self._update_progress_ui(current, total, str(value_of(result, "machine_name", "")), str(value_of(result, "rom_name", "")), status))
        self._queue_ui(self._update_summary_from_stats)

    def _on_machine_complete(self, result: Any) -> None:
        self._queue_status(f"Máquina concluída: {value_of(result, 'machine_name', '')} — {value_of(result, 'valid', 0)}/{value_of(result, 'total', 0)} válidas")

    def _on_scanner_log(self, message: str) -> None:
        logger.info(message)

    def _queue_ui(self, callback) -> None:
        QTimer.singleShot(0, callback)

    def _queue_status(self, text: str) -> None:
        self._queue_ui(lambda: self.status_label.setText(text))

    def _queue_summary(self, *, machines: int, total: int) -> None:
        self._queue_ui(lambda: (self.summary_labels["machines"].setText(str(machines)), self.summary_labels["total"].setText(str(total))))

    def _finish_scan(self, *, cancelled: bool) -> None:
        self.scanning = False
        self.scanner = None
        self._update_summary_from_results()
        self._update_summary_from_stats()
        self._update_ui_state()

    def _show_scan_error(self, error: str) -> None:
        self.scanning = False
        self.scanner = None
        self._update_ui_state()
        QMessageBox.critical(self, "Erro no escaneamento", error)

    def _reset_summary(self) -> None:
        self.scan_stats = {"valid": 0, "missing": 0, "invalid": 0, "error": 0}
        for label in self.summary_labels.values():
            label.setText("0")

    def _update_summary_from_stats(self) -> None:
        self.summary_labels["valid"].setText(str(self.scan_stats["valid"]))
        self.summary_labels["missing"].setText(str(self.scan_stats["missing"]))
        self.summary_labels["bad"].setText(str(self.scan_stats["invalid"]))
        self.summary_labels["error"].setText(str(self.scan_stats["error"]))
        self.summary_labels["total"].setText(str(self.progress_total))
        self.summary_labels["found"].setText(str(self.scan_stats["valid"] + self.scan_stats["invalid"] + self.scan_stats["error"]))

    def _update_progress_ui(self, current: int, total: int, machine_name: str, rom_name: str, status: str) -> None:
        percent = int(current * 100 / total) if total else 0
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{current}/{total} ROMs — {percent}%")
        self.status_label.setText(f"Escaneando {current}/{total}: {machine_name} — {rom_name} [{status}]")

    def _update_summary_from_results(self) -> None:
        self.summary_labels["machines"].setText(str(len(self.scan_results)))
        self.summary_labels["total"].setText(str(sum(m.total for m in self.scan_results)))
        self.summary_labels["found"].setText(str(sum(m.found for m in self.scan_results)))
        self.summary_labels["valid"].setText(str(sum(m.valid for m in self.scan_results)))
        self.summary_labels["missing"].setText(str(sum(m.missing for m in self.scan_results)))
        self.summary_labels["bad"].setText(str(sum(m.bad for m in self.scan_results)))
        self.summary_labels["error"].setText(str(sum(m.error_count for m in self.scan_results)))

    def _populate_tree(self) -> None:
        self.tree.clear()
        self._populating_tree = True
        self._tree_index = 0
        self._tree_batch_size = 50
        self._tree_timer = QTimer(self)
        self._tree_timer.timeout.connect(self._populate_tree_batch)
        self._tree_timer.start(0)

    def _populate_tree_batch(self) -> None:
        if self._tree_index >= len(self.scan_results):
            self._tree_timer.stop()
            self._populating_tree = False
            self._finish_tree_population(0.0)
            return
        end = min(self._tree_index + self._tree_batch_size, len(self.scan_results))
        for machine in self.scan_results[self._tree_index:end]:
            self.tree.add_machine(machine)
        self._tree_index = end

    def _finish_tree_population(self, elapsed: float) -> None:
        self.scanning = False
        self._update_summary_from_results()
        self._update_ui_state()

    def _delayed_load_scan(self) -> None:
        path = self._scans_dir() / "current_scan.jsonl"
        if path.is_file():
            worker = LoadManifestWorker(path)
            worker.finished.connect(self._apply_loaded_scan)
            worker.start()
            self._manifest_worker = worker

    def _apply_loaded_scan(self, results) -> None:
        self.scan_results = results
        self._update_summary_from_results()
        self._populate_tree()

    def _on_tree_double_click(self, item, column) -> None:
        return

    def _on_repair_requested(self, data) -> None:
        return

    def _export_report(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Exportar relatório", str(self._scans_dir() / "rom_report.csv"), "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.writer(handle)
                writer.writerow(["machine", "rom", "status", "expected_size", "actual_size", "expected_crc", "actual_crc", "source"])
                for machine in self.scan_results:
                    for rom in machine.roms:
                        writer.writerow([machine.machine_name, rom.rom_name, rom.status.value, rom.expected_size, rom.actual_size, rom.expected_crc, rom.actual_crc, str(rom.location or "")])
        except Exception as exc:
            QMessageBox.critical(self, "Erro", str(exc))
