"""
MAME Set Builder
================

Aba "Scan Roms".

Responsabilidades
-----------------
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

Regra fundamental
-----------------
O XML filtrado é a fonte de verdade.

Esta aba NÃO deve:

    * consultar o banco para decidir quais ROMs serão escaneadas;
    * varrer todos os ZIPs existentes;
    * criar um índice global de ROMs;
    * procurar ROMs que não estejam no XML.

Fluxo
-----
    Filtros (selecionados via combobox ou fallback)
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
       +---- resumo
       |
       +---- árvore
       |
       +---- detalhes
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
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from app.config.app_config import AppConfig

from app.core.services.filter_service import FilterService
from app.core.services.listxml_export_service import ListxmlExportService
from app.database.database import Database
from app.gui.widgets.log_panel import LogPanel
from app.mame.rom_scanner import RomScanner


logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTES DA INTERFACE
# ============================================================================

DEFAULT_LOG_HEIGHT = 220
MIN_LOG_HEIGHT = 80
MAX_LOG_HEIGHT = 900
DEFAULT_WORKERS = 1
DEFAULT_MAME_VERSION = "0.289"


# ============================================================================
# CORES DOS ESTADOS
# ============================================================================

STATUS_COLORS = {
    "good": "#008000",
    "bad": "#CC8800",
    "missing": "#808080",
    "error": "#CC0000",
    "cancelled": "#808080",
}

STATUS_LABELS = {
    "good": "OK",
    "bad": "INVÁLIDA",
    "missing": "AUSENTE",
    "error": "ERRO",
    "cancelled": "CANCELADA",
}


# ============================================================================
# HELPERS
# ============================================================================

def _value(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _as_path(value: Any) -> Path | None:
    if value is None:
        return None
    if isinstance(value, Path):
        return value
    text = str(value).strip()
    return Path(text) if text else None


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _format_size(value: Any) -> str:
    size = _as_int(value)
    if size < 1024:
        return f"{size} B"
    if size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    if size < 1024 ** 3:
        return f"{size / (1024 ** 2):.1f} MB"
    if size < 1024 ** 4:
        return f"{size / (1024 ** 3):.2f} GB"
    return f"{size / (1024 ** 4):.2f} TB"


# ============================================================================
# ABA
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
        self.progress_total = 0
        self.total_machines = 0

        # ------------------------------------------------------------------
        # SERVIÇO DE FILTRO (para obter perfis)
        # ------------------------------------------------------------------
        self._filter_service: Optional[FilterService] = None
        self._init_filter_service()

        # ------------------------------------------------------------------
        # UI
        # ------------------------------------------------------------------
        self._build_ui()
        self._load_paths_from_config()
        self._load_profiles()
        self._update_ui_state()

    # ========================================================================
    # INICIALIZAÇÃO DO FILTER SERVICE
    # ========================================================================

    def _init_filter_service(self) -> None:
        conn = self._get_db_connection()
        if conn is not None:
            self._filter_service = FilterService(conn)

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

        # ---- Ações (com seletor de perfil) ----
        layout.addLayout(self._build_actions())

        # ---- XML ativo ----
        layout.addLayout(self._build_xml_row())

        # ---- Pastas ----
        layout.addWidget(self._build_paths_group())

        # ---- Opções ----
        layout.addWidget(self._build_options_group())

        # ---- Resumo ----
        layout.addWidget(self._build_summary_group())

        # ---- Barra de progresso ----
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Aguardando scan...")
        layout.addWidget(self.progress_bar)

        # ---- Status e perfil ativo ----
        self.status_label = QLabel("Pronto.")
        layout.addWidget(self.status_label)

        self.profile_label = QLabel("Perfil ativo: (nenhum)")
        self.profile_label.setStyleSheet("color: #555; font-style: italic;")
        self.profile_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.profile_label)

        # ---- Árvore ----
        layout.addWidget(self._build_tree())

        # ---- Log ----
        splitter.addWidget(content)
        splitter.addWidget(self._build_log_group())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([650, DEFAULT_LOG_HEIGHT])

        outer.addWidget(splitter)
        self.main_splitter = splitter

    # ========================================================================
    # AÇÕES (COM SELETOR DE PERFIL)
    # ========================================================================

    def _build_actions(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self.btn_generate = QPushButton("Gerar LISTXML filtrado")
        self.btn_generate.setToolTip(
            "Gera o LISTXML contendo somente as máquinas selecionadas pelos filtros."
        )
        self.btn_generate.clicked.connect(self._generate_filtered_xml)

        # ----- Seletor de perfil -----
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(150)
        self.profile_combo.addItem("(usar perfil da aba Filters)", None)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_combo_changed)
        self.profile_combo.setToolTip(
            "Selecione um perfil para filtrar as máquinas. "
            "Se '(usar perfil da aba Filters)' for selecionado, "
            "usará os filtros atuais da guia Filtragem."
        )

        self.btn_scan = QPushButton("Iniciar escaneamento")
        self.btn_scan.setToolTip(
            "Escaneia somente as máquinas e ROMs presentes no XML selecionado."
        )
        self.btn_scan.clicked.connect(self._start_scan)

        self.btn_stop = QPushButton("Parar")
        self.btn_stop.setToolTip("Solicita o cancelamento do escaneamento.")
        self.btn_stop.clicked.connect(self._stop_scan)
        self.btn_stop.setEnabled(False)

        layout.addWidget(self.btn_generate)
        layout.addWidget(QLabel("Perfil:"))
        layout.addWidget(self.profile_combo)
        layout.addWidget(self.btn_scan)
        layout.addWidget(self.btn_stop)
        layout.addStretch()

        return layout

    # ========================================================================
    # PERFIS
    # ========================================================================

    def _load_profiles(self) -> None:
        if not self._filter_service:
            return

        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("(usar perfil da aba Filters)", None)

        profiles = self._filter_service.get_profiles()
        for p in profiles:
            self.profile_combo.addItem(p.name, p.id)

        # Tenta definir o perfil ativo da aba Filters como selecionado
        default_profile = self._filter_service.get_default_profile()
        if default_profile:
            idx = self.profile_combo.findData(default_profile.id)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)

        self.profile_combo.blockSignals(False)
        self._update_profile_label()

    def _on_profile_combo_changed(self, index: int) -> None:
        self._update_profile_label()

    def _update_profile_label(self) -> None:
        idx = self.profile_combo.currentIndex()
        if idx <= 0:
            self.profile_label.setText("Perfil ativo: (usando filtros da aba Filters)")
        else:
            name = self.profile_combo.currentText()
            self.profile_label.setText(f"Perfil ativo: {name}")

    def refresh_profiles(self) -> None:
        self._load_profiles()

    # ========================================================================
    # OBTENÇÃO DOS CRITÉRIOS
    # ========================================================================

    def _get_selected_criteria(self) -> Any:
        selected_id = self.profile_combo.currentData()
        if selected_id is not None and self._filter_service is not None:
            # Busca o perfil pelo ID usando o repositório
            profile = self._filter_service.profile_repo.get_by_id(selected_id)
            if profile:
                return profile.criteria

        # Fallback: usar o critério da guia Filters (se disponível)
        provider = getattr(self.parent_widget, "get_current_filter_criteria", None)
        if callable(provider):
            criteria = provider()
            if criteria is not None:
                return criteria

        from app.core.models.filter_profile import FilterCriteria
        return FilterCriteria()

    # ========================================================================
    # XML ROW
    # ========================================================================

    def _build_xml_row(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.addWidget(QLabel("XML ativo:"))
        self.xml_label = QLabel("Nenhum XML selecionado.")
        self.xml_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.xml_label, stretch=1)

        btn_select = QPushButton("Selecionar XML...")
        btn_select.clicked.connect(self._select_existing_xml)
        layout.addWidget(btn_select)

        btn_open = QPushButton("Abrir pasta")
        btn_open.clicked.connect(self._open_scans_dir)
        layout.addWidget(btn_open)

        return layout

    # ========================================================================
    # PASTAS
    # ========================================================================

    def _build_paths_group(self) -> QGroupBox:
        group = QGroupBox("Origens das ROMs")
        layout = QGridLayout(group)

        self.source_edits: list[QLineEdit] = []
        for index in range(3):
            label = QLabel(f"Origem {index + 1}:")
            edit = QLineEdit()
            button = QPushButton("Escolher")
            button.clicked.connect(lambda checked=False, target=edit: self._choose_directory(target))
            row = QHBoxLayout()
            row.addWidget(edit)
            row.addWidget(button)

            layout.addWidget(label, 0, index)
            layout.addLayout(row, 1, index)
            self.source_edits.append(edit)

        destination_label = QLabel("Destino:")
        self.destination_edit = QLineEdit()
        destination_button = QPushButton("Escolher")
        destination_button.clicked.connect(lambda: self._choose_directory(self.destination_edit))
        destination_row = QHBoxLayout()
        destination_row.addWidget(self.destination_edit)
        destination_row.addWidget(destination_button)

        layout.addWidget(destination_label, 2, 0)
        layout.addLayout(destination_row, 2, 1, 1, 2)

        return group

    # ========================================================================
    # OPÇÕES
    # ========================================================================

    def _build_options_group(self) -> QGroupBox:
        group = QGroupBox("Opções do escaneamento")
        layout = QHBoxLayout(group)

        layout.addWidget(QLabel("Workers:"))
        self.worker_spin = QSpinBox()
        self.worker_spin.setRange(1, max(1, os.cpu_count() or 1))
        self.worker_spin.setValue(DEFAULT_WORKERS)
        self.worker_spin.setToolTip("Quantidade de máquinas processadas simultaneamente.")
        layout.addWidget(self.worker_spin)

        self.alternate_search_checkbox = self._create_checkbox("Busca alternativa")
        self.alternate_search_checkbox.setToolTip(
            "Permite procurar uma ROM pelo nome dentro do diretório da própria máquina."
        )
        layout.addWidget(self.alternate_search_checkbox)

        self.include_chds_checkbox = self._create_checkbox("Verificar CHDs")
        self.include_chds_checkbox.setChecked(True)
        layout.addWidget(self.include_chds_checkbox)

        layout.addStretch()
        return group

    @staticmethod
    def _create_checkbox(text: str):
        from PySide6.QtWidgets import QCheckBox
        return QCheckBox(text)

    # ========================================================================
    # RESUMO
    # ========================================================================

    def _build_summary_group(self) -> QGroupBox:
        group = QGroupBox("Resumo")
        layout = QGridLayout(group)

        self.summary_labels: dict[str, QLabel] = {}
        fields = [
            ("Máquinas", "machines"),
            ("Itens", "total"),
            ("Encontrados", "found"),
            ("Válidos", "valid"),
            ("Ausentes", "missing"),
            ("Inválidos", "bad"),
            ("Erros", "error"),
        ]

        for index, (text, key) in enumerate(fields):
            row = index // 4
            column = (index % 4) * 2
            title = QLabel(text + ":")
            value = QLabel("0")
            value.setMinimumWidth(60)
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            layout.addWidget(title, row, column)
            layout.addWidget(value, row, column + 1)
            self.summary_labels[key] = value

        return group

    # ========================================================================
    # ÁRVORE
    # ========================================================================

    def _build_tree(self) -> QTreeWidget:
        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels([
            "ROM / Máquina",
            "Descrição / Caminho",
            "Tamanho",
            "CRC / SHA1",
            "Status",
        ])
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.itemDoubleClicked.connect(self._on_tree_double_click)
        return self.tree

    # ========================================================================
    # LOG
    # ========================================================================

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
    # CONFIGURAÇÃO
    # ========================================================================

    def _load_paths_from_config(self) -> None:
        source_dirs = getattr(self.config, "source_dirs", []) or []
        for index, edit in enumerate(self.source_edits):
            if index < len(source_dirs):
                edit.setText(str(source_dirs[index]))

        destination = getattr(self.config, "destination_dir", None)
        if destination:
            self.destination_edit.setText(str(destination))

    def _save_paths(self) -> None:
        paths = [
            edit.text().strip()
            for edit in self.source_edits
            if edit.text().strip()
        ]
        try:
            if hasattr(self.config, "source_dirs"):
                self.config.source_dirs = paths
            if hasattr(self.config, "destination_dir"):
                dest = self.destination_edit.text().strip()
                self.config.destination_dir = dest or None
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
    # DIRETÓRIOS
    # ========================================================================

    def _get_rom_paths(self) -> list[Path]:
        paths: list[Path] = []
        for edit in self.source_edits:
            text = edit.text().strip()
            if not text:
                continue
            path = Path(text).expanduser()
            if path.is_dir():
                paths.append(path)
            else:
                logger.warning("Origem de ROM não encontrada: %s", path)
        return paths

    def _scans_dir(self) -> Path:
        configured = getattr(self.config, "scans_dir", None)
        if configured:
            path = Path(configured)
        else:
            destination = _as_path(getattr(self.config, "destination_dir", None))
            if destination:
                path = destination / "scans"
            else:
                path = Path.cwd() / "data" / "scans"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _choose_directory(self, target: QLineEdit) -> None:
        current = target.text().strip()
        initial = current if current else str(Path.home())
        selected = QFileDialog.getExistingDirectory(
            self, "Selecionar diretório", initial
        )
        if selected:
            target.setText(selected)

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
        self.xml_label.setText(str(path))
        self.xml_label.setToolTip(str(path))
        self.xml_label.setStyleSheet("color: green;")
        self.status_label.setText(f"XML ativo ({origin}): {path.name}")
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

        self.btn_generate.setEnabled(False)
        self.status_label.setText("Gerando LISTXML filtrado...")

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
            self.status_label.setText("Erro ao gerar XML.")

        finally:
            self.btn_generate.setEnabled(True)
            self._update_ui_state()

    def _get_mame_version(self) -> str:
        mame_path = _as_path(getattr(self.config, "mame_path", None))
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

        rom_paths = self._get_rom_paths()
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

        self.tree.clear()
        self._reset_summary()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Carregando XML...")
        self.status_label.setText("Carregando XML filtrado...")
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
        self.status_label.setText("Solicitando cancelamento...")
        self.btn_stop.setEnabled(False)

        if self.scanner is not None:
            self.scanner.cancel()

    # ========================================================================
    # EXECUÇÃO DO SCAN
    # ========================================================================

    def _do_scan(self) -> None:
        try:
            xml_path = self.filtered_xml_path
            if xml_path is None or not xml_path.is_file():
                raise FileNotFoundError("LISTXML filtrado não encontrado.")

            self._queue_status("Lendo XML filtrado...")
            machines = self._load_machines_from_xml(xml_path)

            total_items = sum(
                len(machine.get("roms", []))
                + (len(machine.get("disks", [])) if self.include_chds() else 0)
                for machine in machines
            )

            self.progress_total = total_items
            self.total_machines = len(machines)

            self._queue_summary(machines=len(machines), total=total_items)
            self._queue_status(f"Preparado: {len(machines)} máquinas / {total_items} itens.")

            if not machines:
                self._queue_ui(lambda: self._show_no_machines())
                return

            rom_paths = self._get_rom_paths()

            scanner = RomScanner(
                rom_paths=rom_paths,
                max_workers=self.worker_count(),
                progress_callback=self._on_rom_progress,
                machine_callback=self._on_machine_complete,
                log_callback=self._on_scanner_log,
                enable_alternate_search=self.alternate_search_enabled(),
                include_chds=self.include_chds(),
            )

            self.scanner = scanner
            self._queue_status(f"Escaneando 0/{total_items}...")

            results = scanner.scan(machines)
            self.scan_results = results

            self._queue_ui(self._populate_tree)
            self._queue_ui(self._update_summary_from_results)

            cancelled = scanner.cancelled
            self._queue_ui(lambda: self._finish_scan(cancelled=cancelled))

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
                    "size": _as_int(rom_element.get("size", 0)),
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

        status = str(_value(result, "status", "")).lower()
        machine_name = str(_value(result, "machine_name", ""))
        rom_name = str(_value(result, "rom_name", ""))

        self._queue_ui(
            lambda: self._update_progress_ui(current, total, machine_name, rom_name, status)
        )

    def _update_progress_ui(self, current: int, total: int, machine_name: str, rom_name: str, status: str) -> None:
        percentage = int(current * 100 / total) if total > 0 else 0
        self.progress_bar.setValue(percentage)
        self.progress_bar.setFormat(f"{current}/{total} itens — {percentage}%")
        status_text = STATUS_LABELS.get(status, status.upper() if status else "PROCESSANDO")
        self.status_label.setText(
            f"Escaneando {current}/{total}: {machine_name} — {rom_name} [{status_text}]"
        )

    # ========================================================================
    # CALLBACK MÁQUINA
    # ========================================================================

    def _on_machine_complete(self, result: Any) -> None:
        machine_name = str(_value(result, "machine_name", ""))
        total = _as_int(_value(result, "total", 0))
        valid = _as_int(_value(result, "valid", 0))
        missing = _as_int(_value(result, "missing", 0))
        bad = _as_int(_value(result, "bad", 0))

        self._queue_status(
            f"Máquina concluída: {machine_name} — "
            f"{valid}/{total} válidas, {missing} ausentes, {bad} inválidas."
        )

    # ========================================================================
    # LOG
    # ========================================================================

    def _on_scanner_log(self, message: str) -> None:
        logger.info("%s", message)

    # ========================================================================
    # UI THREAD
    # ========================================================================

    def _queue_ui(self, callback) -> None:
        QTimer.singleShot(0, callback)

    def _queue_status(self, text: str) -> None:
        self._queue_ui(lambda: self.status_label.setText(text))

    def _queue_summary(self, *, machines: int, total: int) -> None:
        def update():
            self.summary_labels["machines"].setText(str(machines))
            self.summary_labels["total"].setText(str(total))
        self._queue_ui(update)

    # ========================================================================
    # FINALIZAÇÃO
    # ========================================================================

    def _finish_scan(self, *, cancelled: bool) -> None:
        self.scanning = False
        self.scanner = None
        self._update_summary_from_results()

        if cancelled:
            percentage = int(self.progress_current * 100 / self.progress_total) if self.progress_total > 0 else 0
            self.progress_bar.setValue(percentage)
            self.progress_bar.setFormat(f"{self.progress_current}/{self.progress_total} itens — {percentage}%")
            self.status_label.setText("Escaneamento interrompido.")
        else:
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat(f"{self.progress_total}/{self.progress_total} itens — 100%")
            elapsed = 0.0
            if self.scan_start_time:
                elapsed = time.monotonic() - self.scan_start_time
            self.status_label.setText(f"Escaneamento concluído em {elapsed:.2f}s.")

        self._update_ui_state()

    def _show_no_machines(self) -> None:
        self.scanning = False
        self.scanner = None
        self.status_label.setText("O XML filtrado não possui máquinas.")
        self.progress_bar.setValue(0)
        self._update_ui_state()
        QMessageBox.warning(self, "XML vazio", "O LISTXML selecionado não contém nenhuma máquina.")

    def _show_scan_error(self, error: str) -> None:
        self.scanning = False
        self.scanner = None
        self.status_label.setText(f"Erro: {error}")
        self._update_ui_state()
        QMessageBox.critical(self, "Erro no escaneamento", f"Ocorreu um erro durante o scan:\n\n{error}")

    # ========================================================================
    # RESUMO
    # ========================================================================

    def _reset_summary(self) -> None:
        for label in self.summary_labels.values():
            label.setText("0")

    def _update_summary_from_results(self) -> None:
        machines = len(self.scan_results)
        total = found = valid = missing = bad = error = 0

        for machine in self.scan_results:
            total += _as_int(_value(machine, "total", 0))
            found += _as_int(_value(machine, "found", 0))
            valid += _as_int(_value(machine, "valid", 0))
            missing += _as_int(_value(machine, "missing", 0))
            bad += _as_int(_value(machine, "bad", 0))
            error += _as_int(_value(machine, "error", 0))

        self.summary_labels["machines"].setText(str(machines))
        self.summary_labels["total"].setText(str(total))
        self.summary_labels["found"].setText(str(found))
        self.summary_labels["valid"].setText(str(valid))
        self.summary_labels["missing"].setText(str(missing))
        self.summary_labels["bad"].setText(str(bad))
        self.summary_labels["error"].setText(str(error))

    # ========================================================================
    # ÁRVORE
    # ========================================================================

    def _populate_tree(self) -> None:
        self.tree.clear()
        for machine in self.scan_results:
            self._add_machine_to_tree(machine)

    def _add_machine_to_tree(self, machine: Any) -> None:
        name = str(_value(machine, "machine_name", ""))
        description = ""
        status = self._machine_status(machine)

        item = QTreeWidgetItem(self.tree)
        item.setText(0, f"📁 {name}")
        item.setText(1, description)
        item.setText(2, self._format_machine_size(machine))
        item.setText(3, "-")
        item.setText(4, STATUS_LABELS.get(status, status.upper()))
        self._apply_status_color(item, status)

        for rom in _value(machine, "roms", []):
            self._add_rom_to_tree(item, rom)

    def _add_rom_to_tree(self, parent: QTreeWidgetItem, rom: Any) -> None:
        name = str(_value(rom, "rom_name", ""))
        status = str(_value(rom, "status", "")).lower()
        expected_size = _as_int(_value(rom, "expected_size", 0))
        actual_size = _as_int(_value(rom, "actual_size", 0))
        expected_crc = str(_value(rom, "expected_crc", "") or "")
        actual_crc = str(_value(rom, "actual_crc", "") or "")
        path = _value(rom, "path", None)

        child = QTreeWidgetItem(parent)
        child.setText(0, f"  ├─ {name}")
        child.setText(1, str(path) if path else "")
        child.setText(2, self._format_result_size(expected_size, actual_size, status))
        hash_value = actual_crc or expected_crc or "-"
        child.setText(3, hash_value[:40])
        child.setText(4, STATUS_LABELS.get(status, status.upper() if status else "N/D"))
        self._apply_status_color(child, status)
        child.setToolTip(0, f"Esperado: {expected_crc or '-'}\nEncontrado: {actual_crc or '-'}")
        child.setToolTip(1, str(path) if path else "")

    def _machine_status(self, machine: Any) -> str:
        if _as_int(_value(machine, "error", 0)) > 0:
            return "error"
        if _as_int(_value(machine, "bad", 0)) > 0:
            return "bad"
        if _as_int(_value(machine, "missing", 0)) > 0:
            return "missing"
        if _as_int(_value(machine, "valid", 0)) > 0:
            return "good"
        return "missing"

    def _format_machine_size(self, machine: Any) -> str:
        total = 0
        for rom in _value(machine, "roms", []):
            total += _as_int(_value(rom, "expected_size", 0))
        return _format_size(total)

    @staticmethod
    def _format_result_size(expected: int, actual: int, status: str) -> str:
        if status == "missing":
            return _format_size(expected)
        if actual > 0:
            return f"{_format_size(expected)} / {_format_size(actual)}"
        return _format_size(expected)

    def _apply_status_color(self, item: QTreeWidgetItem, status: str) -> None:
        color = STATUS_COLORS.get(status, "#000000")
        item.setForeground(4, QColor(color))

    def _on_tree_double_click(self, item: QTreeWidgetItem, column: int) -> None:
        details = [
            f"Item: {item.text(0)}",
            f"Descrição/caminho: {item.text(1)}",
            f"Tamanho: {item.text(2)}",
            f"CRC/SHA1: {item.text(3)}",
            f"Status: {item.text(4)}",
        ]
        QMessageBox.information(self, "Detalhes do item", "\n".join(details))

    # ========================================================================
    # OPÇÕES DO SCANNER
    # ========================================================================

    def worker_count(self) -> int:
        return max(1, self.worker_spin.value())

    def alternate_search_enabled(self) -> bool:
        return self.alternate_search_checkbox.isChecked()

    def include_chds(self) -> bool:
        return self.include_chds_checkbox.isChecked()

    # ========================================================================
    # PERFIL ATIVO (mantido para compatibilidade com a MainWindow)
    # ========================================================================

    def set_active_profile_name(self, name: str | None) -> None:
        if name:
            self.profile_label.setText(f"Perfil ativo: {name}")
        else:
            self.profile_label.setText("Perfil ativo: (nenhum)")

    # ========================================================================
    # ESTADO DA INTERFACE
    # ========================================================================

    def _update_ui_state(self) -> None:
        self.btn_generate.setEnabled(not self.scanning)
        self.btn_scan.setEnabled(
            not self.scanning
            and self.filtered_xml_path is not None
            and self.filtered_xml_path.is_file()
        )
        self.btn_stop.setEnabled(self.scanning)
        self.worker_spin.setEnabled(not self.scanning)
        self.alternate_search_checkbox.setEnabled(not self.scanning)
        self.include_chds_checkbox.setEnabled(not self.scanning)
        for edit in self.source_edits:
            edit.setEnabled(not self.scanning)
        self.destination_edit.setEnabled(not self.scanning)

    # ========================================================================
    # DESTRUTOR
    # ========================================================================

    def closeEvent(self, event) -> None:
        if self.scanning and self.scanner is not None:
            self.scanner.cancel()
        event.accept()