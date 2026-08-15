"""Aba de escaneamento e reconstrução de ROMs.

Fluxo típico:
    1. Gerar (ou selecionar) um LISTXML filtrado, de acordo com um
       Perfil de Filtro configurado na aba Filtragem.
    2. Escanear as origens configuradas em busca das ROMs/CHDs
       necessários, comparando CRC/SHA1/tamanho.
    3. Revisar o resumo e a árvore de resultados.
    4. Reconstruir (copiar) os itens válidos para o destino, no modo
       Split/Non-Merged/Merged escolhido.

O scan é executado em uma thread separada para não travar a GUI, e
qualquer falha isolada (uma ROM corrompida, uma máquina com XML
inconsistente etc.) é registrada no log e tratada como
``ScanStatus.CORRUPTED`` — nunca aborta o restante do processo.
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

# Altura padrão/limites do painel de log, em pixels. O usuário pode
# ajustar livremente através do QSpinBox da toolbar do log.
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
        """Constrói toda a interface da aba."""
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
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(content)
        splitter.addWidget(self._build_log_group())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([650, _LOG_HEIGHT_DEFAULT])

        outer_layout.addWidget(splitter)

    def _build_actions_row(self) -> QHBoxLayout:
        """Botões principais: gerar XML, iniciar/parar scan."""
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
            "descritos no XML selecionado."
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
        """Linha com o caminho do XML atual e botão de seleção manual."""
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
        """Seletor do Perfil de Filtro usado para gerar/escanear o set."""
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
        """Origens (até 3, independentes de mame.ini), destino e modo de set."""
        paths_group = QGroupBox("ORIGENS E DESTINO")
        paths_layout = QGridLayout(paths_group)

        self.source_edits: List[QLineEdit] = []
        for row in range(3):
            edit = QLineEdit(
                str(self.config.source_dirs[row]) if row < len(self.config.source_dirs) else ""
            )
            button = QPushButton("Escolher")
            button.clicked.connect(lambda _=False, e=edit: self._choose_directory(e))
            paths_layout.addWidget(QLabel(f"Origem {row + 1}:"), row, 0)
            paths_layout.addWidget(edit, row, 1)
            paths_layout.addWidget(button, row, 2)
            self.source_edits.append(edit)

        self.destination_edit = QLineEdit(
            str(self.config.destination_dir) if self.config.destination_dir else ""
        )
        destination_button = QPushButton("Escolher")
        destination_button.clicked.connect(lambda: self._choose_directory(self.destination_edit))

        self.layout_combo = QComboBox()
        self.layout_combo.addItem("Uma pasta", "single")
        self.layout_combo.addItem("Roms / CHD / Devices / Bios", "split")
        self.layout_combo.setCurrentIndex(1 if self.config.output_layout == "split" else 0)

        paths_layout.addWidget(QLabel("Destino:"), 3, 0)
        paths_layout.addWidget(self.destination_edit, 3, 1)
        paths_layout.addWidget(destination_button, 3, 2)
        paths_layout.addWidget(QLabel("Organização:"), 4, 0)
        paths_layout.addWidget(self.layout_combo, 4, 1, 1, 2)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Split — pai separado dos clones", "split")
        self.mode_combo.addItem("Non-merged — cada jogo completo", "non-merged")
        self.mode_combo.addItem("Merged — pai contém os clones", "merged")
        paths_layout.addWidget(QLabel("Modo MAME:"), 5, 0)
        paths_layout.addWidget(self.mode_combo, 5, 1, 1, 2)

        self.btn_reconstruct = QPushButton("Reconstruir válidos")
        self.btn_reconstruct.clicked.connect(self._reconstruct_validated)
        paths_layout.addWidget(self.btn_reconstruct, 6, 1, 1, 2)

        return paths_group

    def _build_summary_group(self) -> QGroupBox:
        """Resumo numérico do último resultado de scan."""
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
        """Árvore de máquinas/ROMs escaneadas."""
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
        """Painel de log com altura personalizável pelo usuário."""
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
            "Ajusta a altura do painel de log abaixo, entre "
            f"{_LOG_HEIGHT_MIN} e {_LOG_HEIGHT_MAX} pixels."
        )
        self.log_height_spin.valueChanged.connect(self._on_log_height_changed)
        log_toolbar.addWidget(self.log_height_spin)
        log_toolbar.addStretch()
        log_layout.addLayout(log_toolbar)

        # logger_name="" -> anexa ao logger raiz, capturando logs de toda
        # a aplicação (scanner, exportação de XML, reconstrução etc.), não
        # apenas desta aba.
        self.log_panel = LogPanel(self, logger_name="")
        log_layout.addWidget(self.log_panel)

        self._on_log_height_changed(self.log_height_spin.value())

        return log_container

    def _on_log_height_changed(self, value: int) -> None:
        """Aplica a altura escolhida pelo usuário ao painel de log."""
        self.log_panel.setMinimumHeight(value)
        self.log_panel.setMaximumHeight(value)

    # ========================================================================
    # PERFIS DE FILTRO
    # ========================================================================

    def _get_db_connection(self):
        """Retorna ``(conn, owns_connection)``.

        Reaproveita a conexão SQLite da MainWindow (mesma conexão usada
        pela aba Filtragem) quando disponível, evitando abrir conexões
        redundantes. Caso não exista (ex.: aba usada isoladamente em
        testes), abre e devolve uma conexão própria — quem chamar deve
        fechá-la.
        """
        main_db = getattr(self.parent, "db", None)
        if main_db is not None and getattr(main_db, "conn", None) is not None:
            return main_db.conn, False

        db = Database(self.config.db_path)
        db.connect()
        return db.conn, True

    def _load_filter_profiles(self) -> None:
        """Carrega no combo os perfis de filtro salvos na aba Filtragem."""
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
            # Primeira execução / banco ainda sem perfis: mantém apenas a
            # opção "sem filtro" e não quebra a inicialização da aba.
            logger.warning(f"Não foi possível carregar perfis de filtro: {e}")
        finally:
            self.profile_combo.blockSignals(False)
            if owns:
                conn.close()

    def _get_selected_criteria(self) -> FilterCriteria:
        """Retorna os critérios do perfil selecionado no combo local."""
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
        """Habilita/desabilita controles conforme o estado atual."""
        has_xml = self.filtered_xml_path is not None and self.filtered_xml_path.exists()

        self.btn_scan.setEnabled(has_xml and not self.scanning)
        self.btn_stop.setEnabled(self.scanning)
        self.btn_generate.setEnabled(not self.scanning)
        self.profile_combo.setEnabled(not self.scanning)
        self.btn_reconstruct.setEnabled(bool(self.scan_result) and not self.scanning)

    # Mantido por compatibilidade com quem já referenciava o nome antigo.
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
        """Abre a pasta data/scans no explorador de arquivos do sistema."""
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
        """Permite escolher, dentre os XMLs já gerados em data/scans, qual
        usar para o escaneamento — sem precisar gerar um novo agora.
        """
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
        """Centraliza a atualização do XML ativo, evitando duplicação de
        lógica entre geração e seleção manual."""
        self.filtered_xml_path = xml_path
        self.xml_label.setText(str(xml_path))
        self.xml_label.setStyleSheet("color: green;")
        self.status_label.setText(f"XML ativo ({origin}): {xml_path.name}")
        logger.info(f"XML ativo para scan ({origin}): {xml_path}")
        self._update_ui_state()

    def _generate_filtered_xml(self) -> None:
        """Gera um LISTXML contendo apenas as máquinas do perfil selecionado."""
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
        """Executa o scan em background.

        Qualquer falha isolada (uma máquina com XML inconsistente, uma
        ROM corrompida, um erro de I/O pontual) é registrada no log e
        tratada como ``ScanStatus.CORRUPTED`` para aquele item — o
        restante do escaneamento continua normalmente. Apenas uma falha
        que impeça o carregamento do próprio XML ou das origens configuradas
        interrompe o processo por completo (e é reportada via
        ``_show_scan_error``).
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
                    # segue para a próxima, sem abortar o scan inteiro.
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
        """Carrega as máquinas de um XML filtrado para uso pelo scanner.

        Usa ``xml.etree.ElementTree.parse`` diretamente (XML filtrado é
        tipicamente pequeno o suficiente para caber em memória, ao
        contrário do -listxml completo do MAME).
        """
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