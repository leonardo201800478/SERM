"""Aba Scan ROMs baseada no PhysicalRomScanner.

A aba usa exclusivamente o LISTXML ativo para definir as machines esperadas,
e as pastas configuradas nela como origem física. A origem nunca é modificada.
O scan físico lê ZIPs/membros em streaming, persiste evidências no SQLite e,
ao terminar, gera atomicamente ``current_scan.jsonl``.
"""
from __future__ import annotations

import json
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

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog, QCheckBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QProgressBar, QPushButton, QSpinBox, QSplitter,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QComboBox,
)

from app.config.app_config import AppConfig
from app.core.models.filter_profile import FilterCriteria
from app.core.services.filter_service import FilterService
from app.core.services.listxml_export_service import ListxmlExportService
from app.database.database import Database
from app.gui.widgets.log_panel import LogPanel
from app.mame.physical_rom_scanner import PhysicalRomScanner

logger = logging.getLogger(__name__)
DEFAULT_MAME_VERSION = "0.289"
DEFAULT_LOG_HEIGHT = 220


class PhysicalScanWorker(QThread):
    """Executa o scanner físico em thread própria e emite somente sinais Qt."""

    progress = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, db_path: Path, source_paths: list[Path], machines: list[dict], xml_path: Path, scans_dir: Path, mame_version: str) -> None:
        super().__init__()
        self.db_path = db_path
        self.source_paths = source_paths
        self.machines = machines
        self.xml_path = xml_path
        self.scans_dir = scans_dir
        self.mame_version = mame_version
        self.scanner: PhysicalRomScanner | None = None
        self._cancel = False

    def cancel(self) -> None:
        """Solicita cancelamento do scanner físico."""
        self._cancel = True
        if self.scanner:
            self.scanner.cancel()

    def run(self) -> None:
        db = Database(self.db_path)
        try:
            db.connect()
            self.scanner = PhysicalRomScanner(db, self.source_paths)
            names = [m["name"] for m in self.machines]

            def cancelled() -> bool:
                return self._cancel

            def on_progress(current: int, message: str) -> None:
                self.progress.emit(current, message)

            stats = self.scanner.scan(
                machine_names=names,
                progress=on_progress,
                cancelled=cancelled,
            )
            if stats.get("status") == "cancelled":
                self.finished.emit(stats)
                return

            # Nunca sobrescreve um manifesto válido durante a escrita.
            temporary = self.scans_dir / "current_scan.jsonl.tmp"
            current = self.scans_dir / "current_scan.jsonl"
            self.scanner.write_manifest(
                self.machines,
                self.xml_path,
                temporary,
                self.mame_version,
                self.source_paths,
            )
            os.replace(temporary, current)
            stats["manifest_path"] = str(current)
            self.finished.emit(stats)
        except Exception as exc:
            logger.exception("Falha no worker do scan físico.")
            try:
                temporary = self.scans_dir / "current_scan.jsonl.tmp"
                if temporary.exists():
                    temporary.unlink()
            except OSError:
                logger.warning("Não foi possível remover manifesto temporário.", exc_info=True)
            self.failed.emit(str(exc))
        finally:
            try:
                db.close()
            except Exception:
                logger.debug("Falha fechando banco do worker.", exc_info=True)


