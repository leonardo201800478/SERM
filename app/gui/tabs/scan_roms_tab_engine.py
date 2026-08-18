"""Aba Scan Roms integrada ao manifesto persistente do MAME Set Builder."""
from __future__ import annotations

import csv
import json
import logging
import os
import re
import subprocess
import threading
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFileDialog, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QSpinBox, QSplitter, QVBoxLayout, QWidget

from app.config.app_config import AppConfig
from app.core.models.filter_profile import FilterCriteria
from app.core.services.filter_service import FilterService
from app.core.services.listxml_export_service import ListxmlExportService
from app.database.database import Database
from app.gui.widgets import ScanControlWidget, ScanSummaryWidget, RomTreeWidget
from app.gui.widgets.log_panel import LogPanel
from app.gui.widgets.rom_tree_widget import value_of
from app.mame.rom_scan_engine import RomScanEngine

logger = logging.getLogger(__name__)


class ScanRomsTabEngine(QWidget):
    """UI do Scan Roms usando o current_scan.jsonl como snapshot oficial."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.parent_widget = parent
        self.config = AppConfig()
        self.filtered_xml_path: Path | None = None
        self.scanning = False
        self.scanner: RomScanEngine | None = None
        self.scan_thread: threading.Thread | None = None
        self.scan_results: list[Any] = []
        self._filter_service: FilterService | None = None
        self._tree_timer: QTimer | None = None
        self._build_ui()
        self._ensure_filter_service()
        self._load_paths_from_config()
        self._load_profiles()
        self._update_ui_state()
        QTimer.singleShot(100, self._load_current_manifest)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        content = QWidget()
        layout = QVBoxLayout(content)
        self.control = ScanControlWidget()
        self.summary = ScanSummaryWidget()
        self.tree = RomTreeWidget()
        layout.addWidget(self.control)
        layout.addWidget(self.summary)
        layout.addWidget(self.tree, 1)
        self.splitter.addWidget(content)
        self.splitter.addWidget(self._build_log_group())
        self.splitter.setSizes([650, 220])
        root.addWidget(self.splitter)
        self.control.generate_xml_requested.connect(self._generate_xml)
        self.control.select_xml_requested.connect(self._select_xml)
        self.control.open_folder_requested.connect(self._open_scans)
        self.control.start_scan_requested.connect(self._start_scan)
        self.control.stop_scan_requested.connect(self._stop_scan)
        self.control.profile_changed.connect(lambda _: self._update_profile_label())
        self.control.export_report_requested.connect(self._export_report)
        self.tree.population_finished.connect(lambda _: self._update_ui_state())

    def _build_log_group(self) -> QGroupBox:
        group = QGroupBox("Log")
        layout = QVBoxLayout(group)
        row = QHBoxLayout()
        row.addWidget(QLabel("Altura:"))
        self.log_height = QSpinBox()
        self.log_height.setRange(80, 900)
        self.log_height.setValue(220)
        self.log_height.valueChanged.connect(lambda value: self.splitter.setSizes([max(150, self.splitter.height() - value), value]))
        row.addWidget(self.log_height)
        row.addStretch()
        layout.addLayout(row)
        self.log_panel = LogPanel(self, logger_name="")
        layout.addWidget(self.log_panel)
        return group

    def _ensure_filter_service(self) -> None:
        try:
            conn = getattr(getattr(self.parent_widget, "db", None), "conn", None)
            if conn is None:
                db_path = getattr(self.config, "db_path", None)
                if db_path:
                    db = Database(db_path)
                    db.connect()
                    conn = db.conn
            self._filter_service = FilterService(conn) if conn is not None else None
        except Exception:
            logger.exception("Falha inicializando FilterService")
            self._filter_service = None

    def _load_profiles(self) -> None:
        if self._filter_service is None:
            self.control.load_profiles([])
            return
        profiles = self._filter_service.get_profiles()
        default = self._filter_service.get_default_profile()
        self.control.load_profiles(profiles, default.id if default else None)
        self._update_profile_label()

    def refresh_profiles(self) -> None:
        self._ensure_filter_service()
        self._load_profiles()

    def set_active_profile_name(self, name: str) -> None:
        self.summary.set_profile_label(name)

    def _update_profile_label(self) -> None:
        self.summary.set_profile_label(self.control.current_profile_label())

    def _get_criteria(self) -> FilterCriteria:
        selected = self.control.current_profile_id()
        if selected is not None and self._filter_service is not None:
            profile = self._filter_service.profile_repo.get_by_id(selected)
            if profile:
                return profile.criteria
        provider = getattr(self.parent_widget, "get_current_filter_criteria", None)
        return provider() if callable(provider) else FilterCriteria()

    def _load_paths_from_config(self) -> None:
        self.control.load_paths_from_config(getattr(self.config, "source_dirs", []) or [], getattr(self.config, "destination_dir", None))

    def _save_paths(self) -> None:
        paths, destination = self.control.collect_paths_for_save()
        self.config.source_dirs = paths
        self.config.destination_dir = destination or None
        if callable(getattr(self.config, "save", None)):
            self.config.save()

    def _scans_dir(self) -> Path:
        configured = getattr(self.config, "scans_dir", None)
        path = Path(configured) if configured else Path(__file__).resolve().parents[3] / "data" / "database" / "scan"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _select_xml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar LISTXML", str(self._scans_dir()), "XML (*.xml)")
        if path:
            self._set_xml(Path(path))

    def _set_xml(self, path: Path) -> None:
        if not path.is_file():
            QMessageBox.warning(self, "XML", "Arquivo não encontrado.")
            return
        self.filtered_xml_path = path
        self.control.display_xml(path)
        self.summary.set_status(f"XML ativo: {path.name}")
        self._update_ui_state()

    def _open_scans(self) -> None:
        path = self._scans_dir()
        try:
            if os.name == "nt":
                os.startfile(str(path))
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            QMessageBox.warning(self, "Erro", str(exc))

    def _generate_xml(self) -> None:
        try:
            service = ListxmlExportService(getattr(self.config, "db_path", None), getattr(self.config, "mame_path", None))
            ids = service.get_machine_ids_from_db(self._get_criteria())
            if not ids:
                QMessageBox.warning(self, "XML", "Nenhuma machine encontrada.")
                return
            version = self._mame_version()
            path = self._scans_dir() / f"mame_{version}_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
            service.generate_filtered_xml(ids, path)
            self._set_xml(path)
        except Exception as exc:
            logger.exception("Falha gerando LISTXML")
            QMessageBox.critical(self, "XML", str(exc))

    def _mame_version(self) -> str:
        path = Path(getattr(self.config, "mame_path", "")) if getattr(self.config, "mame_path", None) else None
        if not path or not path.is_file():
            return "0.289"
        try:
            result = subprocess.run([str(path), "-help"], capture_output=True, text=True, timeout=5, check=False)
            match = re.search(r"\bv?(\d+\.\d+)\b", result.stdout or result.stderr or "")
            return match.group(1) if match else "0.289"
        except Exception:
            return "0.289"

    def _xml_machines(self) -> list[dict[str, Any]]:
        if self.filtered_xml_path is None:
            raise RuntimeError("LISTXML não selecionado.")
        root = ET.parse(self.filtered_xml_path).getroot()
        machines = []
        for element in root.findall("machine"):
            name = element.get("name", "")
            if not name:
                continue
            roms = []
            for rom in element.findall("rom"):
                roms.append({"name": rom.get("name", ""), "size": int(rom.get("size", 0) or 0), "crc": (rom.get("crc", "") or "").lower(), "sha1": (rom.get("sha1", "") or "").lower(), "merge": rom.get("merge"), "optional": rom.get("optional")})
            machines.append({"name": name, "description": element.findtext("description") or "", "cloneof": element.get("cloneof"), "roms": roms})
        return machines

    def _start_scan(self) -> None:
        if self.scanning:
            return
        if self.filtered_xml_path is None:
            QMessageBox.warning(self, "Scan", "Selecione ou gere um LISTXML primeiro.")
            return
        self._save_paths()
        self.scanning = True
        self.summary.reset()
        self.tree.clear()
        self.summary.set_status("Iniciando novo escaneamento...")
        self._update_ui_state()
        self.scan_thread = threading.Thread(target=self._scan_worker, daemon=True, name="mame-rom-scan")
        self.scan_thread.start()

    def _scan_worker(self) -> None:
        try:
            machines = self._xml_machines()
            self.scanner = RomScanEngine(self.control.get_rom_paths(), max_workers=self.control.worker_count(), progress_callback=self._progress, log_callback=self._log, enable_alternate_search=self.control.alternate_search_enabled(), include_chds=self.control.include_chds(), manifest_directory=self._scans_dir())
            self.scan_results = self.scanner.scan(machines, mame_version=self._mame_version(), xml_path=self.filtered_xml_path)
            QTimer.singleShot(0, self._scan_finished)
        except Exception as exc:
            logger.exception("Falha no scan")
            QTimer.singleShot(0, lambda: self._scan_error(str(exc)))

    def _progress(self, current: int, total: int, result: Any) -> None:
        self._queue_ui(lambda: self._set_progress(current, total, result))

    def _set_progress(self, current: int, total: int, result: Any) -> None:
        status = str(value_of(result, "status", "")).lower()
        counts = {"valid": sum(m.valid for m in self.scan_results), "missing": sum(m.missing for m in self.scan_results), "bad": sum(m.bad for m in self.scan_results), "error": sum(m.error_count for m in self.scan_results), "total": total}
        self.summary.update_counts(counts)
        self.summary.set_progress(int(current * 100 / total) if total else 0, f"{current}/{total} ROMs")
        self.summary.set_status(f"{value_of(result, 'machine_name', '')} — {value_of(result, 'rom_name', '')} [{status}]")

    def _log(self, message: str) -> None:
        logging.getLogger("app.mame.rom_scan_engine").info(message)

    def _scan_finished(self) -> None:
        """Encerra o estado do scanner e recarrega o snapshot persistido."""
        self.scanning = False
        self.scanner = None
        self.scan_thread = None
        self._load_current_manifest(show_errors=True)
        self.summary.set_progress(100, "Scan concluído")
        self.summary.set_status("Escaneamento concluído — current_scan.jsonl carregado")
        self._update_ui_state()

    def _scan_error(self, message: str) -> None:
        self.scanning = False
        self.scanner = None
        self.scan_thread = None
        self._update_ui_state()
        QMessageBox.critical(self, "Scan", message)

    def _stop_scan(self) -> None:
        if self.scanner:
            self.scanner.cancel()

    def _update_counts(self) -> None:
        self.summary.update_counts({"machines": len(self.scan_results), "total": sum(m.total for m in self.scan_results), "found": sum(m.found for m in self.scan_results), "valid": sum(m.valid for m in self.scan_results), "missing": sum(m.missing for m in self.scan_results), "bad": sum(m.bad for m in self.scan_results), "error": sum(m.error_count for m in self.scan_results)})

    @staticmethod
    def _manifest_status_to_scan_status(status: str):
        """Converte status persistido no JSONL para ScanStatus."""
        from app.core.models.scan_result import ScanStatus
        return {"valid": ScanStatus.VALID, "missing": ScanStatus.MISSING, "invalid": ScanStatus.INVALID, "corrupted": ScanStatus.INVALID, "error": ScanStatus.ERROR, "cancelled": ScanStatus.CANCELLED}.get(status.lower(), ScanStatus.UNKNOWN)

    def _load_current_manifest(self, show_errors: bool = False) -> bool:
        """Carrega current_scan.jsonl diretamente, sem depender da Reconstrução."""
        manifest = self._scans_dir() / "current_scan.jsonl"
        if not manifest.is_file():
            return False
        try:
            from app.core.models.scan_result import MachineScanResult, RomScanResult
            machines: dict[str, MachineScanResult] = {}
            header: dict[str, Any] | None = None
            with manifest.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, 1):
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"JSONL inválido na linha {line_number}: {exc}") from exc
                    record_type = record.get("record_type")
                    if record_type == "header":
                        header = record
                        continue
                    if record_type == "machine":
                        data = record.get("machine") or {}
                        name = str(data.get("name") or "")
                        if not name:
                            continue
                        result = machines.get(name)
                        if result is None:
                            result = MachineScanResult(machine_name=name, description=str(data.get("description") or ""), cloneof=data.get("cloneof"))
                            machines[name] = result
                        else:
                            if data.get("description"):
                                result.description = str(data["description"])
                            if data.get("cloneof"):
                                result.cloneof = data["cloneof"]
                        continue
                    if record_type != "rom":
                        continue
                    data = record.get("rom") or record
                    machine_name = str(data.get("machine") or "")
                    rom_name = str(data.get("rom_name") or "")
                    if not machine_name or not rom_name:
                        continue
                    machine = machines.setdefault(machine_name, MachineScanResult(machine_name=machine_name))
                    source = data.get("source") or {}
                    source_kind = str(source.get("kind") or "").lower()
                    archive = source.get("archive")
                    member = source.get("member")
                    machine.roms.append(RomScanResult(machine_name=machine_name, rom_name=rom_name, expected_size=int(data.get("expected_size") or 0), actual_size=int(data.get("actual_size") or 0), expected_crc=str(data.get("expected_crc") or "").lower(), actual_crc=str(data.get("actual_crc") or "").lower(), expected_sha1=str(data.get("expected_sha1") or "").lower(), actual_sha1=str(data.get("actual_sha1") or "").lower(), status=self._manifest_status_to_scan_status(str(data.get("status") or "unknown")), archive_path=Path(archive) if archive and source_kind == "zip" else None, archive_member=str(member) if member else None, path=Path(archive) if archive and source_kind in {"file", "loose", "raw"} else None, merge=data.get("merge"), optional=bool(data.get("optional", False)), error=data.get("error")))
            if header is None:
                raise ValueError("current_scan.jsonl não possui header")
            self.scan_results = list(machines.values())
            xml_path = header.get("xml_path")
            if xml_path:
                candidate = Path(str(xml_path))
                if candidate.is_file():
                    self.filtered_xml_path = candidate
                    self.control.display_xml(candidate)
            source_paths = header.get("source_paths") or []
            if source_paths and not (getattr(self.config, "source_dirs", []) or []):
                self.config.source_dirs = [str(p) for p in source_paths]
                self.control.load_paths_from_config(self.config.source_dirs, getattr(self.config, "destination_dir", None))
            self._update_counts()
            self.tree.clear()
            self.tree.populate_async(self.scan_results)
            self.summary.set_status(f"Manifesto carregado: {len(self.scan_results)} machines")
            logger.info("current_scan.jsonl carregado: %d machines", len(self.scan_results))
            self._update_ui_state()
            return True
        except Exception as exc:
            logger.exception("Falha carregando current_scan.jsonl")
            if show_errors:
                QMessageBox.warning(self, "Manifesto de Scan", f"O scan terminou, mas o current_scan.jsonl não pôde ser carregado:\n\n{exc}")
            return False

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
            QMessageBox.critical(self, "Relatório", str(exc))

    def _queue_ui(self, callback) -> None:
        QTimer.singleShot(0, callback)

    def _update_ui_state(self) -> None:
        self.control.set_scanning_state(self.scanning, xml_ready=self.filtered_xml_path is not None and self.filtered_xml_path.is_file())

    def _finish_tree_population(self, elapsed: float) -> None:
        self._update_ui_state()

    def _on_repair_requested(self, data: dict) -> None:
        return
