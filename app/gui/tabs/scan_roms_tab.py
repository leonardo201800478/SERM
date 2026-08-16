"""
MAME Set Builder
================

Aba "Scan Roms".

Responsabilidades da aba (orquestração)
----------------------------------------
1. Gerar o LISTXML filtrado.
2. Selecionar um LISTXML filtrado existente.
3. Ler exclusivamente as máquinas presentes no XML.
4. Enviar as máquinas/ROMs para o RomScanner.
5. Executar o scanner fora da thread principal do Qt.
6. Exibir progresso em tempo real.
7. Permitir cancelamento.
8. Exibir resumo do scan.
9. Exibir máquinas e ROMs em árvore.
10. Exibir detalhes dos resultados.
11. Preservar os resultados do último scan em memória.
12. Permitir selecionar um perfil de filtro específico para geração do XML.

Toda a apresentação (XML/perfil/diretórios, progresso/contadores e
árvore de resultados) vive em widgets dedicados em
``app/gui/widgets/scan/``. Esta classe cuida apenas da fiação entre
eles, da integração com banco/filtros e da execução do scan em thread
separada — ela não conhece detalhes de layout desses blocos.

Regra fundamental
------------------
O XML filtrado é a fonte de verdade.

Esta aba NÃO deve:

    * consultar o banco para decidir quais ROMs serão escaneadas;
    * varrer todos os ZIPs existentes;
    * criar um índice global de ROMs;
    * procurar ROMs que não estejam no XML.

Fluxo
-----
    ScanControlWidget (perfil/XML)
       |
       v
    LISTXML filtrado
       |
       v
    leitura do XML
       |
       v
    Machine / ROM / Disk
       |
       v
    RomScanner
       |
       v
    resultados
       |
       +---- ScanSummaryWidget (resumo/progresso)
       |
       +---- RomTreeWidget (árvore/reparo)
       |
       +---- LogPanel (log)
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import threading
import time
import xml.etree.ElementTree as ET

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.config.app_config import AppConfig

from app.core.services.filter_service import FilterService
from app.core.services.listxml_export_service import ListxmlExportService
from app.database.database import Database
from app.gui.widgets.log_panel import LogPanel
from app.gui.widgets import ScanControlWidget, ScanSummaryWidget, RomTreeWidget
from app.gui.widgets.rom_tree_widget import value_of, as_int
from app.mame.rom_scanner import RomScanner


logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTES DA INTERFACE
# ============================================================================

DEFAULT_LOG_HEIGHT = 220
MIN_LOG_HEIGHT = 80
MAX_LOG_HEIGHT = 900
DEFAULT_MAME_VERSION = "0.289"


# ============================================================================
# ABA (ORQUESTRADORA)
# ============================================================================

class ScanRomsTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.parent_widget = parent
        self.config = AppConfig()

        # ------------------------------------------------------------------
        # ESTADO DO XML
        # ------------------------------------------------------------------
        self.filtered_xml_path: Path | None = None

        # ------------------------------------------------------------------
        # ESTADO DO SCAN
        # ------------------------------------------------------------------
        self.scanning = False
        self.scanner: RomScanner | None = None
        self.scan_thread: threading.Thread | None = None
        self.scan_results: list[Any] = []
        self.scan_start_time: float | None = None
        self.progress_current = 0
        self.scan_stats = {"valid": 0, "missing": 0, "invalid": 0, "error": 0}
        self.progress_total = 0
        self.total_machines = 0

        # ------------------------------------------------------------------
        # SERVIÇO DE FILTRO (para obter perfis)
        # ------------------------------------------------------------------
        self._filter_service = None
        self._ensure_filter_service()

        # ------------------------------------------------------------------
        # UI
        # ------------------------------------------------------------------
        self._build_ui()
        self._wire_signals()
        self._load_paths_from_config()
        self._load_profiles()
        self._update_ui_state()

    # ========================================================================
    # INICIALIZAÇÃO DO FILTER SERVICE
    # ========================================================================

    def _ensure_filter_service(self) -> None:
        """Recria o FilterService com a conexão atual do banco, se necessário."""
        try:
            conn = self._get_db_connection()
            if conn is None:
                self._filter_service = None
                return
            if (self._filter_service is not None and
                    hasattr(self._filter_service, "conn") and
                    self._filter_service.conn is conn):
                return
            self._filter_service = FilterService(conn)
        except Exception:
            self._filter_service = None

    # ========================================================================
    # CONSTRUÇÃO DA INTERFACE
    # ========================================================================

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Vertical)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self.control_widget = ScanControlWidget()
        layout.addWidget(self.control_widget)

        self.summary_widget = ScanSummaryWidget()
        layout.addWidget(self.summary_widget)

        self.tree = RomTreeWidget()
        layout.addWidget(self.tree)

        splitter.addWidget(content)
        splitter.addWidget(self._build_log_group())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([650, DEFAULT_LOG_HEIGHT])

        outer.addWidget(splitter)
        self.main_splitter = splitter

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
        total = self.main_splitter.height()
        if total <= 0:
            total = 650 + value
        top = max(150, total - value)
        self.main_splitter.setSizes([top, value])

    # ========================================================================
    # FIAÇÃO DE SINAIS
    # ========================================================================

    def _wire_signals(self) -> None:
        self.control_widget.generate_xml_requested.connect(self._generate_filtered_xml)
        self.control_widget.select_xml_requested.connect(self._select_existing_xml)
        self.control_widget.open_folder_requested.connect(self._open_scans_dir)
        self.control_widget.start_scan_requested.connect(self._start_scan)
        self.control_widget.stop_scan_requested.connect(self._stop_scan)
        self.control_widget.profile_changed.connect(self._on_profile_combo_changed)

        self.tree.population_finished.connect(self._finish_tree_population)
        self.tree.repair_requested.connect(self._on_repair_requested)

    # ========================================================================
    # PERFIS
    # ========================================================================

    def _load_profiles(self) -> None:
        if self._filter_service is None:
            self.control_widget.load_profiles([])
            self._update_profile_label()
            return

        profiles = self._filter_service.get_profiles()
        default_profile = self._filter_service.get_default_profile()
        default_id = default_profile.id if default_profile else None

        self.control_widget.load_profiles(profiles, default_id)
        self._update_profile_label()

    def _on_profile_combo_changed(self, index: int) -> None:
        self._update_profile_label()

    def _update_profile_label(self) -> None:
        self.summary_widget.set_profile_label(self.control_widget.current_profile_label())

    def refresh_profiles(self) -> None:
        self._ensure_filter_service()
        self._load_profiles()

    # ========================================================================
    # OBTENÇÃO DOS CRITÉRIOS
    # ========================================================================

    def _get_selected_criteria(self) -> Any:
        self._ensure_filter_service()

        selected_id = self.control_widget.current_profile_id()
        if selected_id is not None and self._filter_service is not None:
            profile = self._filter_service.profile_repo.get_by_id(selected_id)
            if profile:
                return profile.criteria

        provider = getattr(self.parent_widget, "get_current_filter_criteria", None)
        if callable(provider):
            criteria = provider()
            if criteria is not None:
                return criteria

        from app.core.models.filter_profile import FilterCriteria
        return FilterCriteria()

    # ========================================================================
    # CONFIGURAÇÃO
    # ========================================================================

    def _load_paths_from_config(self) -> None:
        source_dirs = getattr(self.config, "source_dirs", []) or []
        destination = getattr(self.config, "destination_dir", None)
        self.control_widget.load_paths_from_config(source_dirs, destination)

    def _save_paths(self) -> None:
        paths, destination = self.control_widget.collect_paths_for_save()
        try:
            if hasattr(self.config, "source_dirs"):
                self.config.source_dirs = paths
            if hasattr(self.config, "destination_dir"):
                self.config.destination_dir = destination or None
            save_method = getattr(self.config, "save", None)
            if callable(save_method):
                save_method()
        except Exception:
            logger.warning("Não foi possível persistir as configurações de diretórios.", exc_info=True)

    # ========================================================================
    # DATABASE
    # ========================================================================

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

    # ========================================================================
    # DIRETÓRIOS DE SCANS
    # ========================================================================

    def _scans_dir(self) -> Path:
        configured = getattr(self.config, "scans_dir", None)
        if configured:
            path = Path(configured)
        else:
            destination_text = self.control_widget.get_destination()
            if destination_text:
                path = Path(destination_text) / "scans"
            else:
                path = Path.cwd() / "data" / "scans"
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ========================================================================
    # XML
    # ========================================================================

    def _select_existing_xml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar LISTXML filtrado",
            str(self._scans_dir()),
            "XML (*.xml);;Todos os arquivos (*)",
        )
        if path:
            self._set_active_xml(Path(path), "selecionado manualmente")

    def _set_active_xml(self, path: Path, origin: str) -> None:
        path = path.expanduser()
        if not path.is_file():
            QMessageBox.warning(self, "XML inválido", f"O arquivo não existe:\n{path}")
            return

        self.filtered_xml_path = path
        self.control_widget.display_xml(path)
        self.summary_widget.set_status(f"XML ativo ({origin}): {path.name}")
        logger.info("XML ativo para scan (%s): %s", origin, path)
        self._update_ui_state()

    def _open_scans_dir(self) -> None:
        path = self._scans_dir()
        try:
            if os.name == "nt":
                os.startfile(str(path))
            elif os.name == "posix":
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            QMessageBox.warning(self, "Erro", f"Não foi possível abrir a pasta:\n{exc}")

    # ========================================================================
    # GERAÇÃO DO XML
    # ========================================================================

    def _generate_filtered_xml(self) -> None:
        if self.scanning:
            return

        self.control_widget.btn_generate.setEnabled(False)
        self.summary_widget.set_status("Gerando LISTXML filtrado...")

        try:
            db_path = getattr(self.config, "db_path", None)
            mame_path = getattr(self.config, "mame_path", None)

            service = ListxmlExportService(db_path, mame_path)

            criteria = self._get_selected_criteria()
            machine_ids = service.get_machine_ids_from_db(criteria)

            if not machine_ids:
                QMessageBox.warning(
                    self,
                    "Nenhuma máquina",
                    "Nenhuma máquina foi encontrada com os filtros atuais.",
                )
                return

            version = self._get_mame_version()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"mame_{version}_filtered_{timestamp}.xml"
            output_path = self._scans_dir() / filename

            service.generate_filtered_xml(machine_ids, output_path)

            self._set_active_xml(output_path, "recém-gerado")

            QMessageBox.information(
                self,
                "XML gerado",
                f"LISTXML filtrado gerado com sucesso.\n\nMáquinas: {len(machine_ids)}\nArquivo:\n{output_path}"
            )

        except Exception as exc:
            logger.exception("Erro gerando LISTXML filtrado.")
            QMessageBox.critical(self, "Erro", f"Não foi possível gerar o XML:\n{exc}")
            self.summary_widget.set_status("Erro ao gerar XML.")

        finally:
            self.control_widget.btn_generate.setEnabled(True)
            self._update_ui_state()

    def _get_mame_version(self) -> str:
        mame_path = getattr(self.config, "mame_path", None)
        if mame_path is not None and not isinstance(mame_path, Path):
            mame_path = Path(str(mame_path))
        if not mame_path or not mame_path.is_file():
            return DEFAULT_MAME_VERSION

        try:
            result = subprocess.run(
                [str(mame_path), "-help"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            text = result.stdout or result.stderr or ""
            match = re.search(r"\bv?(\d+\.\d+)\b", text)
            if match:
                return match.group(1)
        except Exception:
            logger.debug("Não foi possível detectar a versão do MAME.", exc_info=True)

        return DEFAULT_MAME_VERSION

    # ========================================================================
    # INÍCIO DO SCAN
    # ========================================================================

    def _start_scan(self) -> None:
        if self.scanning:
            return

        if self.filtered_xml_path is None or not self.filtered_xml_path.is_file():
            QMessageBox.warning(
                self,
                "XML necessário",
                "Selecione ou gere primeiro um LISTXML filtrado.",
            )
            return

        rom_paths = self.control_widget.get_rom_paths()
        if not rom_paths:
            answer = QMessageBox.question(
                self,
                "Nenhuma origem",
                "Nenhuma origem válida de ROM foi configurada.\n\nDeseja continuar mesmo assim?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self._save_paths()

        self.scanning = True
        self.scanner = None
        self.scan_results = []
        self.progress_current = 0
        self.progress_total = 0
        self.total_machines = 0
        self.scan_start_time = time.monotonic()
        self.scan_stats = {"valid": 0, "missing": 0, "invalid": 0, "error": 0}
        self._update_summary_from_stats()

        self.tree.clear()
        self._reset_summary()
        self.summary_widget.set_progress(0, "Carregando XML...")
        self.summary_widget.set_status("Carregando XML filtrado...")
        self._update_ui_state()

        self.scan_thread = threading.Thread(
            target=self._do_scan,
            name="mame-rom-scan",
            daemon=True,
        )
        self.scan_thread.start()

    # ========================================================================
    # CANCELAMENTO
    # ========================================================================

    def _stop_scan(self) -> None:
        if not self.scanning:
            return

        logger.info("Cancelamento do scan solicitado pelo usuário.")
        self.summary_widget.set_status("Solicitando cancelamento...")
        self.control_widget.btn_stop.setEnabled(False)

        if self.scanner is not None:
            self.scanner.cancel()

    # ========================================================================
    # EXECUÇÃO DO SCAN
    # ========================================================================

    def _do_scan(self) -> None:
        """Executa o scan em thread separada e agenda a atualização da UI."""
        try:
            xml_path = self.filtered_xml_path
            if xml_path is None or not xml_path.is_file():
                raise FileNotFoundError("LISTXML filtrado não encontrado.")

            self._queue_status("Lendo XML filtrado...")
            machines = self._load_machines_from_xml(xml_path)

            total_items = sum(
                len(machine.get("roms", []))
                + (len(machine.get("disks", [])) if self.control_widget.include_chds() else 0)
                for machine in machines
            )

            self.progress_total = total_items
            self.total_machines = len(machines)

            self._queue_summary(machines=len(machines), total=total_items)
            self._queue_status(f"Preparado: {len(machines)} máquinas / {total_items} itens.")

            if not machines:
                self._queue_ui(lambda: self._show_no_machines())
                return

            rom_paths = self.control_widget.get_rom_paths()

            scanner = RomScanner(
                rom_paths=rom_paths,
                max_workers=self.control_widget.worker_count(),
                progress_callback=self._on_rom_progress,
                machine_callback=self._on_machine_complete,
                log_callback=self._on_scanner_log,
                enable_alternate_search=self.control_widget.alternate_search_enabled(),
                include_chds=self.control_widget.include_chds(),
            )

            self.scanner = scanner
            self._queue_status(f"Escaneando 0/{total_items}...")

            results = scanner.scan(machines)
            self.scan_results = results
            cancelled = scanner.cancelled

            logger.info(
                "Scan finalizado. Resultados: %d máquinas, cancelado=%s",
                len(results),
                cancelled,
            )

            if cancelled:
                logger.info("Scan cancelado, finalizando sem popular árvore.")
                self._queue_ui(lambda: self._finish_scan(cancelled=True))
            else:
                logger.info("Scan concluído, iniciando população da árvore...")
                self._queue_ui(self._populate_tree)

            logger.info("Todas as atualizações da UI foram enfileiradas.")

        except Exception as exc:
            logger.exception("Erro geral durante o scan.")
            self._queue_ui(lambda: self._show_scan_error(str(exc)))

    # ========================================================================
    # LEITURA DO XML
    # ========================================================================

    def _load_machines_from_xml(self, xml_path: Path) -> list[dict[str, Any]]:
        logger.info("Lendo XML filtrado: %s", xml_path)
        tree = ET.parse(xml_path)
        root = tree.getroot()

        machines: list[dict[str, Any]] = []
        machine_elements = root.findall("machine")
        logger.info("XML contém %d máquina(s).", len(machine_elements))

        for machine_element in machine_elements:
            machine_name = machine_element.get("name", "")
            if not machine_name:
                continue

            description_element = machine_element.find("description")
            description = ""
            if description_element is not None:
                description = (description_element.text or "").strip()

            roms: list[dict[str, Any]] = []
            for rom_element in machine_element.findall("rom"):
                rom_name = rom_element.get("name", "")
                if not rom_name:
                    continue
                roms.append({
                    "name": rom_name,
                    "size": as_int(rom_element.get("size", 0)),
                    "crc": (rom_element.get("crc", "") or "").lower(),
                    "sha1": (rom_element.get("sha1", "") or "").lower(),
                    "merge": rom_element.get("merge"),
                    "status": rom_element.get("status"),
                    "optional": rom_element.get("optional"),
                })

            disks: list[dict[str, Any]] = []
            for disk_element in machine_element.findall("disk"):
                disk_name = disk_element.get("name", "")
                if not disk_name:
                    continue
                disks.append({
                    "name": disk_name,
                    "sha1": (disk_element.get("sha1", "") or "").lower(),
                    "merge": disk_element.get("merge"),
                    "region": disk_element.get("region"),
                    "index": disk_element.get("index"),
                })

            machines.append({
                "name": machine_name,
                "description": description,
                "cloneof": machine_element.get("cloneof"),
                "roms": roms,
                "disks": disks,
            })

        return machines

    # ========================================================================
    # CALLBACK ROM
    # ========================================================================

    def _on_rom_progress(self, current: int, total: int, result: Any) -> None:
        self.progress_current = current
        self.progress_total = total

        status = str(value_of(result, "status", "")).lower()
        if status == "valid":
            self.scan_stats["valid"] += 1
        elif status == "missing":
            self.scan_stats["missing"] += 1
        elif status == "invalid":
            self.scan_stats["invalid"] += 1
        elif status == "error":
            self.scan_stats["error"] += 1

        machine_name = str(value_of(result, "machine_name", ""))
        rom_name = str(value_of(result, "rom_name", ""))

        self._queue_ui(lambda: self._update_progress_ui(current, total, machine_name, rom_name, status))
        self._queue_ui(self._update_summary_from_stats)
        self._queue_ui(self._update_mainwindow_status)

    def _update_summary_from_stats(self) -> None:
        found = self.scan_stats["valid"] + self.scan_stats["invalid"] + self.scan_stats["error"]
        self.summary_widget.update_counts({
            "valid": self.scan_stats["valid"],
            "missing": self.scan_stats["missing"],
            "bad": self.scan_stats["invalid"],
            "error": self.scan_stats["error"],
            "total": self.progress_total,
            "found": found,
        })

    def _update_progress_ui(self, current: int, total: int, machine_name: str, rom_name: str, status: str) -> None:
        percentage = int(current * 100 / total) if total > 0 else 0
        self.summary_widget.set_progress(percentage, f"{current}/{total} ROMs — {percentage}%")

        from app.gui.widgets.rom_tree_widget import STATUS_LABELS
        status_text = STATUS_LABELS.get(status, status.upper() if status else "PROCESSANDO")
        stats_text = (
            f"✓ {self.scan_stats['valid']} | "
            f"✗ {self.scan_stats['missing']} | "
            f"⚠ {self.scan_stats['invalid']} | "
            f"! {self.scan_stats['error']}"
        )
        self.summary_widget.set_status(
            f"Escaneando {current}/{total}: {machine_name} — {rom_name} [{status_text}]  "
            f"({stats_text})"
        )

    def _update_mainwindow_status(self) -> None:
        """Atualiza a barra de status da janela principal com o progresso."""
        if self.parent_widget and hasattr(self.parent_widget, 'status_bar'):
            stats_text = (
                f"Válidas: {self.scan_stats['valid']} | "
                f"Ausentes: {self.scan_stats['missing']} | "
                f"Inválidas: {self.scan_stats['invalid']} | "
                f"Erros: {self.scan_stats['error']}"
            )
            message = f"Escaneando {self.progress_current}/{self.progress_total} ROMs — {stats_text}"
            self.parent_widget.status_bar.showMessage(message)

    # ========================================================================
    # CALLBACK MÁQUINA
    # ========================================================================

    def _on_machine_complete(self, result: Any) -> None:
        machine_name = str(value_of(result, "machine_name", ""))
        total = as_int(value_of(result, "total", 0))
        valid = as_int(value_of(result, "valid", 0))
        missing = as_int(value_of(result, "missing", 0))
        bad = as_int(value_of(result, "bad", 0))

        self._queue_status(
            f"Máquina concluída: {machine_name} — "
            f"{valid}/{total} válidas, {missing} ausentes, {bad} inválidas."
        )
        self._queue_ui(self._update_summary_from_stats)

    # ========================================================================
    # LOG
    # ========================================================================

    def _on_scanner_log(self, message: str) -> None:
        logger.info("%s", message)

    # ========================================================================
    # REPARO
    # ========================================================================

    def _on_repair_requested(self, payload: dict) -> None:
        """Recebe o pedido de reparo emitido pela árvore.

        A resolução automática de dependências/fontes alternativas
        pertence a fases futuras do projeto (ver REGRA Nº 24/25 do
        prompt mestre); aqui apenas confirmamos o pedido e registramos
        no log, sem prometer uma ação que ainda não existe.
        """
        rom = payload.get("rom")
        machine = payload.get("machine")
        rom_name = str(value_of(rom, "rom_name", ""))
        machine_name = str(value_of(machine, "machine_name", ""))

        logger.info("Reparo solicitado: machine=%s rom=%s", machine_name, rom_name)

        QMessageBox.information(
            self,
            "Reparo",
            (
                f"Máquina: {machine_name}\n"
                f"ROM: {rom_name}\n\n"
                "A busca automática por uma fonte alternativa ainda não "
                "está implementada nesta fase do projeto. Este pedido foi "
                "registrado no log."
            ),
        )

    # ========================================================================
    # UI THREAD
    # ========================================================================

    def _queue_ui(self, callback) -> None:
        QTimer.singleShot(0, callback)

    def _queue_status(self, text: str) -> None:
        self._queue_ui(lambda: self.summary_widget.set_status(text))

    def _queue_summary(self, *, machines: int, total: int) -> None:
        def update():
            self.summary_widget.update_counts({"machines": machines, "total": total})
        self._queue_ui(update)

    # ========================================================================
    # FINALIZAÇÃO
    # ========================================================================

    def _finish_scan(self, *, cancelled: bool) -> None:
        logger.info("=== INÍCIO _finish_scan (cancelled=%s) ===", cancelled)
        self.scanning = False
        self.scanner = None

        try:
            self._update_summary_from_results()
            self._update_summary_from_stats()

            if cancelled:
                percentage = int(self.progress_current * 100 / self.progress_total) if self.progress_total > 0 else 0
                self.summary_widget.set_progress(percentage, f"{self.progress_current}/{self.progress_total} itens — {percentage}%")
                if self.parent_widget and hasattr(self.parent_widget, 'status_bar'):
                    self.parent_widget.status_bar.showMessage("Escaneamento interrompido.")
                self._update_ui_state()
            else:
                elapsed = 0.0
                if self.scan_start_time:
                    elapsed = time.monotonic() - self.scan_start_time
                if self.parent_widget and hasattr(self.parent_widget, 'status_bar'):
                    self.parent_widget.status_bar.showMessage(
                        f"Escaneamento concluído em {elapsed:.2f}s. Populando árvore..."
                    )
                self.summary_widget.set_progress(100, f"{self.progress_total}/{self.progress_total} itens — 100%")

                if not self.scan_results:
                    if self.parent_widget and hasattr(self.parent_widget, 'status_bar'):
                        self.parent_widget.status_bar.showMessage(
                            f"Escaneamento concluído em {elapsed:.2f}s. Nenhuma máquina."
                        )
                    self._update_ui_state()
                else:
                    logger.info("Aguardando término da população da árvore para habilitar UI.")

            logger.info("=== FIM _finish_scan (processamento inicial concluído) ===")

        except Exception as e:
            logger.exception("Erro em _finish_scan: %s", e)
            self._update_ui_state()

    def _show_no_machines(self) -> None:
        self.scanning = False
        self.scanner = None
        if self.parent_widget and hasattr(self.parent_widget, 'status_bar'):
            self.parent_widget.status_bar.showMessage("O XML filtrado não possui máquinas.")
        self.summary_widget.set_progress(0, "Aguardando scan...")
        self._update_ui_state()
        QMessageBox.warning(self, "XML vazio", "O LISTXML selecionado não contém nenhuma máquina.")

    def _show_scan_error(self, error: str) -> None:
        self.scanning = False
        self.scanner = None
        if self.parent_widget and hasattr(self.parent_widget, 'status_bar'):
            self.parent_widget.status_bar.showMessage(f"Erro: {error}")
        self._update_ui_state()
        QMessageBox.critical(self, "Erro no escaneamento", f"Ocorreu um erro durante o scan:\n\n{error}")

    # ========================================================================
    # RESUMO
    # ========================================================================

    def _reset_summary(self) -> None:
        self.scan_stats = {"valid": 0, "missing": 0, "invalid": 0, "error": 0}
        self.summary_widget.reset()
        if self.parent_widget and hasattr(self.parent_widget, 'status_bar'):
            self.parent_widget.status_bar.showMessage("Pronto")

    def _update_summary_from_results(self) -> None:
        logger.info("=== INÍCIO _update_summary_from_results ===")
        try:
            machines = len(self.scan_results)
            total = found = valid = missing = bad = error = 0

            for machine in self.scan_results:
                total += as_int(value_of(machine, "total", 0))
                found += as_int(value_of(machine, "found", 0))
                valid += as_int(value_of(machine, "valid", 0))
                missing += as_int(value_of(machine, "missing", 0))
                bad += as_int(value_of(machine, "bad", 0))
                error += as_int(value_of(machine, "error", 0))

            self.summary_widget.update_counts({
                "machines": machines,
                "total": total,
                "found": found,
                "valid": valid,
                "missing": missing,
                "bad": bad,
                "error": error,
            })

            logger.info("Resumo atualizado: máquinas=%d, total=%d, válidos=%d", machines, total, valid)
            logger.info("=== FIM _update_summary_from_results ===")
        except Exception as e:
            logger.exception("Erro ao atualizar resumo: %s", e)

    # ========================================================================
    # ÁRVORE
    # ========================================================================

    def _populate_tree(self) -> None:
        """Dispara a população em lote da árvore de resultados."""
        logger.info("=== INÍCIO _populate_tree() ===")

        def on_progress(done: int, total: int) -> None:
            progress = int(done * 100 / total) if total else 100
            self.summary_widget.set_progress(progress, f"Populando árvore: {done}/{total}")
            if self.parent_widget and hasattr(self.parent_widget, 'status_bar'):
                self.parent_widget.status_bar.showMessage(
                    f"Populando árvore: {done}/{total} máquinas"
                )

        self.tree.populate_async(self.scan_results, on_progress=on_progress)

    def _finish_tree_population(self, elapsed: float) -> None:
        """Finaliza o processo de população da árvore e habilita a UI."""
        total_machines = len(self.scan_results)
        if self.parent_widget and hasattr(self.parent_widget, 'status_bar'):
            self.parent_widget.status_bar.showMessage(
                f"Escaneamento concluído em {elapsed:.2f}s. Árvore populada com {total_machines} máquinas."
            )
        self.summary_widget.set_progress(100, f"{total_machines}/{total_machines} máquinas — 100%")
        self.scanning = False
        self.scanner = None
        self._update_summary_from_results()
        self._update_ui_state()
        logger.info("=== FIM _finish_tree_population ===")

    # ========================================================================
    # PERFIL ATIVO (mantido para compatibilidade com a MainWindow)
    # ========================================================================

    def set_active_profile_name(self, name: str | None) -> None:
        if self.parent_widget and hasattr(self.parent_widget, 'status_bar'):
            if name:
                self.parent_widget.status_bar.showMessage(f"Perfil ativo: {name}")
            else:
                self.parent_widget.status_bar.showMessage("Perfil ativo: (nenhum)")

    # ========================================================================
    # ESTADO DA INTERFACE
    # ========================================================================

    def _update_ui_state(self) -> None:
        xml_ready = self.filtered_xml_path is not None and self.filtered_xml_path.is_file()
        self.control_widget.set_scanning_state(self.scanning, xml_ready=xml_ready)

    # ========================================================================
    # DESTRUTOR
    # ========================================================================

    def closeEvent(self, event) -> None:
        if self.scanning and self.scanner is not None:
            self.scanner.cancel()
        # Sem isso, o QtLogHandler de LogPanel permanece registrado no
        # logger raiz apontando para um QPlainTextEdit já destruído,
        # arriscando RuntimeError do Qt no próximo log emitido.
        if hasattr(self, "log_panel"):
            self.log_panel.detach()
        event.accept()