class ManifestLoadWorker(QThread):
    """Carrega o manifesto sem bloquear a interface."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    def run(self) -> None:
        try:
            machines: dict[str, dict] = {}
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    if record.get("record_type") != "rom":
                        continue
                    data = record.get("record") or {}
                    name = str(data.get("machine") or "")
                    if not name:
                        continue
                    machine = machines.setdefault(name, {
                        "name": name,
                        "description": data.get("machine_description", ""),
                        "cloneof": None,
                        "roms": [],
                    })
                    machine["roms"].append(data)
            self.finished.emit(list(machines.values()))
        except Exception as exc:
            self.failed.emit(str(exc))


class ScanRomsTab(QWidget):
    """Interface principal do scan físico de ROMs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.parent_widget = parent
        self.config = AppConfig()
        self.filtered_xml_path: Path | None = None
        self.worker: PhysicalScanWorker | None = None
        self.loader: ManifestLoadWorker | None = None
        self.scanning = False
        self.scan_results: list[dict] = []
        self.scan_start_time = 0.0
        self._filter_service: FilterService | None = None
        self._build_ui()
        self._ensure_filter_service()
        self._load_paths_from_config()
        self._load_profiles()
        self._update_ui_state()
        QTimer.singleShot(150, self._load_current_manifest)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.addLayout(self._build_actions())
        layout.addLayout(self._build_xml_row())
        layout.addWidget(self._build_paths_group())
        layout.addWidget(self._build_options_group())
        layout.addWidget(self._build_summary_group())
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFormat("Aguardando scan...")
        layout.addWidget(self.progress)
        self.status_label = QLabel("Pronto.")
        layout.addWidget(self.status_label)
        self.profile_label = QLabel("Perfil ativo: (filtros da aba Filters)")
        layout.addWidget(self.profile_label)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["ROM / Machine", "Origem", "Tamanho", "CRC / SHA1", "Status"])
        self.tree.setAlternatingRowColors(True)
        layout.addWidget(self.tree, 1)
        splitter.addWidget(content)
        splitter.addWidget(self._build_log_group())
        splitter.setSizes([700, DEFAULT_LOG_HEIGHT])
        outer.addWidget(splitter)
        self.main_splitter = splitter

    def _build_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.btn_generate = QPushButton("Gerar LISTXML filtrado")
        self.btn_generate.clicked.connect(self._generate_filtered_xml)
        row.addWidget(self.btn_generate)
        row.addWidget(QLabel("Perfil:"))
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(180)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        row.addWidget(self.profile_combo)
        self.btn_scan = QPushButton("Iniciar escaneamento")
        self.btn_scan.clicked.connect(self._start_scan)
        row.addWidget(self.btn_scan)
        self.btn_stop = QPushButton("Parar")
        self.btn_stop.clicked.connect(self._stop_scan)
        self.btn_stop.setEnabled(False)
        row.addWidget(self.btn_stop)
        self.btn_open = QPushButton("Abrir pasta de scans")
        self.btn_open.clicked.connect(self._open_scans_dir)
        row.addWidget(self.btn_open)
        row.addStretch()
        return row

    def _build_xml_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel("XML ativo:"))
        self.xml_label = QLabel("Nenhum XML selecionado.")
        row.addWidget(self.xml_label, 1)
        select = QPushButton("Selecionar XML...")
        select.clicked.connect(self._select_existing_xml)
        row.addWidget(select)
        return row

    def _build_paths_group(self) -> QGroupBox:
        group = QGroupBox("Origens físicas das ROMs — somente leitura")
        grid = QGridLayout(group)
        self.source_edits: list[QLineEdit] = []
        for index in range(3):
            edit = QLineEdit()
            choose = QPushButton("Escolher")
            choose.clicked.connect(lambda _, target=edit: self._choose_directory(target))
            row = QHBoxLayout()
            row.addWidget(edit, 1)
            row.addWidget(choose)
            grid.addWidget(QLabel(f"Origem {index + 1}:"), 0, index)
            grid.addLayout(row, 1, index)
            self.source_edits.append(edit)
        grid.addWidget(QLabel("Destino:"), 2, 0)
        self.destination_edit = QLineEdit()
        grid.addWidget(self.destination_edit, 2, 1, 1, 2)
        return group

    def _build_options_group(self) -> QGroupBox:
        group = QGroupBox("Opções")
        row = QHBoxLayout(group)
        row.addWidget(QLabel("Workers:"))
        self.worker_spin = QSpinBox()
        self.worker_spin.setRange(1, 1)
        self.worker_spin.setValue(1)
        self.worker_spin.setToolTip("O scanner físico é deliberadamente serial para evitar pressão de I/O e RAM.")
        row.addWidget(self.worker_spin)
        self.alternate_checkbox = QCheckBox("Busca alternativa")
        self.alternate_checkbox.setEnabled(False)
        self.alternate_checkbox.setToolTip("Desativada: o scanner físico usa conteúdo/hash, não uma busca frágil por nome.")
        row.addWidget(self.alternate_checkbox)
        self.chd_checkbox = QCheckBox("Verificar CHDs")
        self.chd_checkbox.setChecked(True)
        self.chd_checkbox.setEnabled(False)
        self.chd_checkbox.setToolTip("CHDs são processados pelo scanner dedicado da Base MAME.")
        row.addWidget(self.chd_checkbox)
        row.addStretch()
        return group

    def _build_summary_group(self) -> QGroupBox:
        group = QGroupBox("Resumo")
        grid = QGridLayout(group)
        self.summary_labels: dict[str, QLabel] = {}
        for i, key in enumerate(("machines", "total", "valid", "missing", "invalid", "errors", "bytes")):
            title = QLabel({"machines": "Máquinas", "total": "ROMs", "valid": "Válidas", "missing": "Ausentes", "invalid": "Inválidas", "errors": "Erros", "bytes": "Bytes lidos"}[key] + ":")
            value = QLabel("0")
            grid.addWidget(title, 0, i * 2)
            grid.addWidget(value, 0, i * 2 + 1)
            self.summary_labels[key] = value
        return group

    def _build_log_group(self) -> QGroupBox:
        group = QGroupBox("Log")
        layout = QVBoxLayout(group)
        self.log_panel = LogPanel(self, logger_name="")
        layout.addWidget(self.log_panel)
        return group

    # ------------------------------------------------------------------
    # Configuração / filtros
    # ------------------------------------------------------------------

    def _get_db_connection(self):
        main_db = getattr(self.parent_widget, "db", None)
        if main_db is not None and main_db.conn is not None:
            return main_db.conn
        db = Database(getattr(self.config, "db_path", None))
        db.connect()
        return db.conn

    def _ensure_filter_service(self) -> None:
        try:
            conn = self._get_db_connection()
            self._filter_service = FilterService(conn) if conn else None
        except Exception:
            self._filter_service = None

    def _load_profiles(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("(usar filtros da aba Filters)", None)
        if self._filter_service:
            for profile in self._filter_service.get_profiles():
                self.profile_combo.addItem(profile.name, profile.id)
            default = self._filter_service.get_default_profile()
            if default:
                index = self.profile_combo.findData(default.id)
                if index >= 0:
                    self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False)
        self._on_profile_changed(self.profile_combo.currentIndex())

    def refresh_profiles(self) -> None:
        """Atualiza os perfis disponíveis na aba."""
        self._ensure_filter_service()
        self._load_profiles()

    def _on_profile_changed(self, _index: int) -> None:
        self.profile_label.setText(
            "Perfil ativo: " + (self.profile_combo.currentText() if self.profile_combo.currentIndex() > 0 else "(filtros da aba Filters)")
        )

    def _get_selected_criteria(self) -> FilterCriteria:
        selected = self.profile_combo.currentData()
        if selected is not None and self._filter_service:
            profile = self._filter_service.profile_repo.get_by_id(selected)
            if profile:
                return profile.criteria
        provider = getattr(self.parent_widget, "get_current_filter_criteria", None)
        return provider() if callable(provider) else FilterCriteria()

    def _load_paths_from_config(self) -> None:
        paths = getattr(self.config, "source_dirs", []) or []
        for index, edit in enumerate(self.source_edits):
            if index < len(paths):
                edit.setText(str(paths[index]))
        destination = getattr(self.config, "destination_dir", None)
        if destination:
            self.destination_edit.setText(str(destination))

    def _save_paths(self) -> None:
        self.config.source_dirs = [e.text().strip() for e in self.source_edits if e.text().strip()]
        self.config.destination_dir = self.destination_edit.text().strip() or None
        if callable(getattr(self.config, "save", None)):
            self.config.save()

    def _get_rom_paths(self) -> list[Path]:
        paths = []
        for edit in self.source_edits:
            text = edit.text().strip()
            if not text:
                continue
            path = Path(text).expanduser()
            if path.is_dir():
                paths.append(path)
            else:
                logger.warning("Origem física não encontrada: %s", path)
        return paths

    def _choose_directory(self, target: QLineEdit) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Selecionar diretório", target.text().strip() or str(Path.home()))
        if selected:
            target.setText(selected)

    def _scans_dir(self) -> Path:
        configured = getattr(self.config, "scans_dir", None)
        path = Path(configured) if configured else Path(getattr(self.config, "destination_dir", None) or Path.cwd() / "data" / "scans") / "scans"
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ------------------------------------------------------------------
    # XML
    # ------------------------------------------------------------------

    def _select_existing_xml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar LISTXML filtrado", str(self._scans_dir()), "XML (*.xml)")
        if path:
            self._set_active_xml(Path(path), "selecionado")

    def _set_active_xml(self, path: Path, origin: str) -> None:
        if not path.is_file():
            QMessageBox.warning(self, "XML", f"Arquivo não encontrado:\n{path}")
            return
        self.filtered_xml_path = path
        self.xml_label.setText(str(path))
        self.status_label.setText(f"XML ativo ({origin}): {path.name}")
        self._update_ui_state()

    def _generate_filtered_xml(self) -> None:
        if self.scanning:
            return
        self.btn_generate.setEnabled(False)
        try:
            service = ListxmlExportService(getattr(self.config, "db_path", None), getattr(self.config, "mame_path", None))
            ids = service.get_machine_ids_from_db(self._get_selected_criteria())
            if not ids:
                QMessageBox.warning(self, "XML", "Nenhuma machine encontrada com os filtros atuais.")
                return
            output = self._scans_dir() / f"mame_{self._get_mame_version()}_filtered_{datetime.now():%Y%m%d_%H%M%S}.xml"
            service.generate_filtered_xml(ids, output)
            self._set_active_xml(output, "gerado")
        except Exception as exc:
            logger.exception("Falha gerando LISTXML.")
            QMessageBox.critical(self, "XML", str(exc))
        finally:
            self.btn_generate.setEnabled(True)

    def _get_mame_version(self) -> str:
        path = Path(getattr(self.config, "mame_path", "")) if getattr(self.config, "mame_path", None) else None
        if not path or not path.is_file():
            return DEFAULT_MAME_VERSION
        try:
            result = subprocess.run([str(path), "-help"], capture_output=True, text=True, timeout=5, check=False)
            match = re.search(r"\bv?(\d+\.\d+)\b", result.stdout or result.stderr or "")
            return match.group(1) if match else DEFAULT_MAME_VERSION
        except Exception:
            return DEFAULT_MAME_VERSION

    def _load_machines_from_xml(self, path: Path) -> list[dict]:
        root = ET.parse(path).getroot()
        machines = []
        for element in root.findall("machine"):
            name = element.get("name", "")
            if not name:
                continue
            machines.append({
                "name": name,
                "description": (element.findtext("description") or "").strip(),
                "cloneof": element.get("cloneof"),
                "roms": [
                    {"name": r.get("name", ""), "size": int(r.get("size", 0) or 0), "crc": (r.get("crc", "") or "").lower(), "sha1": (r.get("sha1", "") or "").lower(), "merge": r.get("merge"), "optional": r.get("optional")}
                    for r in element.findall("rom") if r.get("name")
                ],
            })
        return machines

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def _start_scan(self) -> None:
        if self.scanning:
            return
        if not self.filtered_xml_path or not self.filtered_xml_path.is_file():
            QMessageBox.warning(self, "Scan", "Selecione ou gere um LISTXML primeiro.")
            return
        sources = self._get_rom_paths()
        if not sources:
            QMessageBox.warning(self, "Scan", "Nenhuma origem física válida foi configurada.")
            return
        self._save_paths()
        machines = self._load_machines_from_xml(self.filtered_xml_path)
        if not machines:
            QMessageBox.warning(self, "Scan", "O LISTXML não possui machines.")
            return
        db_path = Path(getattr(self.config, "db_path", ""))
        self.scanning = True
        self.scan_start_time = time.monotonic()
        self.scan_results = []
        self.tree.clear()
        self.progress.setValue(0)
        self.progress.setFormat("Iniciando leitura física...")
        self.status_label.setText(f"Preparado: {len(machines)} machines. Validando origem física...")
        self._update_ui_state()
        self.worker = PhysicalScanWorker(
            db_path=db_path,
            source_paths=sources,
            machines=machines,
            xml_path=self.filtered_xml_path,
            scans_dir=self._scans_dir(),
            mame_version=self._get_mame_version(),
        )
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.start()

    def _stop_scan(self) -> None:
        if self.worker:
            self.status_label.setText("Solicitando cancelamento...")
            self.worker.cancel()
            self.btn_stop.setEnabled(False)

    def _on_worker_progress(self, current: int, message: str) -> None:
        self.status_label.setText(message)
        self.progress.setRange(0, 0)
        self.summary_labels["bytes"].setText(self._extract_bytes(message))
        if self.parent_widget and hasattr(self.parent_widget, "status_bar"):
            self.parent_widget.status_bar.showMessage(message)

    @staticmethod
    def _extract_bytes(message: str) -> str:
        match = re.search(r"bytes lidos ([\d,]+)", message)
        return match.group(1) if match else "0"

    def _on_worker_finished(self, stats: dict) -> None:
        self.scanning = False
        self.progress.setRange(0, 100)
        if stats.get("status") == "cancelled":
            self.status_label.setText("Scan físico cancelado.")
            self._update_ui_state()
            return
        elapsed = time.monotonic() - self.scan_start_time
        self.status_label.setText(f"Scan físico concluído em {elapsed:.1f}s — {stats.get('bytes_read', 0):,} bytes lidos.")
        self.progress.setValue(100)
        self.progress.setFormat("Scan físico concluído — current_scan.jsonl atualizado")
        self._update_summary_from_stats(stats)
        self.worker = None
        self._load_current_manifest()
        self._update_ui_state()

    def _on_worker_failed(self, message: str) -> None:
        self.scanning = False
        self.worker = None
        self.progress.setRange(0, 100)
        self.status_label.setText("Falha no scan físico.")
        self._update_ui_state()
        QMessageBox.critical(self, "Scan físico", message)

    # ------------------------------------------------------------------
    # Manifesto / árvore
    # ------------------------------------------------------------------

    def _load_current_manifest(self) -> None:
        path = self._scans_dir() / "current_scan.jsonl"
        if not path.is_file():
            return
        if self.loader and self.loader.isRunning():
            return
        self.loader = ManifestLoadWorker(path)
        self.loader.finished.connect(self._on_manifest_loaded)
        self.loader.failed.connect(lambda msg: logger.error("Falha carregando current_scan.jsonl: %s", msg))
        self.loader.start()

    def _on_manifest_loaded(self, machines: list[dict]) -> None:
        self.scan_results = machines
        self._populate_tree(machines)
        valid = missing = invalid = errors = total = 0
        for machine in machines:
            for rom in machine["roms"]:
                total += 1
                status = str(rom.get("status", "missing")).lower()
                if status == "valid":
                    valid += 1
                elif status == "missing":
                    missing += 1
                elif status in {"sha1_mismatch", "invalid", "corrupted"}:
                    invalid += 1
                else:
                    errors += 1
        self._set_summary(len(machines), total, valid, missing, invalid, errors)
        if machines and not self.scanning:
            self.status_label.setText(f"current_scan.jsonl carregado: {len(machines)} machines")

    def _populate_tree(self, machines: list[dict]) -> None:
        self.tree.clear()
        for machine in machines:
            machine_item = QTreeWidgetItem([machine["name"], machine.get("description", ""), "", "", ""])
            self.tree.addTopLevelItem(machine_item)
            for rom in machine.get("roms", []):
                source = rom.get("source") or {}
                origin = source.get("archive") or ""
                member = source.get("member")
                if member:
                    origin = f"{origin}!{member}"
                expected = f"{rom.get('expected_crc', '')} / {rom.get('expected_sha1', '')[:12]}"
                status = str(rom.get("status", "missing"))
                item = QTreeWidgetItem([
                    f"  {rom.get('rom_name', '')}", origin,
                    str(rom.get("actual_size") or rom.get("expected_size") or 0), expected, status,
                ])
                if status == "valid":
                    item.setForeground(4, QColor("#008000"))
                elif status == "missing":
                    item.setForeground(4, QColor("#808080"))
                else:
                    item.setForeground(4, QColor("#CC0000"))
                machine_item.addChild(item)
        self.tree.expandToDepth(0)

    def _update_summary_from_stats(self, stats: dict) -> None:
        self.summary_labels["machines"].setText(str(self._machine_count_from_xml()))
        self.summary_labels["valid"].setText(str(stats.get("valid", 0)))
        self.summary_labels["invalid"].setText(str(stats.get("sha1_mismatch", 0)))
        self.summary_labels["errors"].setText(str(stats.get("read_errors", 0)))
        self.summary_labels["bytes"].setText(f"{stats.get('bytes_read', 0):,}")

    def _machine_count_from_xml(self) -> int:
        if not self.filtered_xml_path or not self.filtered_xml_path.is_file():
            return 0
        try:
            return len(ET.parse(self.filtered_xml_path).getroot().findall("machine"))
        except Exception:
            return 0

    def _set_summary(self, machines: int, total: int, valid: int, missing: int, invalid: int, errors: int) -> None:
        values = {"machines": machines, "total": total, "valid": valid, "missing": missing, "invalid": invalid, "errors": errors}
        for key, value in values.items():
            self.summary_labels[key].setText(str(value))

    def _reset_summary(self) -> None:
        self._set_summary(0, 0, 0, 0, 0, 0)
        self.summary_labels["bytes"].setText("0")

    # ------------------------------------------------------------------
    # Estado / utilidades
    # ------------------------------------------------------------------

    def _update_ui_state(self) -> None:
        active = self.scanning
        self.btn_scan.setEnabled(not active and self.filtered_xml_path is not None)
        self.btn_generate.setEnabled(not active)
        self.btn_stop.setEnabled(active)

    def _open_scans_dir(self) -> None:
        path = self._scans_dir()
        try:
            if os.name == "nt":
                os.startfile(str(path))
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            QMessageBox.warning(self, "Pasta", str(exc))

    def _delayed_load_scan(self) -> None:
        """Restaura o último manifesto automaticamente ao abrir a aplicação."""
        self._load_current_manifest()

    # Compatibilidade com código antigo que consulta estes métodos.
    def worker_count(self) -> int:
        return 1

    def alternate_search_enabled(self) -> bool:
        return False

    def include_chds(self) -> bool:
        return False


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# Compatibilidade para imports antigos. O engine foi removido do fluxo.
LoadManifestWorker = ManifestLoadWorker
