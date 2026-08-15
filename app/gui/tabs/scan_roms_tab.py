"""
MAME Set Builder - Aba Scan Roms
================================

Responsável por:

1. Selecionar ou gerar o XML filtrado.
2. Ler EXCLUSIVAMENTE as máquinas/ROMs presentes nesse XML.
3. Escanear as ROMs nas origens configuradas.
4. Exibir progresso por ROM.
5. Registrar todas as ROMs no log, inclusive as válidas.
6. Permitir cancelamento do scan.
7. Exibir os resultados em árvore.
8. Permitir reconstrução dos itens válidos.

IMPORTANTE
----------

O XML filtrado é a fonte de verdade para o scan.

A aba NÃO deve:

- varrer todas as máquinas do banco;
- indexar todos os ZIPs da origem;
- procurar ROMs que não estejam no XML;
- construir um índice global de arquivos antes do scan.

Somente as ROMs presentes no XML filtrado serão verificadas.
"""

from __future__ import annotations

import logging
import threading
import time
import xml.etree.ElementTree as ET

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
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
)

from app.config.app_config import AppConfig

from app.core.models.filter_profile import FilterCriteria

from app.core.models.scan_result import (
    MachineScanResult,
    RomFile,
    ScanResult,
    ScanStatus,
)

from app.core.services.filter_service import FilterService

from app.core.services.listxml_export_service import (
    ListxmlExportService,
)

from app.core.services.reconstruction_service import (
    ReconstructionOptions,
    ReconstructionService,
)

from app.database.database import Database

from app.gui.widgets.log_panel import LogPanel

from app.mame.rom_scanner import (
    RomScanResult,
    RomScanner,
)


logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURAÇÕES DA INTERFACE
# ============================================================================

_LOG_HEIGHT_DEFAULT = 220
_LOG_HEIGHT_MIN = 80
_LOG_HEIGHT_MAX = 900


_STATUS_COLORS = {
    ScanStatus.OK: "#00AA00",
    ScanStatus.FIXABLE: "#FFAA00",
    ScanStatus.MISSING: "#808080",
    ScanStatus.UNAVAILABLE: "#FF0000",
    ScanStatus.CORRUPTED: "#000000",
    ScanStatus.NOT_SCANNED: "#808080",
}


# ============================================================================
# ABA SCAN ROMS
# ============================================================================


