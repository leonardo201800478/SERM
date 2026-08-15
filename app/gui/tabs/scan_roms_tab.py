"""Aba de escaneamento e reconstrução de ROMs.

Fluxo típico:
    1. Gerar (ou selecionar) um LISTXML filtrado, de acordo com um
       Perfil de Filtro configurado na aba Filtragem.
    2. Escanear as origens configuradas em busca das ROMs/CHDs
       necessários, comparando CRC/SHA1/tamanho.
    3. Revisar o resumo e a árvore de resultados.
    4. Reconstruir (copiar) os itens válidos para o destino, no modo
       Split/Non-Merged/Merged escolhido.

O scan roda em thread separada e NUNCA para no primeiro erro: qualquer
falha isolada (uma ROM corrompida, uma máquina com XML inconsistente
etc.) é registrada no log e tratada como ``ScanStatus.CORRUPTED`` —
o scan sempre prossegue até o fim, relatando os problemas encontrados.
"""

import logging
import threading
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
from app.core.models.scan_result import MachineScanResult, ScanResult, ScanStatus
from app.core.services.filter_service import FilterService
from app.core.services.listxml_export_service import ListxmlExportService
from app.core.services.reconstruction_service import ReconstructionOptions, ReconstructionService
from app.database.database import Database
from app.gui.widgets.log_panel import LogPanel
from app.mame.rom_scanner import RomScanner

logger = logging.getLogger(__name__)

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