class ScanRomsTab(QWidget):
    """
    Aba responsável pelo processo de scan das ROMs.

    O fluxo principal é:

        XML filtrado
             |
             v
        máquinas selecionadas
             |
             v
        ROMs presentes no XML
             |
             v
        RomScanner
             |
             v
        ScanResult
             |
             +--> árvore
             +--> resumo
             +--> reconstrução

    O scanner roda em uma thread para que a interface permaneça responsiva.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.parent = parent

        self.config = AppConfig()

        # Resultado atual do último scan.
        self.scan_result: Optional[ScanResult] = None

        # Estado do processo.
        self.scanning = False

        # XML atualmente selecionado.
        self.filtered_xml_path: Optional[Path] = None

        # Thread do scanner.
        self.scan_thread: Optional[threading.Thread] = None

        # Instância do scanner atualmente em execução.
        self.scanner: Optional[RomScanner] = None

        # Contadores de progresso.
        self._progress_current = 0
        self._progress_total = 0

        # Tempo de início.
        self._scan_start_time: Optional[float] = None

        self._setup_ui()

        self._load_filter_profiles()

        self._update_ui_state()

    # ========================================================================
    # UI
    # ========================================================================

    def _setup_ui(self) -> None:
        """
        Monta toda a interface gráfica da aba.
        """

        outer_layout = QVBoxLayout(self)

        outer_layout.setContentsMargins(
            4,
            4,
            4,
            4,
        )

        outer_layout.setSpacing(4)

        content = QWidget()

        layout = QVBoxLayout(content)

        layout.setContentsMargins(
            4,
            4,
            4,
            4,
        )

        layout.setSpacing(8)

        layout.addLayout(
            self._build_actions_row()
        )

        layout.addLayout(
            self._build_xml_row()
        )

        layout.addWidget(
            self._build_profile_group()
        )

        layout.addWidget(
            self._build_paths_group()
        )

        layout.addWidget(
            self._build_summary_group()
        )

        # --------------------------------------------------------------------
        # BARRA DE PROGRESSO
        # --------------------------------------------------------------------

        self.progress_bar = QProgressBar()

        self.progress_bar.setRange(
            0,
            100,
        )

        self.progress_bar.setValue(0)

        self.progress_bar.setTextVisible(True)

        layout.addWidget(
            self.progress_bar
        )

        # --------------------------------------------------------------------
        # STATUS
        # --------------------------------------------------------------------

        self.status_label = QLabel(
            "Pronto"
        )

        layout.addWidget(
            self.status_label
        )

        # --------------------------------------------------------------------
        # ÁRVORE
        # --------------------------------------------------------------------

        layout.addWidget(
            self._build_tree()
        )

        # --------------------------------------------------------------------
        # SPLITTER
        # --------------------------------------------------------------------

        self.main_splitter = QSplitter(
            Qt.Orientation.Vertical
        )

        self.main_splitter.addWidget(
            content
        )

        self.main_splitter.addWidget(
            self._build_log_group()
        )

        self.main_splitter.setStretchFactor(
            0,
            3,
        )

        self.main_splitter.setStretchFactor(
            1,
            1,
        )

        self.main_splitter.setSizes(
            [
                650,
                _LOG_HEIGHT_DEFAULT,
            ]
        )

        outer_layout.addWidget(
            self.main_splitter
        )

    # ========================================================================
    # AÇÕES
    # ========================================================================

    def _build_actions_row(self) -> QHBoxLayout:
        """
        Cria a linha principal de ações.
        """

        layout = QHBoxLayout()

        # Gerar XML.
        self.btn_generate = QPushButton(
            "Gerar LISTXML filtrado"
        )

        self.btn_generate.setToolTip(
            "Gera um XML contendo somente as máquinas "
            "selecionadas pelo perfil de filtro."
        )

        self.btn_generate.clicked.connect(
            self._generate_filtered_xml
        )

        # Scan.
        self.btn_scan = QPushButton(
            "Iniciar escaneamento"
        )

        self.btn_scan.setToolTip(
            "Escaneia somente as ROMs presentes no XML filtrado."
        )

        self.btn_scan.clicked.connect(
            self._start_scan
        )

        # Parar.
        self.btn_stop = QPushButton(
            "Parar"
        )

        self.btn_stop.setToolTip(
            "Interrompe o escaneamento em andamento."
        )

        self.btn_stop.clicked.connect(
            self._stop_scan
        )

        self.btn_stop.setEnabled(
            False
        )

        layout.addWidget(
            self.btn_generate
        )

        layout.addWidget(
            self.btn_scan
        )

        layout.addWidget(
            self.btn_stop
        )

        layout.addStretch()

        return layout

    # ========================================================================
    # XML
    # ========================================================================

    def _build_xml_row(self) -> QHBoxLayout:
        """
        Cria a área de seleção do XML.
        """

        layout = QHBoxLayout()

        layout.addWidget(
            QLabel("Arquivo:")
        )

        self.xml_label = QLabel(
            "Nenhum arquivo gerado"
        )

        self.xml_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout.addWidget(
            self.xml_label,
            stretch=1,
        )

        btn_select = QPushButton(
            "Selecionar XML existente..."
        )

        btn_select.setToolTip(
            "Seleciona um XML filtrado anteriormente."
        )

        btn_select.clicked.connect(
            self._select_existing_xml
        )

        layout.addWidget(
            btn_select
        )

        btn_open = QPushButton(
            "Abrir pasta de XMLs"
        )

        btn_open.clicked.connect(
            self._open_scans_dir
        )

        layout.addWidget(
            btn_open
        )

        return layout

    # ========================================================================
    # PERFIL
    # ========================================================================

    def _build_profile_group(self) -> QGroupBox:
        """
        Cria o grupo de seleção de perfil.
        """

        group = QGroupBox(
            "PERFIL DE FILTRO PARA O SET"
        )

        layout = QHBoxLayout(
            group
        )

        layout.addWidget(
            QLabel("Perfil:")
        )

        self.profile_combo = QComboBox()

        self.profile_combo.setToolTip(
            "Perfil utilizado para gerar o XML filtrado."
        )

        layout.addWidget(
            self.profile_combo,
            stretch=1,
        )

        btn_refresh = QPushButton(
            "Atualizar perfis"
        )

        btn_refresh.clicked.connect(
            self._load_filter_profiles
        )

        layout.addWidget(
            btn_refresh
        )

        return group

    # ========================================================================
    # PASTAS
    # ========================================================================

    def _build_paths_group(self) -> QGroupBox:
        """
        Cria o grupo de configuração das origens e destino.
        """

        group = QGroupBox(
            "Configurações de Pastas"
        )

        layout = QGridLayout(
            group
        )

        layout.setHorizontalSpacing(
            12
        )

        layout.setVerticalSpacing(
            6
        )

        self.source_edits: List[QLineEdit] = []

        # --------------------------------------------------------------------
        # ORIGENS
        # --------------------------------------------------------------------

        for col in range(3):

            box = QVBoxLayout()

            box.addWidget(
                QLabel(
                    f"Origem {col + 1}:"
                )
            )

            value = ""

            if (
                col
                < len(self.config.source_dirs)
            ):
                value = str(
                    self.config.source_dirs[col]
                )

            edit = QLineEdit(
                value
            )

            row = QHBoxLayout()

            row.addWidget(
                edit
            )

            button = QPushButton(
                "Escolher"
            )

            button.clicked.connect(
                lambda _=False,
                e=edit: self._choose_directory(e)
            )

            row.addWidget(
                button
            )

            box.addLayout(
                row
            )

            layout.addLayout(
                box,
                0,
                col,
            )

            self.source_edits.append(
                edit
            )

        # --------------------------------------------------------------------
        # DESTINO
        # --------------------------------------------------------------------

        destination_row = QHBoxLayout()

        destination_row.addWidget(
            QLabel("Destino:")
        )

        destination_value = ""

        if self.config.destination_dir:
            destination_value = str(
                self.config.destination_dir
            )

        self.destination_edit = QLineEdit(
            destination_value
        )

        destination_row.addWidget(
            self.destination_edit,
            stretch=1,
        )

        destination_button = QPushButton(
            "Escolher"
        )

        destination_button.clicked.connect(
            lambda: self._choose_directory(
                self.destination_edit
            )
        )

        destination_row.addWidget(
            destination_button
        )

        layout.addLayout(
            destination_row,
            1,
            0,
            1,
            3,
        )

        # --------------------------------------------------------------------
        # OPÇÕES
        # --------------------------------------------------------------------

        options = QHBoxLayout()

        options.addWidget(
            QLabel("Organização:")
        )

        self.layout_combo = QComboBox()

        self.layout_combo.addItem(
            "Uma pasta",
            "single",
        )

        self.layout_combo.addItem(
            "Roms / CHD / Devices / Bios",
            "split",
        )

        self.layout_combo.setCurrentIndex(
            1
            if self.config.output_layout == "split"
            else 0
        )

        options.addWidget(
            self.layout_combo,
            stretch=1,
        )

        options.addWidget(
            QLabel("Modo MAME:")
        )

        self.mode_combo = QComboBox()

        self.mode_combo.addItem(
            "Split — pai separado dos clones",
            "split",
        )

        self.mode_combo.addItem(
            "Non-merged — cada jogo completo",
            "non-merged",
        )

        self.mode_combo.addItem(
            "Merged — pai contém os clones",
            "merged",
        )

        options.addWidget(
            self.mode_combo,
            stretch=1,
        )

        layout.addLayout(
            options,
            2,
            0,
            1,
            3,
        )

        # --------------------------------------------------------------------
        # RECONSTRUÇÃO
        # --------------------------------------------------------------------

        self.btn_reconstruct = QPushButton(
            "Reconstruir válidos"
        )

        self.btn_reconstruct.clicked.connect(
            self._reconstruct_validated
        )

        layout.addWidget(
            self.btn_reconstruct,
            3,
            0,
            1,
            3,
        )

        return group

    # ========================================================================
    # RESUMO
    # ========================================================================

    def _build_summary_group(self) -> QGroupBox:
        """
        Cria os indicadores resumidos do scan.
        """

        group = QGroupBox(
            "RESUMO"
        )

        layout = QGridLayout(
            group
        )

        self.summary_labels = {}

        categories = [
            ("ROMs", "roms_total"),
            ("BIOS", "bios_total"),
            ("DEVICES", "devices_total"),
            ("CHDs", "chds_total"),
            ("🟢 OK", "ok_count"),
            ("🟡 Corrigíveis", "fixable_count"),
            ("🔴 Ausentes", "missing_count"),
            ("⬛ Corrompidos", "corrupted_count"),
        ]

        for index, (
            label,
            key,
        ) in enumerate(categories):

            row, col = divmod(
                index,
                4,
            )

            layout.addWidget(
                QLabel(
                    f"{label}:"
                ),
                row,
                col * 2,
            )

            value = QLabel(
                "0"
            )

            value.setStyleSheet(
                "font-weight: bold;"
            )

            self.summary_labels[
                key
            ] = value

            layout.addWidget(
                value,
                row,
                col * 2 + 1,
            )

        return group

    # ========================================================================
    # ÁRVORE
    # ========================================================================

    def _build_tree(self) -> QTreeWidget:
        """
        Cria a árvore dos resultados.
        """

        self.tree = QTreeWidget()

        self.tree.setHeaderLabels(
            [
                "ROM",
                "Jogo",
                "Tamanho",
                "CRC",
                "Status",
            ]
        )

        self.tree.setColumnWidth(
            0,
            260,
        )

        self.tree.setColumnWidth(
            1,
            260,
        )

        self.tree.setColumnWidth(
            2,
            110,
        )

        self.tree.setColumnWidth(
            3,
            120,
        )

        self.tree.setColumnWidth(
            4,
            120,
        )

        self.tree.itemDoubleClicked.connect(
            self._on_tree_double_click
        )

        return self.tree

    # ========================================================================
    # LOG
    # ========================================================================

    def _build_log_group(self) -> QWidget:
        """
        Cria o painel de log.
        """

        container = QWidget()

        layout = QVBoxLayout(
            container
        )

        layout.setContentsMargins(
            0,
            4,
            0,
            0,
        )

        toolbar = QHBoxLayout()

        toolbar.addWidget(
            QLabel(
                "Altura do log (px):"
            )
        )

        self.log_height_spin = QSpinBox()

        self.log_height_spin.setRange(
            _LOG_HEIGHT_MIN,
            _LOG_HEIGHT_MAX,
        )

        self.log_height_spin.setSingleStep(
            20
        )

        self.log_height_spin.setValue(
            _LOG_HEIGHT_DEFAULT
        )

        self.log_height_spin.valueChanged.connect(
            self._on_log_height_changed
        )

        toolbar.addWidget(
            self.log_height_spin
        )

        toolbar.addStretch()

        layout.addLayout(
            toolbar
        )

        self.log_panel = LogPanel(
            self,
            logger_name="",
        )

        layout.addWidget(
            self.log_panel
        )

        return container

    def _on_log_height_changed(
        self,
        value: int,
    ) -> None:
        """
        Ajusta a altura do painel de log.
        """

        total = self.main_splitter.height()

        if total <= 0:
            total = 650 + value

        top = max(
            150,
            total - value,
        )

        self.main_splitter.setSizes(
            [
                top,
                value,
            ]
        )

    # ========================================================================
    # DATABASE
    # ========================================================================

    def _get_db_connection(self):
        """
        Obtém a conexão principal ou abre uma conexão independente.
        """

        main_db = getattr(
            self.parent,
            "db",
            None,
        )

        if (
            main_db is not None
            and getattr(
                main_db,
                "conn",
                None,
            ) is not None
        ):
            return (
                main_db.conn,
                False,
            )

        db = Database(
            self.config.db_path
        )

        db.connect()

        return (
            db.conn,
            True,
        )

    # ========================================================================
    # PERFIS
    # ========================================================================

    def _load_filter_profiles(self) -> None:
        """
        Carrega os perfis disponíveis no banco.
        """

        current_id = None

        if hasattr(
            self,
            "profile_combo",
        ):
            current_id = (
                self.profile_combo.currentData()
            )

        self.profile_combo.blockSignals(
            True
        )

        self.profile_combo.clear()

        self.profile_combo.addItem(
            "Todas as máquinas (sem filtro)",
            None,
        )

        conn, owns = (
            self._get_db_connection()
        )

        try:

            service = FilterService(
                conn
            )

            profiles = service.get_profiles()

            for profile in profiles:

                self.profile_combo.addItem(
                    profile.name,
                    profile.id,
                )

            target_id = current_id

            if target_id is None:

                default = (
                    service.get_default_profile()
                )

                if default:
                    target_id = default.id

            if target_id is not None:

                index = (
                    self.profile_combo.findData(
                        target_id
                    )
                )

                if index >= 0:
                    self.profile_combo.setCurrentIndex(
                        index
                    )

        except Exception as exc:

            logger.warning(
                "Não foi possível carregar perfis: %s",
                exc,
            )

        finally:

            self.profile_combo.blockSignals(
                False
            )

            if owns:
                conn.close()

    def _get_selected_criteria(
        self,
    ) -> FilterCriteria:
        """
        Obtém os critérios do perfil selecionado.
        """

        profile_id = (
            self.profile_combo.currentData()
        )

        if not profile_id:
            return FilterCriteria()

        conn, owns = (
            self._get_db_connection()
        )

        try:

            service = FilterService(
                conn
            )

            profile = next(
                (
                    profile
                    for profile
                    in service.get_profiles()
                    if profile.id == profile_id
                ),
                None,
            )

            if profile:
                return profile.criteria

            return FilterCriteria()

        finally:

            if owns:
                conn.close()

    # ========================================================================
    # ESTADO
    # ========================================================================

    def _update_ui_state(self) -> None:
        """
        Atualiza o estado dos controles.
        """

        has_xml = (
            self.filtered_xml_path is not None
            and self.filtered_xml_path.exists()
        )

        self.btn_scan.setEnabled(
            has_xml
            and not self.scanning
        )

        self.btn_stop.setEnabled(
            self.scanning
        )

        self.btn_generate.setEnabled(
            not self.scanning
        )

        self.profile_combo.setEnabled(
            not self.scanning
        )

        self.btn_reconstruct.setEnabled(
            bool(self.scan_result)
            and not self.scanning
        )

    update_ui_state = _update_ui_state

    # ========================================================================
    # PASTAS
    # ========================================================================

    def _choose_directory(
        self,
        edit: QLineEdit,
    ) -> None:
        """
        Abre o seletor de diretórios.
        """

        selected = (
            QFileDialog.getExistingDirectory(
                self,
                "Escolher diretório",
            )
        )

        if selected:

            edit.setText(
                selected
            )

            self._save_paths()

    def _save_paths(self) -> None:
        """
        Salva as origens e destino no AppConfig.
        """

        self.config.source_dirs = [
            Path(edit.text())
            for edit in self.source_edits
            if edit.text().strip()
        ][:3]

        self.config.destination_dir = (
            Path(
                self.destination_edit.text()
            )
            if self.destination_edit.text().strip()
            else None
        )

        self.config.output_layout = (
            self.layout_combo.currentData()
        )

        self.config.save()

    def _get_rom_paths(self) -> List[Path]:
        """
        Retorna somente origens válidas configuradas.
        """

        return [
            Path(edit.text())
            for edit in self.source_edits
            if (
                edit.text().strip()
                and Path(
                    edit.text()
                ).is_dir()
            )
        ][:3]

    # ========================================================================
    # XML
    # ========================================================================

    def _scans_dir(self) -> Path:
        """
        Retorna o diretório dos XMLs de scan.
        """

        directory = Path(
            "data/scans"
        )

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        return directory

    def _open_scans_dir(self) -> None:
        """
        Abre o diretório dos XMLs no sistema operacional.
        """

        import os
        import sys

        directory = self._scans_dir()

        try:

            if sys.platform == "win32":

                os.startfile(
                    str(directory)
                )

            elif sys.platform == "darwin":

                os.system(
                    f'open "{directory}"'
                )

            else:

                os.system(
                    f'xdg-open "{directory}"'
                )

        except Exception as exc:

            logger.warning(
                "Não foi possível abrir pasta de scans: %s",
                exc,
            )

            QMessageBox.information(
                self,
                "Pasta de XMLs",
                f"Local:\n{directory}",
            )

    def _select_existing_xml(self) -> None:
        """
        Permite selecionar um XML filtrado existente.
        """

        directory = self._scans_dir()

        file_path, _ = (
            QFileDialog.getOpenFileName(
                self,
                "Selecionar XML filtrado para escanear",
                str(directory),
                "Arquivos XML (*.xml);;Todos os arquivos (*)",
            )
        )

        if not file_path:
            return

        path = Path(
            file_path
        )

        if not path.exists():

            QMessageBox.warning(
                self,
                "Erro",
                "Arquivo selecionado não encontrado.",
            )

            return

        self._set_active_xml(
            path,
            origin="selecionado manualmente",
        )

    def _set_active_xml(
        self,
        xml_path: Path,
        *,
        origin: str,
    ) -> None:
        """
        Define o XML ativo.
        """

        self.filtered_xml_path = (
            xml_path
        )

        self.xml_label.setText(
            str(xml_path)
        )

        self.xml_label.setStyleSheet(
            "color: green;"
        )

        self.status_label.setText(
            f"XML ativo ({origin}): "
            f"{xml_path.name}"
        )

        logger.info(
            "XML ativo para scan (%s): %s",
            origin,
            xml_path,
        )

        self._update_ui_state()

    # ========================================================================
    # GERAÇÃO DO XML
    # ========================================================================

    def _generate_filtered_xml(self) -> None:
        """
        Gera o XML filtrado utilizando o serviço atual do projeto.
        """

        self.status_label.setText(
            "Gerando XML filtrado..."
        )

        self.btn_generate.setEnabled(
            False
        )

        try:

            service = ListxmlExportService(
                self.config.db_path,
                self.config.mame_path,
            )

            criteria = (
                self._get_selected_criteria()
            )

            machine_ids = (
                service.get_machine_ids_from_db(
                    criteria
                )
            )

            if not machine_ids:

                QMessageBox.warning(
                    self,
                    "Aviso",
                    "Nenhuma máquina encontrada com os filtros atuais.",
                )

                return

            logger.info(
                "%d máquina(s) selecionada(s) "
                "para o XML filtrado.",
                len(machine_ids),
            )

            version = (
                self._get_mame_version()
            )

            timestamp = datetime.now().strftime(
                "%Y%m%d_%H%M%S"
            )

            filename = (
                f"mame_{version}"
                f"_filtered_{timestamp}.xml"
            )

            output_path = (
                self._scans_dir()
                / filename
            )

            service.generate_filtered_xml(
                machine_ids,
                output_path,
            )

            self._set_active_xml(
                output_path,
                origin="recém-gerado",
            )

            QMessageBox.information(
                self,
                "Sucesso",
                f"XML filtrado gerado em:\n"
                f"{output_path}\n\n"
                f"{len(machine_ids)} máquina(s) selecionada(s).",
            )

        except Exception as exc:

            logger.exception(
                "Falha ao gerar XML filtrado."
            )

            QMessageBox.critical(
                self,
                "Erro",
                f"Erro ao gerar XML:\n{exc}",
            )

        finally:

            self.btn_generate.setEnabled(
                True
            )

            self._update_ui_state()

    def _get_mame_version(self) -> str:
        """
        Obtém a versão do MAME pelo executável configurado.
        """

        try:

            import re
            import subprocess

            if (
                self.config.mame_path
                and self.config.mame_path.exists()
            ):

                result = subprocess.run(
                    [
                        str(
                            self.config.mame_path
                        ),
                        "-help",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                first_line = (
                    result.stdout
                    .strip()
                    .split("\n")[0]
                )

                match = re.search(
                    r"v?(\d+\.\d+)",
                    first_line,
                )

                if match:
                    return match.group(1)

        except Exception:
            logger.debug(
                "Não foi possível detectar versão do MAME.",
                exc_info=True,
            )

        return "0.289"

    # ========================================================================
    # INÍCIO DO SCAN
    # ========================================================================

    def _start_scan(self) -> None:
        """
        Inicia o scan em uma thread separada.
        """

        if (
            not self.filtered_xml_path
            or not self.filtered_xml_path.exists()
        ):

            QMessageBox.critical(
                self,
                "Erro",
                "Nenhum XML filtrado disponível.",
            )

            return

        if self.scanning:
            return

        # --------------------------------------------------------------------
        # RESET
        # --------------------------------------------------------------------

        self.scanning = True

        self.scan_result = None

        self.scanner = None

        self._progress_current = 0

        self._progress_total = 0

        self._scan_start_time = time.monotonic()

        self.tree.clear()

        self.progress_bar.setValue(
            0
        )

        self.progress_bar.setFormat(
            "Preparando scan..."
        )

        self.status_label.setText(
            "Carregando XML filtrado..."
        )

        self._update_ui_state()

        # --------------------------------------------------------------------
        # THREAD
        # --------------------------------------------------------------------

        self.scan_thread = threading.Thread(
            target=self._do_scan,
            name="mame-rom-scan",
            daemon=True,
        )

        self.scan_thread.start()

    # ========================================================================
    # PARAR
    # ========================================================================

    def _stop_scan(self) -> None:
        """
        Solicita o cancelamento do scanner.

        O scanner faz cancelamento cooperativo.
        """

        if not self.scanning:
            return

        logger.info(
            "Solicitado cancelamento do scan pelo usuário."
        )

        self.status_label.setText(
            "Parando scan..."
        )

        self.btn_stop.setEnabled(
            False
        )

        if self.scanner:

            self.scanner.cancel()

    # ========================================================================
    # EXECUÇÃO DO SCAN
    # ========================================================================

    def _do_scan(self) -> None:
        """
        Executa o scan fora da thread principal.

        O XML é carregado primeiro.

        Depois:

            XML
             |
             +--> máquinas
                    |
                    +--> ROMs
                           |
                           v
                       RomScanner

        Nenhuma ROM fora do XML é enviada ao scanner.
        """

        try:

            xml_path = (
                self.filtered_xml_path
            )

            if (
                xml_path is None
                or not xml_path.exists()
            ):
                raise FileNotFoundError(
                    "XML filtrado não encontrado."
                )

            logger.info(
                "============================================================"
            )

            logger.info(
                "Iniciando scan do XML filtrado:"
            )

            logger.info(
                "%s",
                xml_path,
            )

            # ----------------------------------------------------------------
            # CARREGA XML
            # ----------------------------------------------------------------

            machines = (
                self._load_machines_from_xml(
                    xml_path
                )
            )

            # ----------------------------------------------------------------
            # CONTAGEM REAL DE ROMS
            # ----------------------------------------------------------------

            total_machines = len(
                machines
            )

            total_roms = sum(
                len(
                    machine.get(
                        "roms",
                        [],
                    )
                )
                for machine in machines
            )

            self._progress_total = (
                total_roms
            )

            logger.info(
                "Máquinas no XML filtrado: %d",
                total_machines,
            )

            logger.info(
                "ROMs no XML filtrado: %d",
                total_roms,
            )

            # ----------------------------------------------------------------
            # LOG INDICATIVO
            # ----------------------------------------------------------------

            logger.info(
                "Somente as %d ROM(s) presentes no XML "
                "serão verificadas.",
                total_roms,
            )

            # ----------------------------------------------------------------
            # ORIGENS
            # ----------------------------------------------------------------

            self._save_paths()

            rom_paths = (
                self._get_rom_paths()
            )

            logger.info(
                "Origens configuradas:"
            )

            for path in rom_paths:

                logger.info(
                    "  - %s",
                    path,
                )

            if not rom_paths:

                logger.warning(
                    "Nenhuma origem válida configurada."
                )

            # ----------------------------------------------------------------
            # SCANNER
            # ----------------------------------------------------------------

            scanner = RomScanner(
                rom_paths=rom_paths,
                max_workers=1,
                progress_callback=self._on_rom_progress,
                log_callback=self._on_scanner_log,
                enable_alternate_search=False,
            )

            self.scanner = scanner

            # ----------------------------------------------------------------
            # RESULTADO
            # ----------------------------------------------------------------

            self._queue_status(
                f"Escaneando 0/{total_roms} ROMs..."
            )

            scan_results = scanner.scan(
                machines
            )

            # ----------------------------------------------------------------
            # CONVERTE RESULTADOS
            # ----------------------------------------------------------------

            converted = (
                self._convert_scan_results(
                    scan_results
                )
            )

            self.scan_result = converted

            # ----------------------------------------------------------------
            # ÁRVORE
            # ----------------------------------------------------------------

            self._queue_ui(
                self._populate_tree
            )

            # ----------------------------------------------------------------
            # FINALIZAÇÃO
            # ----------------------------------------------------------------

            elapsed = 0.0

            if self._scan_start_time:
                elapsed = (
                    time.monotonic()
                    - self._scan_start_time
                )

            logger.info(
                "Scan finalizado em %.2f segundos.",
                elapsed,
            )

            self._queue_ui(
                lambda: self._finish_scan(
                    cancelled=scanner.cancelled
                )
            )

        except Exception as exc:

            logger.exception(
                "Falha geral durante o scan."
            )

            self._queue_ui(
                lambda: self._show_scan_error(
                    str(exc)
                )
            )

    # ========================================================================
    # CALLBACK DE PROGRESSO
    # ========================================================================

    def _on_rom_progress(
        self,
        current: int,
        total: int,
        result: RomScanResult,
    ) -> None:
        """
        Recebe o progresso de cada ROM processada.

        Este callback é executado pelo scanner.

        A GUI é atualizada através de QTimer para evitar acesso direto aos
        widgets a partir da thread de trabalho.
        """

        self._progress_current = current

        self._progress_total = total

        if total > 0:

            percentage = int(
                current * 100 / total
            )

        else:

            percentage = 100

        status_text = {
            "good": "OK",
            "bad": "RUIM",
            "missing": "AUSENTE",
            "error": "ERRO",
            "cancelled": "CANCELADA",
        }.get(
            result.status,
            result.status.upper(),
        )

        self._queue_ui(
            lambda: self._update_progress_ui(
                current,
                total,
                percentage,
                result,
                status_text,
            )
        )

    def _update_progress_ui(
        self,
        current: int,
        total: int,
        percentage: int,
        result: RomScanResult,
        status_text: str,
    ) -> None:
        """
        Atualiza visualmente a barra de progresso e o status.
        """

        self.progress_bar.setValue(
            percentage
        )

        self.progress_bar.setFormat(
            f"{current}/{total} ROMs — {percentage}%"
        )

        self.status_label.setText(
            f"Escaneando "
            f"{current}/{total}: "
            f"{result.machine_name} — "
            f"{result.rom_name} "
            f"[{status_text}]"
        )

    # ========================================================================
    # LOG DO SCANNER
    # ========================================================================

    def _on_scanner_log(
        self,
        message: str,
    ) -> None:
        """
        Recebe mensagens do RomScanner.

        O logger principal já captura essas mensagens através do LogPanel,
        portanto este callback existe principalmente para integração futura
        e para garantir que o fluxo possa ser observado pela GUI.
        """

        logger.info(
            "%s",
            message,
        )

    # ========================================================================
    # UI THREAD
    # ========================================================================

    def _queue_ui(
        self,
        callback,
    ) -> None:
        """
        Agenda uma função para execução na thread principal do Qt.
        """

        QTimer.singleShot(
            0,
            callback,
        )

    def _queue_status(
        self,
        text: str,
    ) -> None:
        """
        Agenda uma alteração do status.
        """

        self._queue_ui(
            lambda: self.status_label.setText(
                text
            )
        )

    # ========================================================================
    # FINALIZAÇÃO
    # ========================================================================

    def _finish_scan(
        self,
        *,
        cancelled: bool = False,
    ) -> None:
        """
        Finaliza o scan e atualiza os indicadores.
        """

        self.scanning = False

        self._update_summary_labels()

        self._update_ui_state()

        if cancelled:

            percentage = 0

            if self._progress_total:
                percentage = int(
                    self._progress_current
                    * 100
                    / self._progress_total
                )

            self.progress_bar.setValue(
                percentage
            )

            self.progress_bar.setFormat(
                f"{self._progress_current}/"
                f"{self._progress_total} ROMs — "
                f"{percentage}%"
            )

            self.status_label.setText(
                "Escaneamento interrompido."
            )

            logger.info(
                "Scan interrompido pelo usuário: "
                "%d/%d ROMs processadas.",
                self._progress_current,
                self._progress_total,
            )

        else:

            self.progress_bar.setValue(
                100
            )

            self.progress_bar.setFormat(
                f"{self._progress_total}/"
                f"{self._progress_total} ROMs — 100%"
            )

            self.status_label.setText(
                "Escaneamento concluído."
            )

        self.scanner = None

    def _show_scan_error(
        self,
        error: str,
    ) -> None:
        """
        Trata uma falha geral do processo de scan.
        """

        self.scanning = False

        self.scanner = None

        self._update_ui_state()

        self.status_label.setText(
            f"Erro: {error}"
        )

        QMessageBox.critical(
            self,
            "Erro",
            f"Erro durante o escaneamento:\n{error}",
        )

    # ========================================================================
    # CONVERSÃO DOS RESULTADOS
    # ========================================================================

    def _convert_scan_results(
        self,
        machine_results,
    ) -> ScanResult:
        """
        Converte os resultados do novo RomScanner para o modelo
        ScanResult utilizado pelo restante da aplicação.

        Isso mantém a compatibilidade com ReconstructionService e com
        os componentes existentes da GUI.
        """

        result = ScanResult(
            version=self._get_mame_version()
        )

        for machine_result in machine_results:

            converted_machine = MachineScanResult(
                name=machine_result.machine_name,
                description="",
                cloneof=None,
            )

            for rom_result in machine_result.roms:

                status = (
                    self._convert_rom_status(
                        rom_result.status
                    )
                )

                rom = RomFile(
                    name=rom_result.rom_name,
                    size=rom_result.expected_size,
                    crc=(
                        rom_result.expected_crc
                        or ""
                    ).lower(),
                    status=status,
                    found_in=rom_result.source,
                    found_member=(
                        rom_result.rom_name
                        if rom_result.source
                        and rom_result.source.suffix.lower()
                        == ".zip"
                        else None
                    ),
                    actual_size=(
                        rom_result.actual_size
                        if rom_result.found
                        else None
                    ),
                    actual_crc=(
                        rom_result.actual_crc
                        if rom_result.found
                        else None
                    ),
                )

                converted_machine.roms.append(
                    rom
                )

            converted_machine.total_size = sum(
                rom.size
                for rom in converted_machine.roms
                if rom.status == ScanStatus.OK
            )

            converted_machine.update_status()

            result.machines.append(
                converted_machine
            )

        result.total_machines = len(
            result.machines
        )

        result.update_summary()

        return result

    @staticmethod
    def _convert_rom_status(
        status: str,
    ) -> ScanStatus:
        """
        Converte o status textual do novo scanner para ScanStatus.
        """

        mapping = {
            "good": ScanStatus.OK,
            "bad": ScanStatus.CORRUPTED,
            "missing": ScanStatus.MISSING,
            "error": ScanStatus.CORRUPTED,
            "cancelled": ScanStatus.NOT_SCANNED,
        }

        return mapping.get(
            status,
            ScanStatus.NOT_SCANNED,
        )

    # ========================================================================
    # RESUMO
    # ========================================================================

    def _update_summary_labels(self) -> None:
        """
        Atualiza os indicadores do resumo.
        """

        if not self.scan_result:
            return

        result = self.scan_result

        self.summary_labels[
            "roms_total"
        ].setText(
            str(
                result.roms_total
            )
        )

        self.summary_labels[
            "bios_total"
        ].setText(
            str(
                result.bios_total
            )
        )

        self.summary_labels[
            "devices_total"
        ].setText(
            str(
                result.devices_total
            )
        )

        self.summary_labels[
            "chds_total"
        ].setText(
            str(
                result.chds_total
            )
        )

        self.summary_labels[
            "ok_count"
        ].setText(
            str(
                result.ok_count
            )
        )

        self.summary_labels[
            "fixable_count"
        ].setText(
            str(
                result.fixable_count
            )
        )

        self.summary_labels[
            "missing_count"
        ].setText(
            str(
                result.missing_count
                + result.unavailable_count
            )
        )

        self.summary_labels[
            "corrupted_count"
        ].setText(
            str(
                result.corrupted_count
            )
        )

    # ========================================================================
    # ÁRVORE
    # ========================================================================

    def _populate_tree(self) -> None:
        """
        Recria a árvore completa a partir do resultado do scan.
        """

        self.tree.clear()

        if not self.scan_result:
            return

        for machine in self.scan_result.machines:

            self._add_machine_to_tree(
                machine
            )

    def _add_machine_to_tree(
        self,
        machine_result: MachineScanResult,
    ) -> None:
        """
        Adiciona uma máquina e suas ROMs à árvore.
        """

        icon = (
            "📦"
            if machine_result.cloneof
            else "📁"
        )

        item = QTreeWidgetItem(
            self.tree
        )

        item.setText(
            0,
            f"{icon} {machine_result.name}",
        )

        item.setText(
            1,
            machine_result.description[:80],
        )

        item.setText(
            2,
            self._format_size(
                machine_result.total_size
            ),
        )

        item.setText(
            3,
            "-",
        )

        item.setText(
            4,
            machine_result.status.label,
        )

        self._apply_status_color(
            item,
            machine_result.status,
        )

        for rom in machine_result.roms:

            child = QTreeWidgetItem(
                item
            )

            child.setText(
                0,
                f"  ├─ {rom.name}",
            )

            child.setText(
                1,
                "",
            )

            child.setText(
                2,
                self._format_size(
                    rom.size
                ),
            )

            child.setText(
                3,
                (
                    rom.crc[:8]
                    if rom.crc
                    else "-"
                ),
            )

            child.setText(
                4,
                rom.status.label,
            )

            self._apply_status_color(
                child,
                rom.status,
            )

    def _apply_status_color(
        self,
        item: QTreeWidgetItem,
        status: ScanStatus,
    ) -> None:
        """
        Aplica a cor correspondente ao status.
        """

        color = _STATUS_COLORS.get(
            status,
            "#000000",
        )

        item.setForeground(
            4,
            color,
        )

    def _on_tree_double_click(
        self,
        item: QTreeWidgetItem,
        column: int,
    ) -> None:
        """
        Exibe informações básicas do item selecionado.
        """

        QMessageBox.information(
            self,
            "Detalhes",
            (
                f"Item: {item.text(0)}\n"
                f"Status: {item.text(4)}\n"
                f"Tamanho: {item.text(2)}\n"
                f"CRC: {item.text(3)}"
            ),
        )

    # ========================================================================
    # LEITURA DO XML
    # ========================================================================

    def _load_machines_from_xml(
        self,
        xml_path: Path,
    ) -> List[dict]:
        """
        Carrega as máquinas e ROMs diretamente do XML filtrado.

        IMPORTANTE:

        Nenhuma consulta ao banco é realizada aqui.

        Isso garante que o conjunto efetivamente escaneado seja exatamente
        aquele representado pelo XML selecionado.
        """

        machines: List[dict] = []

        logger.info(
            "Lendo XML filtrado: %s",
            xml_path,
        )

        tree = ET.parse(
            xml_path
        )

        root = tree.getroot()

        machine_elements = (
            root.findall(
                "machine"
            )
        )

        logger.info(
            "XML contém %d máquina(s).",
            len(machine_elements),
        )

        for machine_element in machine_elements:

            machine_name = (
                machine_element.get(
                    "name",
                    "",
                )
            )

            description_element = (
                machine_element.find(
                    "description"
                )
            )

            description = ""

            if (
                description_element
                is not None
            ):
                description = (
                    description_element.text
                    or ""
                )
            machine = {
                "name": machine_name,
                "description": description,
                "cloneof": (
                    machine_element.get(
                        "cloneof",
                        "",
                    )
                ),
                "roms": [],
                "disks": [],
            }

            # ---------------------------------------------------------------
            # ROMS
            # ---------------------------------------------------------------

            for rom_element in machine_element.findall(
                "rom"
            ):

                size_text = (
                    rom_element.get(
                        "size",
                        "0",
                    )
                )

                try:

                    size = int(
                        size_text
                        or 0
                    )

                except (
                    ValueError,
                    TypeError,
                ):

                    logger.warning(
                        "ROM '%s' da máquina '%s' "
                        "possui tamanho inválido: %r",
                        rom_element.get(
                            "name",
                            "?",
                        ),
                        machine_name,
                        size_text,
                    )

                    size = 0

                rom = {
                    "name": (
                        rom_element.get(
                            "name",
                            "",
                        )
                    ),
                    "size": size,
                    "crc": (
                        rom_element.get(
                            "crc",
                            "",
                        )
                    ),
                    "sha1": (
                        rom_element.get(
                            "sha1",
                            "",
                        )
                    ),
                    "merge": (
                        rom_element.get(
                            "merge",
                            "",
                        )
                    ),
                }

                machine[
                    "roms"
                ].append(
                    rom
                )

            # ---------------------------------------------------------------
            # DISKS
            # ---------------------------------------------------------------

            for disk_element in machine_element.findall(
                "disk"
            ):

                machine[
                    "disks"
                ].append(
                    {
                        "name": (
                            disk_element.get(
                                "name",
                                "",
                            )
                        ),
                        "sha1": (
                            disk_element.get(
                                "sha1",
                                "",
                            )
                        ),
                        "merge": (
                            disk_element.get(
                                "merge",
                                "",
                            )
                        ),
                    }
                )

            machines.append(
                machine
            )

        logger.info(
            "XML carregado: %d máquina(s), %d ROM(s).",
            len(machines),
            sum(
                len(
                    machine["roms"]
                )
                for machine in machines
            ),
        )

        return machines

    # ========================================================================
    # RECONSTRUÇÃO
    # ========================================================================

    def _reconstruct_validated(self) -> None:
        """
        Reconstrói os itens válidos usando o serviço de reconstrução existente.
        """

        if not self.scan_result:
            return

        self._save_paths()

        if not self.config.destination_dir:

            QMessageBox.warning(
                self,
                "Destino ausente",
                "Escolha o diretório de destino antes de reconstruir.",
            )

            return

        try:

            service = ReconstructionService(
                ReconstructionOptions(
                    destination=(
                        self.config.destination_dir
                    ),
                    layout=(
                        self.config.output_layout
                    ),
                    mode=(
                        self.mode_combo.currentData()
                    ),
                )
            )

            manifest = service.reconstruct(
                self.scan_result
            )

            logger.info(
                "Reconstrução concluída. Manifesto: %s",
                manifest,
            )

            QMessageBox.information(
                self,
                "Reconstrução",
                (
                    "Reconstrução concluída.\n\n"
                    f"Manifesto salvo em:\n{manifest}"
                ),
            )

        except Exception as exc:

            logger.exception(
                "Falha durante reconstrução."
            )

            QMessageBox.critical(
                self,
                "Reconstrução",
                str(exc),
            )

    # ========================================================================
    # HELPERS
    # ========================================================================

    @staticmethod
    def _format_size(
        size: int,
    ) -> str:
        """
        Formata um tamanho em bytes para uma unidade legível.
        """

        if size < 1024:

            return f"{size} B"

        if size < 1024 * 1024:

            return (
                f"{size / 1024:.1f} KB"
            )

        if size < 1024 * 1024 * 1024:

            return (
                f"{size / (1024 * 1024):.1f} MB"
            )

        return (
            f"{size / (1024 * 1024 * 1024):.2f} GB"
        )