class ScanRomsTab(QWidget):
    """Aba responsável por gerar XML filtrado, escanear e reconstruir sets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.config = AppConfig()

        self.scan_result: Optional[ScanResult] = None
        self.scanning = False
        self.filtered_xml_path: Optional[Path] = None
        self.scan_thread: Optional[threading.Thread] = None

        self._setup_ui()
        self._load_filter_profiles()
        self._update_ui_state()

    # ========================================================================
    # UI SETUP
    # ========================================================================

    def _setup_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(4, 4, 4, 4)
        outer_layout.setSpacing(4)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        layout.addLayout(self._build_actions_row())
        layout.addLayout(self._build_xml_row())
        layout.addWidget(self._build_profile_group())
        layout.addWidget(self._build_paths_group())
        layout.addWidget(self._build_summary_group())

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Pronto")
        layout.addWidget(self.status_label)

        layout.addWidget(self._build_tree())

        # ============================
        # SPLITTER: conteúdo + log
        # ============================
        # IMPORTANTE: o painel de log NÃO tem altura mínima/máxima fixa
        # aqui — isso é o que travava o redimensionamento por arraste do
        # splitter nesta aba (funcionava na aba Filtragem justamente por
        # não haver essa trava). O QSpinBox abaixo é um atalho que ajusta
        # os tamanhos do splitter, mas o arraste manual continua livre.
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.addWidget(content)
        self.main_splitter.addWidget(self._build_log_group())
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([650, _LOG_HEIGHT_DEFAULT])

        outer_layout.addWidget(self.main_splitter)

    def _build_actions_row(self) -> QHBoxLayout:
        top_layout = QHBoxLayout()

        self.btn_generate = QPushButton("Gerar LISTXML filtrado")
        self.btn_generate.setToolTip(
            "Gera um XML contendo apenas as máquinas que atendem ao "
            "Perfil de Filtro selecionado abaixo."
        )
        self.btn_generate.clicked.connect(self._generate_filtered_xml)

        self.btn_scan = QPushButton("Iniciar escaneamento")
        self.btn_scan.setToolTip(
            "Escaneia as origens configuradas em busca das ROMs/CHDs "
            "descritos no XML selecionado. Erros isolados são reportados "
            "no log, mas nunca interrompem o processo."
        )
        self.btn_scan.clicked.connect(self._start_scan)

        self.btn_stop = QPushButton("Parar")
        self.btn_stop.setToolTip("Interrompe o escaneamento em andamento.")
        self.btn_stop.clicked.connect(self._stop_scan)
        self.btn_stop.setEnabled(False)

        top_layout.addWidget(self.btn_generate)
        top_layout.addWidget(self.btn_scan)
        top_layout.addWidget(self.btn_stop)
        top_layout.addStretch()
        return top_layout

    def _build_xml_row(self) -> QHBoxLayout:
        xml_layout = QHBoxLayout()
        xml_layout.addWidget(QLabel("Arquivo:"))

        self.xml_label = QLabel("Nenhum arquivo gerado")
        self.xml_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        xml_layout.addWidget(self.xml_label, stretch=1)

        btn_select_xml = QPushButton("Selecionar XML existente...")
        btn_select_xml.setToolTip(
            "Escolhe, dentre os XMLs já gerados em data/scans, qual usar "
            "para o escaneamento — sem precisar gerar um novo agora."
        )
        btn_select_xml.clicked.connect(self._select_existing_xml)
        xml_layout.addWidget(btn_select_xml)

        btn_open_scans_dir = QPushButton("Abrir pasta de XMLs")
        btn_open_scans_dir.setToolTip("Abre data/scans no explorador de arquivos.")
        btn_open_scans_dir.clicked.connect(self._open_scans_dir)
        xml_layout.addWidget(btn_open_scans_dir)

        return xml_layout

    def _build_profile_group(self) -> QGroupBox:
        profile_group = QGroupBox("PERFIL DE FILTRO PARA O SET")
        profile_layout = QHBoxLayout(profile_group)

        profile_layout.addWidget(QLabel("Perfil:"))

        self.profile_combo = QComboBox()
        self.profile_combo.setToolTip(
            "Perfil de filtro (criado/salvo na aba Filtragem) usado para "
            "selecionar quais máquinas entram no XML filtrado.\n"
            "'Todas as máquinas' gera o set completo, sem filtro."
        )
        profile_layout.addWidget(self.profile_combo, stretch=1)

        btn_refresh_profiles = QPushButton("Atualizar perfis")
        btn_refresh_profiles.clicked.connect(self._load_filter_profiles)
        profile_layout.addWidget(btn_refresh_profiles)

        return profile_group

    def _build_paths_group(self) -> QGroupBox:
        """Configurações de Pastas: 3 origens lado a lado, destino, layout e modo.

        Renomeado de "ORIGENS E DESTINO" e reorganizado: as 3 origens
        ficam alinhadas em colunas (Origem 1 | Origem 2 | Origem 3),
        cada uma com rótulo + campo + botão empilhados verticalmente.
        """
        paths_group = QGroupBox("Configurações de Pastas")
        paths_layout = QGridLayout(paths_group)
        paths_layout.setHorizontalSpacing(12)
        paths_layout.setVerticalSpacing(6)

        self.source_edits: List[QLineEdit] = []
        for col in range(3):
            origem_box = QVBoxLayout()
            origem_box.addWidget(QLabel(f"Origem {col + 1}:"))

            edit = QLineEdit(
                str(self.config.source_dirs[col]) if col < len(self.config.source_dirs) else ""
            )
            row_box = QHBoxLayout()
            row_box.addWidget(edit)

            button = QPushButton("Escolher")
            button.clicked.connect(lambda _=False, e=edit: self._choose_directory(e))
            row_box.addWidget(button)

            origem_box.addLayout(row_box)
            paths_layout.addLayout(origem_box, 0, col)
            self.source_edits.append(edit)

        # Destino, ocupando as 3 colunas.
        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Destino:"))
        self.destination_edit = QLineEdit(
            str(self.config.destination_dir) if self.config.destination_dir else ""
        )
        dest_row.addWidget(self.destination_edit, stretch=1)
        destination_button = QPushButton("Escolher")
        destination_button.clicked.connect(lambda: self._choose_directory(self.destination_edit))
        dest_row.addWidget(destination_button)
        paths_layout.addLayout(dest_row, 1, 0, 1, 3)

        # Organização e Modo MAME lado a lado.
        options_row = QHBoxLayout()
        options_row.addWidget(QLabel("Organização:"))
        self.layout_combo = QComboBox()
        self.layout_combo.addItem("Uma pasta", "single")
        self.layout_combo.addItem("Roms / CHD / Devices / Bios", "split")
        self.layout_combo.setCurrentIndex(1 if self.config.output_layout == "split" else 0)
        options_row.addWidget(self.layout_combo, stretch=1)

        options_row.addWidget(QLabel("Modo MAME:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Split — pai separado dos clones", "split")
        self.mode_combo.addItem("Non-merged — cada jogo completo", "non-merged")
        self.mode_combo.addItem("Merged — pai contém os clones", "merged")
        options_row.addWidget(self.mode_combo, stretch=1)
        paths_layout.addLayout(options_row, 2, 0, 1, 3)

        self.btn_reconstruct = QPushButton("Reconstruir válidos")
        self.btn_reconstruct.clicked.connect(self._reconstruct_validated)
        paths_layout.addWidget(self.btn_reconstruct, 3, 0, 1, 3)

        return paths_group

    def _build_summary_group(self) -> QGroupBox:
        summary_group = QGroupBox("RESUMO")
        summary_layout = QGridLayout(summary_group)

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
        for idx, (label, key) in enumerate(categories):
            row, col = divmod(idx, 4)
            summary_layout.addWidget(QLabel(f"{label}:"), row, col * 2)
            lbl = QLabel("0")
            lbl.setStyleSheet("font-weight: bold;")
            self.summary_labels[key] = lbl
            summary_layout.addWidget(lbl, row, col * 2 + 1)

        return summary_group

    def _build_tree(self) -> QTreeWidget:
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["ROM", "Jogo", "Tamanho", "CRC", "Status"])
        self.tree.setColumnWidth(0, 220)
        self.tree.setColumnWidth(1, 220)
        self.tree.setColumnWidth(2, 100)
        self.tree.setColumnWidth(3, 120)
        self.tree.setColumnWidth(4, 110)
        self.tree.itemDoubleClicked.connect(self._on_tree_double_click)
        return self.tree

    def _build_log_group(self) -> QWidget:
        """Painel de log com atalho de altura (spinbox) + arraste livre pelo splitter."""
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 4, 0, 0)
        log_layout.setSpacing(4)

        log_toolbar = QHBoxLayout()
        log_toolbar.addWidget(QLabel("Altura do log (px):"))

        self.log_height_spin = QSpinBox()
        self.log_height_spin.setRange(_LOG_HEIGHT_MIN, _LOG_HEIGHT_MAX)
        self.log_height_spin.setSingleStep(20)
        self.log_height_spin.setValue(_LOG_HEIGHT_DEFAULT)
        self.log_height_spin.setToolTip(
            "Define a altura do painel de log abaixo. Você também pode "
            "arrastar a divisória entre as seções livremente."
        )
        self.log_height_spin.valueChanged.connect(self._on_log_height_changed)
        log_toolbar.addWidget(self.log_height_spin)
        log_toolbar.addStretch()
        log_layout.addLayout(log_toolbar)

        # logger_name="" -> anexa ao logger raiz, capturando logs de toda
        # a aplicação (scanner, exportação de XML, reconstrução etc.).
        self.log_panel = LogPanel(self, logger_name="")
        log_layout.addWidget(self.log_panel)

        return log_container

    def _on_log_height_changed(self, value: int) -> None:
        """Ajusta o splitter para a altura escolhida, sem travar o arraste manual."""
        total = self.main_splitter.height()
        if total <= 0:
            total = 650 + value
        top = max(150, total - value)
        self.main_splitter.setSizes([top, value])

    # ========================================================================
    # PERFIS DE FILTRO
    # ========================================================================

    def _get_db_connection(self):
        main_db = getattr(self.parent, "db", None)
        if main_db is not None and getattr(main_db, "conn", None) is not None:
            return main_db.conn, False

        db = Database(self.config.db_path)
        db.connect()
        return db.conn, True

    def _load_filter_profiles(self) -> None:
        current_id = self.profile_combo.currentData() if hasattr(self, "profile_combo") else None

        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("Todas as máquinas (sem filtro)", None)

        conn, owns = self._get_db_connection()
        try:
            filter_service = FilterService(conn)
            for profile in filter_service.get_profiles():
                self.profile_combo.addItem(profile.name, profile.id)

            target_id = current_id
            if target_id is None:
                default = filter_service.get_default_profile()
                if default:
                    target_id = default.id

            if target_id is not None:
                idx = self.profile_combo.findData(target_id)
                if idx >= 0:
                    self.profile_combo.setCurrentIndex(idx)
        except Exception as e:
            logger.warning(f"Não foi possível carregar perfis de filtro: {e}")
        finally:
            self.profile_combo.blockSignals(False)
            if owns:
                conn.close()

    def _get_selected_criteria(self) -> FilterCriteria:
        profile_id = self.profile_combo.currentData()
        if not profile_id:
            return FilterCriteria()

        conn, owns = self._get_db_connection()
        try:
            filter_service = FilterService(conn)
            profile = next(
                (p for p in filter_service.get_profiles() if p.id == profile_id),
                None,
            )
            return profile.criteria if profile else FilterCriteria()
        finally:
            if owns:
                conn.close()

    # ========================================================================
    # ESTADO DA UI
    # ========================================================================

    def _update_ui_state(self) -> None:
        has_xml = self.filtered_xml_path is not None and self.filtered_xml_path.exists()

        self.btn_scan.setEnabled(has_xml and not self.scanning)
        self.btn_stop.setEnabled(self.scanning)
        self.btn_generate.setEnabled(not self.scanning)
        self.profile_combo.setEnabled(not self.scanning)
        self.btn_reconstruct.setEnabled(bool(self.scan_result) and not self.scanning)

    # Compatibilidade com quem já referenciava o nome antigo.
    update_ui_state = _update_ui_state

    def _choose_directory(self, edit: QLineEdit) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Escolher diretório")
        if selected:
            edit.setText(selected)
            self._save_paths()

    def _save_paths(self) -> None:
        self.config.source_dirs = [
            Path(e.text()) for e in self.source_edits if e.text().strip()
        ][:3]
        self.config.destination_dir = (
            Path(self.destination_edit.text()) if self.destination_edit.text().strip() else None
        )
        self.config.output_layout = self.layout_combo.currentData()
        self.config.save()

    def _get_rom_paths(self) -> List[Path]:
        return [
            Path(e.text())
            for e in self.source_edits
            if e.text().strip() and Path(e.text()).is_dir()
        ][:3]

    # ========================================================================
    # XML FILTRADO
    # ========================================================================

    def _scans_dir(self) -> Path:
        scans_dir = Path("data/scans")
        scans_dir.mkdir(parents=True, exist_ok=True)
        return scans_dir

    def _open_scans_dir(self) -> None:
        import os
        import sys

        scans_dir = self._scans_dir()
        try:
            if sys.platform == "win32":
                os.startfile(str(scans_dir))  # noqa: S606
            elif sys.platform == "darwin":
                os.system(f'open "{scans_dir}"')
            else:
                os.system(f'xdg-open "{scans_dir}"')
        except Exception as e:
            logger.warning(f"Não foi possível abrir a pasta de scans: {e}")
            QMessageBox.information(self, "Pasta de XMLs", f"Local: {scans_dir}")

    def _select_existing_xml(self) -> None:
        scans_dir = self._scans_dir()

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar XML filtrado para escanear",
            str(scans_dir),
            "Arquivos XML (*.xml);;Todos os arquivos (*)",
        )
        if not file_path:
            return

        selected = Path(file_path)
        if not selected.exists():
            QMessageBox.warning(self, "Erro", "Arquivo selecionado não encontrado.")
            return

        self._set_active_xml(selected, origin="selecionado manualmente")

    def _set_active_xml(self, xml_path: Path, *, origin: str) -> None:
        self.filtered_xml_path = xml_path
        self.xml_label.setText(str(xml_path))
        self.xml_label.setStyleSheet("color: green;")
        self.status_label.setText(f"XML ativo ({origin}): {xml_path.name}")
        logger.info(f"XML ativo para scan ({origin}): {xml_path}")
        self._update_ui_state()

    def _generate_filtered_xml(self) -> None:
        self.status_label.setText("Gerando XML filtrado...")
        self.btn_generate.setEnabled(False)
        try:
            service = ListxmlExportService(self.config.db_path, self.config.mame_path)
            criteria = self._get_selected_criteria()

            machine_ids = service.get_machine_ids_from_db(criteria)
            if not machine_ids:
                QMessageBox.warning(
                    self,
                    "Aviso",
                    "Nenhuma máquina encontrada com os filtros atuais.",
                )
                return

            logger.info(
                f"{len(machine_ids)} máquina(s) selecionada(s) para o XML "
                f"filtrado (perfil: {self.profile_combo.currentText()})."
            )

            version = self._get_mame_version()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"mame_{version}_filtered_{timestamp}.xml"
            output_path = self._scans_dir() / filename

            service.generate_filtered_xml(machine_ids, output_path)

            self._set_active_xml(output_path, origin="recém-gerado")

            QMessageBox.information(
                self,
                "Sucesso",
                f"XML filtrado gerado em:\n{output_path}\n\n"
                f"{len(machine_ids)} máquina(s) selecionada(s) "
                f"(perfil: {self.profile_combo.currentText()}).",
            )
        except Exception as e:
            logger.exception("Falha ao gerar XML filtrado.")
            self.status_label.setText(f"Erro: {e}")
            QMessageBox.critical(self, "Erro", f"Erro ao gerar XML: {e}")
        finally:
            self.btn_generate.setEnabled(True)
            self._update_ui_state()

    def _get_mame_version(self) -> str:
        try:
            import re
            import subprocess

            if self.config.mame_path and self.config.mame_path.exists():
                result = subprocess.run(
                    [str(self.config.mame_path), "-help"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                first_line = result.stdout.strip().split("\n")[0]
                match = re.search(r"v?(\d+\.\d+)", first_line)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return "0.289"

    # ========================================================================
    # SCAN
    # ========================================================================

    def _start_scan(self) -> None:
        if not self.filtered_xml_path or not self.filtered_xml_path.exists():
            QMessageBox.critical(self, "Erro", "Nenhum XML filtrado disponível.")
            return

        if self.scanning:
            return

        self.scanning = True
        self._update_ui_state()
        self.tree.clear()
        self.scan_result = ScanResult(version="unknown")
        self.progress_bar.setValue(0)
        self.status_label.setText("Escaneando...")

        self.scan_thread = threading.Thread(target=self._do_scan, daemon=True)
        self.scan_thread.start()

    def _stop_scan(self) -> None:
        if self.scanning:
            self.scanning = False
            self.status_label.setText("Parando...")
            self.btn_stop.setEnabled(False)
            logger.info("Solicitada a interrupção do scan pelo usuário.")

    def _do_scan(self) -> None:
        """Executa o scan em background, do início ao fim, sem parar em erros.

        Qualquer falha isolada — ROM corrompida, item ausente dentro de um
        ZIP, máquina com XML inconsistente — é registrada no log e tratada
        como ``ScanStatus.CORRUPTED``/``MISSING`` para aquele item
        específico. O laço abaixo NUNCA é interrompido por uma exceção de
        um item isolado: apenas uma falha ao carregar o próprio XML ou ao
        listar as origens interrompe o processo por completo.
        """
        try:
            logger.info(f"Iniciando scan a partir de: {self.filtered_xml_path}")
            machines = self._load_machines_from_xml(self.filtered_xml_path)

            self._save_paths()
            rom_paths = self._get_rom_paths()
            logger.info(f"Origens configuradas para o scan: {rom_paths}")

            if not rom_paths:
                logger.warning(
                    "Nenhuma origem válida configurada — o scan prosseguirá, "
                    "mas todas as ROMs provavelmente aparecerão como ausentes."
                )

            scanner = RomScanner(rom_paths)

            # Constrói o índice (crc,size) -> candidatos UMA VEZ, antes do
            # laço. Sem isso, cada ROM ausente/corrompida reabriria todos
            # os ZIPs das origens do zero em busca de uma cópia
            # alternativa — o que na prática travava o scan no primeiro
            # arquivo problemático.
            self.status_label_safe("Construindo índice de arquivos das origens...")
            scanner.build_archive_index(
                progress_callback=lambda done, total, name: logger.debug(
                    f"Indexando arquivos: {done}/{total} ({name})"
                )
            )

            total = len(machines)
            logger.info(f"{total} máquina(s) a escanear.")

            for idx, machine in enumerate(machines):
                if not self.scanning:
                    logger.info("Scan interrompido pelo usuário.")
                    break

                machine_name = machine.get("name", "?")
                try:
                    result = scanner._scan_single_machine(machine)
                except Exception:
                    # Falha inesperada e isolada nesta máquina: registra e
                    # segue para a próxima. O scan JAMAIS para aqui.
                    logger.exception(
                        f"Falha ao escanear a máquina '{machine_name}'; "
                        "marcada como corrompida e o scan continua."
                    )
                    result = MachineScanResult(
                        name=machine_name,
                        description=machine.get("description", ""),
                        cloneof=machine.get("cloneof"),
                    )
                    result.status = ScanStatus.CORRUPTED

                self.scan_result.machines.append(result)

                QTimer.singleShot(0, lambda r=result: self._add_machine_to_tree(r))
                progress = int((idx + 1) / total * 100) if total else 100
                QTimer.singleShot(0, lambda p=progress: self.progress_bar.setValue(p))
                QTimer.singleShot(
                    0,
                    lambda i=idx + 1, t=total, n=machine_name: self.status_label.setText(
                        f"Escaneando {i}/{t}: {n}"
                    ),
                )

            logger.info("Scan finalizado.")
            QTimer.singleShot(0, self._finish_scan)
        except Exception as e:
            logger.exception("Falha geral durante o scan (interrompido).")
            QTimer.singleShot(0, lambda: self._show_scan_error(str(e)))

    def status_label_safe(self, text: str) -> None:
        """Atualiza o status a partir da thread de scan sem travar a GUI."""
        QTimer.singleShot(0, lambda: self.status_label.setText(text))

    def _finish_scan(self) -> None:
        self.scanning = False
        if self.scan_result:
            self.scan_result.total_machines = len(self.scan_result.machines)
            self.scan_result.update_summary()
            self._update_summary_labels()
        self._update_ui_state()
        self.progress_bar.setValue(100)
        self.status_label.setText("Escaneamento concluído")

    def _show_scan_error(self, error: str) -> None:
        self.scanning = False
        self._update_ui_state()
        self.status_label.setText(f"Erro: {error}")
        QMessageBox.critical(self, "Erro", f"Erro durante o escaneamento:\n{error}")

    def _update_summary_labels(self) -> None:
        if not self.scan_result:
            return
        result = self.scan_result
        self.summary_labels["roms_total"].setText(str(result.roms_total))
        self.summary_labels["bios_total"].setText(str(result.bios_total))
        self.summary_labels["devices_total"].setText(str(result.devices_total))
        self.summary_labels["chds_total"].setText(str(result.chds_total))
        self.summary_labels["ok_count"].setText(str(result.ok_count))
        self.summary_labels["fixable_count"].setText(str(result.fixable_count))
        self.summary_labels["missing_count"].setText(
            str(result.missing_count + result.unavailable_count)
        )
        self.summary_labels["corrupted_count"].setText(str(result.corrupted_count))

    # ========================================================================
    # ÁRVORE DE RESULTADOS
    # ========================================================================

    def _add_machine_to_tree(self, machine_result: MachineScanResult) -> None:
        icon = "📦" if machine_result.cloneof else "📁"
        item = QTreeWidgetItem(self.tree)
        item.setText(0, f"{icon} {machine_result.name}")
        item.setText(1, machine_result.description[:50])
        item.setText(2, self._format_size(machine_result.total_size))
        item.setText(3, "-")
        item.setText(4, machine_result.status.label)
        self._apply_status_color(item, machine_result.status)

        for rom in machine_result.roms:
            child = QTreeWidgetItem(item)
            child.setText(0, f"  ├─ {rom.name}")
            child.setText(1, "")
            child.setText(2, self._format_size(rom.size))
            child.setText(3, rom.crc[:8] if rom.crc else "-")
            child.setText(4, rom.status.label)
            self._apply_status_color(child, rom.status)

    def _apply_status_color(self, item: QTreeWidgetItem, status: ScanStatus) -> None:
        color = _STATUS_COLORS.get(status, "#000000")
        item.setForeground(4, color)

    def _on_tree_double_click(self, item: QTreeWidgetItem, column: int) -> None:
        text = item.text(0)
        status = item.text(4)
        QMessageBox.information(self, "Detalhes", f"Item: {text}\nStatus: {status}")

    # ========================================================================
    # CARREGAMENTO DO XML
    # ========================================================================

    def _load_machines_from_xml(self, xml_path: Path) -> List[dict]:
        import xml.etree.ElementTree as ET

        machines: List[dict] = []
        tree = ET.parse(xml_path)
        root = tree.getroot()

        for machine_elem in root.findall("machine"):
            machine = {
                "name": machine_elem.get("name", ""),
                "description": "",
                "cloneof": machine_elem.get("cloneof", ""),
                "roms": [],
                "disks": [],
            }
            desc = machine_elem.find("description")
            if desc is not None:
                machine["description"] = desc.text or ""

            for rom_elem in machine_elem.findall("rom"):
                try:
                    size = int(rom_elem.get("size", 0) or 0)
                except ValueError:
                    logger.warning(
                        f"ROM '{rom_elem.get('name', '?')}' da máquina "
                        f"'{machine['name']}' com tamanho inválido; usando 0."
                    )
                    size = 0
                machine["roms"].append(
                    {
                        "name": rom_elem.get("name", ""),
                        "size": size,
                        "crc": rom_elem.get("crc", ""),
                        "sha1": rom_elem.get("sha1", ""),
                        "merge": rom_elem.get("merge", ""),
                    }
                )

            for disk_elem in machine_elem.findall("disk"):
                machine["disks"].append(
                    {
                        "name": disk_elem.get("name", ""),
                        "sha1": disk_elem.get("sha1", ""),
                    }
                )

            machines.append(machine)

        return machines

    # ========================================================================
    # RECONSTRUÇÃO
    # ========================================================================

    def _reconstruct_validated(self) -> None:
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
                    destination=self.config.destination_dir,
                    layout=self.config.output_layout,
                    mode=self.mode_combo.currentData(),
                )
            )
            manifest = service.reconstruct(self.scan_result)
            logger.info(f"Reconstrução concluída. Manifesto: {manifest}")
            QMessageBox.information(
                self, "Reconstrução", f"Concluída. Manifesto salvo em:\n{manifest}"
            )
        except Exception as exc:
            logger.exception("Falha durante a reconstrução do set.")
            QMessageBox.critical(self, "Reconstrução", str(exc))

    # ========================================================================
    # HELPERS
    # ========================================================================

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"