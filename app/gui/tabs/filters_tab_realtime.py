"""Aba de filtragem de ROMs e gerenciamento de categorias."""

import logging
import sqlite3
import threading
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QCheckBox,
    QComboBox,
    QMessageBox,
    QScrollArea,
    QLineEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QSplitter,
    QSizePolicy,
)

from app.core.services.filter_service import FilterService
from app.core.models.filter_profile import FilterCriteria, FilterProfile
from app.database.database import Database
from app.config.app_config import AppConfig
from app.mame.executable import MameExecutable
from app.core.services.database_service import DatabaseService
from app.core.services.ini_service import IniService
from app.mame.chd_scanner import scan_chd_sizes
from app.gui.widgets.log_panel import LogPanel


logger = logging.getLogger(__name__)


class FiltersTab(QWidget):
    """Interface principal para configuração e aplicação dos filtros do MAME."""

    class CategoryChip(QPushButton):
        """Botão compacto que alterna uma categoria entre normal e excluída."""

        STATE_NORMAL = 0
        STATE_EXCLUDE = 1

        def __init__(
            self,
            category_name: str,
            display_name: str,
            count: int,
            parent=None,
        ):
            super().__init__(f"{display_name} ({count})", parent)

            self.category_name = category_name
            self.state = self.STATE_NORMAL

            self.setCheckable(False)
            self.setSizePolicy(
                QSizePolicy.Policy.Minimum,
                QSizePolicy.Policy.Fixed,
            )
            self.setMinimumHeight(24)
            self.setMaximumHeight(28)
            self.setToolTip(
                f"Categoria: {display_name}\n"
                "Clique para excluir esta categoria.\n"
                "Clique novamente para restaurá-la."
            )

            self.clicked.connect(self.toggle_state)
            self.update_style()

        def toggle_state(self) -> None:
            """Alterna o estado visual e notifica a aba de filtros."""
            self.state = (
                self.STATE_EXCLUDE
                if self.state == self.STATE_NORMAL
                else self.STATE_NORMAL
            )
            self.update_style()

            parent = self.parentWidget()
            if parent and hasattr(parent, "on_category_changed"):
                parent.on_category_changed(self.category_name, self.state)

        def update_style(self) -> None:
            """Atualiza o estilo do chip conforme seu estado atual."""
            base_style = (
                "border: 1px solid #888;"
                "border-radius: 3px;"
                "padding: 2px 6px;"
                "font-size: 8pt;"
            )

            if self.state == self.STATE_NORMAL:
                self.setStyleSheet(
                    f"background-color: #e0e0e0;"
                    f"color: black;"
                    f"{base_style}"
                )
            else:
                self.setStyleSheet(
                    f"background-color: #ff4d4d;"
                    f"color: white;"
                    f"{base_style}"
                )

        def set_state(self, state: int) -> None:
            """Define o estado do chip sem disparar o callback."""
            self.state = (
                self.STATE_EXCLUDE
                if state == self.STATE_EXCLUDE
                else self.STATE_NORMAL
            )
            self.update_style()

    filters_changed = Signal()
    database_updated = Signal()
    progress_signal = Signal(int, str)
    finish_signal = Signal(bool, str)
    filter_result_signal = Signal(int, object, object)

    def __init__(self, parent=None, db: Database = None):
        super().__init__(parent)

        self.main_window = parent
        self.config = AppConfig()
        self.db = db or Database(self.config.db_path)
        self.db.connect()
        self.filter_service = FilterService(self.db.conn)

        self.current_criteria = FilterCriteria()
        self.profiles = []
        self._import_running = False
        self.category_chips = {}

        # Controle do recálculo assíncrono dos filtros. As consultas de
        # categorias podem ser pesadas e não devem bloquear o thread da UI.
        self._filter_generation = 0
        self._filter_calculation_running = False
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(50)
        self._filter_timer.timeout.connect(self._start_filter_calculation)
        self._pending_filter_criteria = None
        self._pending_filter_generation = 0

        self.progress_signal.connect(self._on_progress_update)
        self.finish_signal.connect(self._on_import_finished)
        self.filter_result_signal.connect(
            self._on_filter_calculation_finished
        )

        self._setup_ui()
        self._load_categories()
        self._load_profiles()
        self._update_database_info()

        QTimer.singleShot(100, self._apply_current_filters)

    def _setup_ui(self) -> None:
        """Cria todos os controles visuais da aba de filtros."""
        if self.layout():
            old_layout = self.layout()
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(4, 4, 4, 4)
        outer_layout.setSpacing(4)
        self.setLayout(outer_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # ============================
        # GRUPO: BANCO DE DADOS
        # ============================
        grp_db = QGroupBox("Banco de Dados do MAME")
        db_layout = QFormLayout()
        grp_db.setLayout(db_layout)

        self.lbl_mame_version = QLabel("Versão do MAME: não detectada")
        self.lbl_db_status = QLabel("Status: banco não criado")
        self.lbl_machine_count = QLabel("Máquinas: 0")
        self.lbl_rom_count = QLabel("ROMs: 0")
        self.lbl_chd_count = QLabel("CHDs: 0")

        db_layout.addRow(self.lbl_mame_version)
        db_layout.addRow(self.lbl_db_status)
        db_layout.addRow(self.lbl_machine_count)
        db_layout.addRow(self.lbl_rom_count)
        db_layout.addRow(self.lbl_chd_count)

        db_buttons_layout = QHBoxLayout()

        btn_sync = QPushButton("Importar/Atualizar Banco")
        btn_sync.clicked.connect(self._sync_database)
        btn_sync.setToolTip(
            "Recria ou atualiza o banco com os dados do MAME -listxml."
        )
        db_buttons_layout.addWidget(btn_sync)

        btn_import_cat = QPushButton("Importar categorias (catver.ini)")
        btn_import_cat.clicked.connect(self._import_categories)
        btn_import_cat.setToolTip(
            "Importa o catver.ini da pasta 'folders' do MAME, "
            "agrupando pelo primeiro nível."
        )
        db_buttons_layout.addWidget(btn_import_cat)

        btn_scan_chd = QPushButton("Escanear tamanho dos CHDs")
        btn_scan_chd.clicked.connect(self._scan_chd_sizes)
        btn_scan_chd.setToolTip(
            "O -listxml do MAME não informa o tamanho dos CHDs. "
            "Este botão lê o tamanho real dos arquivos .chd na pasta "
            "configurada como 'rompath' no mame.ini, para que "
            "'Tamanho estimado' fique correto."
        )
        db_buttons_layout.addWidget(btn_scan_chd)

        db_layout.addRow(db_buttons_layout)
        layout.addWidget(grp_db)

        # ============================
        # GRUPO: PERFIS
        # ============================
        grp_profiles = QGroupBox("Perfis de Filtro")
        prof_layout = QVBoxLayout()
        grp_profiles.setLayout(prof_layout)

        hbox_profiles = QHBoxLayout()

        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(
            self._on_profile_selected
        )
        hbox_profiles.addWidget(self.profile_combo, stretch=1)

        btn_new = QPushButton("Novo")
        btn_new.clicked.connect(self._create_new_profile)
        hbox_profiles.addWidget(btn_new)

        btn_save = QPushButton("Salvar")
        btn_save.clicked.connect(self._save_current_profile)
        hbox_profiles.addWidget(btn_save)

        btn_delete = QPushButton("Excluir")
        btn_delete.clicked.connect(self._delete_profile)
        hbox_profiles.addWidget(btn_delete)

        prof_layout.addLayout(hbox_profiles)
        layout.addWidget(grp_profiles)

        # ============================
        # GRUPO: ESTADO DE EMULAÇÃO
        # ============================
        grp_status = QGroupBox("Estado de Emulação")
        status_layout = QHBoxLayout()
        grp_status.setLayout(status_layout)

        self.status_checkboxes = {}

        status_options = [
            ("working", "Working"),
            ("imperfect", "Imperfect"),
            ("not_working", "Not Working"),
        ]

        for value, label in status_options:
            cb = QCheckBox(label)
            cb.setChecked(False)
            cb.stateChanged.connect(self._on_status_changed)
            self.status_checkboxes[value] = cb
            status_layout.addWidget(cb)

        status_layout.addStretch()
        layout.addWidget(grp_status)

        # ============================
        # GRUPO: OPÇÕES
        # ============================
        grp_options = QGroupBox("Opções")
        options_layout = QHBoxLayout()
        grp_options.setLayout(options_layout)

        self.chk_clones = QCheckBox("Incluir Clones")
        self.chk_clones.setChecked(True)
        self.chk_clones.toggled.connect(self._on_filters_changed)
        options_layout.addWidget(self.chk_clones)

        self.chk_bios = QCheckBox("Incluir BIOS")
        self.chk_bios.setChecked(True)
        self.chk_bios.toggled.connect(self._on_filters_changed)
        options_layout.addWidget(self.chk_bios)

        self.chk_devices = QCheckBox("Incluir Devices")
        self.chk_devices.setChecked(True)
        self.chk_devices.toggled.connect(self._on_filters_changed)
        options_layout.addWidget(self.chk_devices)

        self.chk_chd = QCheckBox("Incluir CHD")
        self.chk_chd.setChecked(True)
        self.chk_chd.toggled.connect(self._on_filters_changed)
        self.chk_chd.setToolTip(
            "Desmarque para excluir máquinas que possuem CHD."
        )
        options_layout.addWidget(self.chk_chd)

        options_layout.addStretch()
        layout.addWidget(grp_options)

        # ============================
        # GRUPO: INFORMAÇÕES DO FILTRO
        # ============================
        grp_info = QGroupBox("Informações do Filtro")
        info_layout = QFormLayout()
        grp_info.setLayout(info_layout)

        self.lbl_machines = QLabel("0")
        self.lbl_roms_filtered = QLabel("0")
        self.lbl_chds_filtered = QLabel("0")
        self.lbl_size = QLabel("0 MB")

        self.lbl_excluded_categories = QLabel("Nenhuma")
        self.lbl_excluded_categories.setWordWrap(True)
        self.lbl_excluded_categories.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        info_layout.addRow("Máquinas:", self.lbl_machines)
        info_layout.addRow("ROMs:", self.lbl_roms_filtered)
        info_layout.addRow("CHDs:", self.lbl_chds_filtered)
        info_layout.addRow("Tamanho estimado:", self.lbl_size)
        info_layout.addRow(
            "Categorias excluídas:",
            self.lbl_excluded_categories,
        )

        layout.addWidget(grp_info)

        # ============================
        # GRUPO: CATEGORIAS
        # ============================
        grp_cats = QGroupBox("Categorias")
        cats_layout = QVBoxLayout()
        cats_layout.setContentsMargins(6, 6, 6, 6)
        cats_layout.setSpacing(4)
        grp_cats.setLayout(cats_layout)

        legend = QLabel(
            "Clique na categoria para excluir (vermelho) "
            "ou restaurar ao estado normal (cinza)."
        )
        legend.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cats_layout.addWidget(legend)

        cat_scroll = QScrollArea()
        cat_scroll.setWidgetResizable(True)
        cat_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        cat_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        cat_scroll.setMinimumHeight(120)
        cat_scroll.setMaximumHeight(320)

        cat_container = QWidget()
        cat_container.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )

        self.cat_grid = QGridLayout(cat_container)
        self.cat_grid.setContentsMargins(4, 4, 4, 4)
        self.cat_grid.setHorizontalSpacing(4)
        self.cat_grid.setVerticalSpacing(4)
        self.cat_grid.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        cat_scroll.setWidget(cat_container)
        cats_layout.addWidget(cat_scroll)

        layout.addWidget(grp_cats)

        scroll.setWidget(container)

        # ============================
        # SPLITTER
        # ============================
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(scroll)

        self.log_panel = LogPanel(self, logger_name="")
        splitter.addWidget(self.log_panel)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([600, 200])

        outer_layout.addWidget(splitter)

        self._set_controls_enabled(False)

    # ========================================================================
    # CATEGORIAS
    # ========================================================================

    def _load_categories(self) -> None:
        """Carrega as categorias do banco e reconstrói os clips da interface."""
        previous_excluded = set(self._get_excluded_categories())

        for chip in self.category_chips.values():
            self.cat_grid.removeWidget(chip)
            chip.deleteLater()

        self.category_chips.clear()

        all_cats = self.filter_service.get_categories_with_counts()

        if not all_cats:
            self.filter_service.seed_default_categories()
            all_cats = self.filter_service.get_categories_with_counts()

        if not all_cats:
            self._update_excluded_categories_info([])
            return

        # Mantém dez colunas como no layout atual, mas força o conteúdo
        # para o topo. Isso elimina a distribuição vertical excessiva.
        cols = 10

        for idx, cat in enumerate(all_cats):
            row = idx // cols
            col = idx % cols

            chip = self.CategoryChip(
                cat["name"],
                cat["display_name"],
                cat["count"],
                self,
            )

            if cat["name"] in previous_excluded:
                chip.set_state(self.CategoryChip.STATE_EXCLUDE)

            self.cat_grid.addWidget(chip, row, col)
            self.category_chips[cat["name"]] = chip

        self._update_excluded_categories_info(
            self._get_excluded_categories()
        )

    def _get_excluded_categories(self) -> List[str]:
        """Retorna os nomes das categorias atualmente marcadas em vermelho."""
        return [
            name
            for name, chip in self.category_chips.items()
            if chip.state == self.CategoryChip.STATE_EXCLUDE
        ]

    def _update_excluded_categories_info(
        self,
        excluded_categories: List[str],
    ) -> None:
        """Atualiza o resumo textual das categorias excluídas."""
        if not excluded_categories:
            self.lbl_excluded_categories.setText("Nenhuma")
            self.lbl_excluded_categories.setToolTip("")
            return

        display_names = []

        for category_name in excluded_categories:
            chip = self.category_chips.get(category_name)

            if chip:
                display_names.append(chip.text())
            else:
                display_names.append(category_name)

        summary = f"{len(display_names)}"
        self.lbl_excluded_categories.setText(
            summary + ": " + ", ".join(display_names)
        )
        self.lbl_excluded_categories.setToolTip(
            "\n".join(display_names)
        )

    def on_category_changed(self, category_name: str, state: int) -> None:
        """
        Processa a alteração de uma categoria e reaplica imediatamente
        os critérios ao banco.

        Args:
            category_name: Nome interno da categoria.
            state: Novo estado do chip.
        """
        excluded_categories = self._get_excluded_categories()

        # Atualiza imediatamente a informação textual. O cálculo pesado das
        # estatísticas será executado em segundo plano.
        self._update_excluded_categories_info(excluded_categories)

        logger.debug(
            "Categoria alterada: %s -> %s; excluídas=%s",
            category_name,
            "EXCLUDE" if state == self.CategoryChip.STATE_EXCLUDE else "NORMAL",
            excluded_categories,
        )

        self._on_filters_changed()

    # ========================================================================
    # ESTADO DE EMULAÇÃO
    # ========================================================================

    def _get_selected_status(self) -> List[str]:
        """Retorna os estados de emulação selecionados na interface."""
        selected = []

        for value, cb in self.status_checkboxes.items():
            if cb.isChecked():
                selected.append(value)

        return selected

    def _on_status_changed(self) -> None:
        """Reaplica os filtros quando o estado de emulação é alterado."""
        self._on_filters_changed()

    # ========================================================================
    # IMPORTAÇÃO DE CATEGORIAS
    # ========================================================================

    def _import_categories(self) -> None:
        """Importa categorias do catver.ini e atualiza a interface."""
        if not self.config.mame_path or not self.config.mame_path.exists():
            QMessageBox.warning(
                self,
                "Erro",
                "Selecione o executável MAME primeiro.",
            )
            return

        default_ini = (
            self.config.mame_path.parent / "folders" / "catver.ini"
        )

        if not default_ini.exists():
            reply = QMessageBox.question(
                self,
                "Arquivo não encontrado",
                (
                    "O arquivo padrão (catver.ini) não foi encontrado em:\n"
                    f"{default_ini}\n\n"
                    "Deseja selecionar manualmente?"
                ),
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar catver.ini",
                "",
                "Arquivos INI (*.ini);;Todos os arquivos (*)",
            )

            if not file_path:
                return

            ini_path = Path(file_path)
        else:
            ini_path = default_ini

        try:
            categorias, maquinas, imported = (
                self.filter_service.import_categories_from_catver(
                    ini_path
                )
            )

            msg = (
                f"Categorias importadas: {categorias}\n"
                f"Máquinas associadas: {maquinas}\n"
            )

            if imported:
                msg += (
                    "\nCategorias criadas:\n"
                    + ", ".join(sorted(imported)[:15])
                )

                if len(imported) > 15:
                    msg += f" ... (+{len(imported) - 15} outras)"

            QMessageBox.information(
                self,
                "Importação concluída",
                msg,
            )

            self._load_categories()
            self._apply_filters()

        except Exception as e:
            logger.error(
                "Falha ao importar categorias.",
                exc_info=True,
            )
            QMessageBox.critical(
                self,
                "Erro",
                f"Falha ao importar categorias:\n{str(e)}",
            )

    # ========================================================================
    # ESCANEAR TAMANHO DOS CHDs
    # ========================================================================

    def _scan_chd_sizes(self) -> None:
        """Escaneia os tamanhos reais dos CHDs configurados no rompath."""
        if self._import_running:
            QMessageBox.warning(
                self,
                "Aguarde",
                "Uma operação já está em andamento.",
            )
            return

        if not self.config.ini_path or not self.config.ini_path.exists():
            QMessageBox.warning(
                self,
                "Erro",
                (
                    "Selecione o mame.ini na aba Diretórios primeiro "
                    "(é de lá que vem o 'rompath' onde os .chd ficam)."
                ),
            )
            return

        try:
            ini_service = IniService(self.config.ini_path)
            rompaths = ini_service.get_paths("rompath")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro",
                f"Falha ao ler mame.ini:\n{e}",
            )
            return

        if not rompaths:
            QMessageBox.warning(
                self,
                "Aviso",
                "Nenhum 'rompath' configurado no mame.ini.",
            )
            return

        self._import_running = True
        self.setEnabled(False)
        self.progress_signal.emit(
            0,
            f"Escaneando CHDs em {len(rompaths)} pasta(s)...",
        )

        def scan_task():
            try:
                chd_sizes = scan_chd_sizes(rompaths)

                self.progress_signal.emit(
                    80,
                    (
                        f"{len(chd_sizes)} CHD(s) encontrados, "
                        "salvando..."
                    ),
                )

                conn = sqlite3.connect(
                    str(self.config.db_path)
                )
                conn.row_factory = sqlite3.Row

                service = DatabaseService(conn)
                updated = service.update_chd_sizes(chd_sizes)
                conn.close()

                self.progress_signal.emit(100, "Concluído.")

                self.finish_signal.emit(
                    True,
                    (
                        "Scanner de CHD concluído.\n"
                        f"{len(chd_sizes)} arquivo(s) .chd encontrados "
                        "nos rompaths.\n"
                        f"{updated} registro(s) atualizados no banco."
                    ),
                )

            except Exception as e:
                logger.error(
                    f"Falha ao escanear CHDs: {e}",
                    exc_info=True,
                )
                self.finish_signal.emit(
                    False,
                    f"Erro ao escanear CHDs: {e}",
                )

        threading.Thread(
            target=scan_task,
            daemon=True,
        ).start()

    # ========================================================================
    # PERFIS
    # ========================================================================

    def _load_profiles(self) -> None:
        """Carrega os perfis disponíveis no banco."""
        self.profile_combo.clear()
        self.profiles = self.filter_service.get_profiles()

        self.profile_combo.addItem("(nenhum)", None)

        for prof in self.profiles:
            self.profile_combo.addItem(prof.name, prof.id)

        default = self.filter_service.get_default_profile()

        if default:
            idx = self.profile_combo.findData(default.id)

            if idx >= 0:
                # O sinal permanece habilitado para que o perfil padrão
                # seja efetivamente carregado na interface.
                self.profile_combo.setCurrentIndex(idx)

    def _on_profile_selected(self, index: int) -> None:
        """Carrega o perfil selecionado e aplica seus critérios."""
        if index <= 0:
            return

        profile_id = self.profile_combo.itemData(index)

        if not profile_id:
            return

        profile = next(
            (p for p in self.profiles if p.id == profile_id),
            None,
        )

        if profile:
            self._load_criteria(profile.criteria)

    def _load_criteria(self, criteria: FilterCriteria) -> None:
        """Transfere os critérios de um perfil para os controles da GUI."""
        self._block_filter_controls(True)

        try:
            for value, cb in self.status_checkboxes.items():
                cb.setChecked(
                    value in criteria.emulation_status
                )

            self.chk_clones.setChecked(criteria.include_clones)
            self.chk_bios.setChecked(criteria.include_bios)
            self.chk_devices.setChecked(criteria.include_devices)
            self.chk_chd.setChecked(criteria.include_chd)

            exclude_set = set(
                criteria.exclude_categories
            )

            for name, chip in self.category_chips.items():
                chip.set_state(
                    self.CategoryChip.STATE_EXCLUDE
                    if name in exclude_set
                    else self.CategoryChip.STATE_NORMAL
                )

        finally:
            self._block_filter_controls(False)

        self.current_criteria = criteria
        self._apply_filters()

    # ========================================================================
    # FILTROS
    # ========================================================================

    def _block_filter_controls(self, blocked: bool) -> None:
        """Bloqueia/desbloqueia sinais dos controles durante carregamentos."""
        for cb in self.status_checkboxes.values():
            cb.blockSignals(blocked)

        self.chk_clones.blockSignals(blocked)
        self.chk_bios.blockSignals(blocked)
        self.chk_devices.blockSignals(blocked)
        self.chk_chd.blockSignals(blocked)

    def _on_filters_changed(self) -> None:
        """
        Atualiza imediatamente o estado lógico da interface e agenda o
        recálculo das estatísticas sem bloquear o thread principal do Qt.

        A consulta SQLite pode envolver centenas de milhares de registros.
        Por isso, a mudança visual e o ``current_criteria`` são atualizados
        primeiro; as estatísticas são calculadas em uma conexão SQLite
        separada, em uma thread de trabalho.
        """
        criteria = self._get_criteria_from_ui()

        self.current_criteria = criteria
        self._filter_generation += 1
        self._pending_filter_generation = self._filter_generation
        self._pending_filter_criteria = criteria

        # Feedback textual é imediato, independentemente do tempo da consulta.
        self._update_excluded_categories_info(criteria.exclude_categories)

        # Informa imediatamente os demais componentes que o critério mudou.
        self.filters_changed.emit()

        # Debounce curto: vários cliques rápidos geram somente o cálculo mais
        # recente, evitando iniciar uma consulta para cada clique.
        self._filter_timer.start()

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Converte bytes para uma unidade legível."""
        if size_bytes >= 1_073_741_824:
            return f"{size_bytes / 1_073_741_824:.2f} GB"

        if size_bytes >= 1_048_576:
            return f"{size_bytes / 1_048_576:.2f} MB"

        if size_bytes >= 1024:
            return f"{size_bytes / 1024:.2f} KB"

        return f"{size_bytes} B"

    def _start_filter_calculation(self) -> None:
        """Inicia o cálculo das estatísticas na thread de trabalho."""
        if self._filter_calculation_running:
            # O cálculo atual terminará e verificará se surgiu uma versão mais
            # nova dos critérios. Não iniciamos duas consultas concorrentes.
            return

        criteria = self._pending_filter_criteria
        generation = self._pending_filter_generation

        if criteria is None:
            return

        self._filter_calculation_running = True
        self._pending_filter_criteria = None

        # Mostra imediatamente que os números estão sendo recalculados, sem
        # apagar o restante das informações já disponíveis.
        self.lbl_machines.setText("Calculando...")
        self.lbl_roms_filtered.setText("Calculando...")
        self.lbl_chds_filtered.setText("Calculando...")
        self.lbl_size.setText("Calculando...")

        def worker() -> None:
            """Executa as consultas usando uma conexão SQLite própria."""
            conn = None

            try:
                # sqlite3.Connection não deve ser compartilhada entre threads.
                # Abrimos uma conexão independente para o cálculo somente leitura.
                conn = sqlite3.connect(
                    str(self.config.db_path),
                    timeout=30,
                )
                conn.execute("PRAGMA busy_timeout = 30000")
                service = FilterService(conn)

                machine_count = service.get_machine_count(criteria)
                rom_count = service.get_rom_count(criteria)
                chd_count = service.get_chd_count(criteria)
                size_bytes = service.get_estimated_size(criteria)
                unscanned_chds = service.get_unscanned_chd_count(criteria)

                result = {
                    "machine_count": machine_count,
                    "rom_count": rom_count,
                    "chd_count": chd_count,
                    "size_bytes": size_bytes,
                    "unscanned_chds": unscanned_chds,
                }

                self.filter_result_signal.emit(
                    generation,
                    result,
                    None,
                )

            except Exception as exc:
                logger.error(
                    "Erro no cálculo assíncrono dos filtros: %s",
                    exc,
                    exc_info=True,
                )
                self.filter_result_signal.emit(
                    generation,
                    None,
                    str(exc),
                )

            finally:
                if conn is not None:
                    conn.close()

        threading.Thread(
            target=worker,
            name="filter-stats-worker",
            daemon=True,
        ).start()

    def _on_filter_calculation_finished(
        self,
        generation: int,
        result: dict | None,
        error: str | None,
    ) -> None:
        """Aplica ao Qt somente o resultado correspondente ao último filtro."""
        self._filter_calculation_running = False

        # Se o usuário alterou o filtro enquanto a consulta estava rodando,
        # este resultado ficou obsoleto e não pode sobrescrever a tela.
        if generation != self._filter_generation:
            if self._pending_filter_criteria is not None:
                self._filter_timer.start()
            return

        if error is not None or result is None:
            logger.error("Falha ao calcular estatísticas do filtro: %s", error)
            self.lbl_machines.setText("Erro")
            self.lbl_roms_filtered.setText("Erro")
            self.lbl_chds_filtered.setText("Erro")
            self.lbl_size.setText("Erro")
            self._update_excluded_categories_info(
                self.current_criteria.exclude_categories
            )
            return

        self.lbl_machines.setText(str(result["machine_count"]))
        self.lbl_roms_filtered.setText(str(result["rom_count"]))
        self.lbl_chds_filtered.setText(str(result["chd_count"]))

        size_str = self._format_size(result["size_bytes"])

        if result["unscanned_chds"] > 0:
            size_str += (
                "  (⚠ "
                f"{result['unscanned_chds']} CHD(s) sem tamanho lido — "
                "use 'Escanear tamanho dos CHDs')"
            )

        self.lbl_size.setText(size_str)
        self._update_excluded_categories_info(
            self.current_criteria.exclude_categories
        )

        # Caso tenha ocorrido outra alteração enquanto o resultado era
        # aplicado, agenda imediatamente o cálculo da versão mais recente.
        if self._pending_filter_criteria is not None:
            self._filter_timer.start()

    def _apply_filters(self) -> None:
        """
        Agenda o recálculo das estatísticas a partir do estado atual da UI.

        Este método mantém a API interna existente, mas não bloqueia mais a
        interface com consultas SQLite demoradas.
        """
        criteria = self._get_criteria_from_ui()
        self.current_criteria = criteria
        self._filter_generation += 1
        self._pending_filter_generation = self._filter_generation
        self._pending_filter_criteria = criteria
        self._update_excluded_categories_info(criteria.exclude_categories)
        self._filter_timer.start()

    def _get_criteria_from_ui(self) -> FilterCriteria:
        """
        Constrói o FilterCriteria exclusivamente a partir do estado atual
        dos controles da interface.
        """
        excluded_cats = self._get_excluded_categories()
        emulation_status = self._get_selected_status()

        return FilterCriteria(
            categories=[],
            emulation_status=emulation_status,
            include_clones=self.chk_clones.isChecked(),
            include_bios=self.chk_bios.isChecked(),
            include_devices=self.chk_devices.isChecked(),
            include_chd=self.chk_chd.isChecked(),
            arcade_systems=[],
            include_categories=[],
            exclude_categories=excluded_cats,
        )

    def _apply_current_filters(self) -> None:
        """Aplica os filtros após a inicialização da interface."""
        self._apply_filters()

    # ========================================================================
    # IMPORTAÇÃO / REBUILD
    # ========================================================================

    def _sync_database(self) -> None:
        """Inicia a atualização ou reconstrução do banco MAME."""
        if self._import_running:
            QMessageBox.warning(
                self,
                "Aguarde",
                "Uma operação já está em andamento.",
            )
            return

        if (
            not self.config.mame_path
            or not self.config.mame_path.exists()
        ):
            QMessageBox.warning(
                self,
                "Erro",
                (
                    "Selecione o executável MAME na aba "
                    "Diretórios primeiro."
                ),
            )
            return

        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM machine")
        count = cursor.fetchone()[0]

        if count > 0:
            reply = QMessageBox.question(
                self,
                "Atualizar banco",
                (
                    "O banco já contém dados. Deseja recriar do zero "
                    "(perderá dados) ou apenas atualizar?"
                ),
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                defaultButton=QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Cancel:
                return

            if reply == QMessageBox.StandardButton.Yes:
                self._rebuild_database()
                return

        self._import_listxml()

    def _import_listxml(self) -> None:
        """Importa o listxml diretamente do executável MAME."""
        if self._import_running:
            return

        self._import_running = True
        self.setEnabled(False)

        def import_task():
            try:
                self.progress_signal.emit(
                    0,
                    "Detectando versão do MAME...",
                )

                mame = MameExecutable(
                    self.config.mame_path
                )
                version = mame.version

                self.progress_signal.emit(
                    5,
                    "Criando conexão com o banco...",
                )

                conn = sqlite3.connect(
                    str(self.config.db_path)
                )
                conn.row_factory = sqlite3.Row

                def on_progress(
                    count: int,
                    message: str,
                ):
                    self.progress_signal.emit(
                        min(95, 5 + count // 200),
                        message,
                    )

                service = DatabaseService(conn)

                total = service.import_from_executable(
                    mame,
                    progress_callback=on_progress,
                )

                conn.close()

                self.progress_signal.emit(
                    100,
                    "Finalizando...",
                )

                self.finish_signal.emit(
                    True,
                    (
                        "Banco atualizado! "
                        f"Versão: {version} "
                        f"({total} máquinas)"
                    ),
                )

            except Exception as e:
                logger.error(
                    f"Falha na importação: {e}",
                    exc_info=True,
                )

                self.finish_signal.emit(
                    False,
                    f"Erro: {str(e)}",
                )

        threading.Thread(
            target=import_task,
            daemon=True,
        ).start()

    def _rebuild_database(self) -> None:
        """Apaga o banco atual e inicia uma importação limpa."""
        if (
            not self.config.mame_path
            or not self.config.mame_path.exists()
        ):
            QMessageBox.warning(
                self,
                "Erro",
                "Selecione o executável MAME primeiro.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Recriar banco",
            (
                "Isso irá APAGAR todo o banco de dados atual e "
                "recriá-lo do zero.\nDeseja continuar?"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if self.db and self.db.conn:
                self.db.conn.close()
                self.db.conn = None

            import time

            time.sleep(0.2)

            db_file = self.config.db_path

            if db_file.exists():
                db_file.unlink()

            self.db = Database(db_file)
            self.db.connect()

            self.filter_service = FilterService(
                self.db.conn
            )

            self._import_listxml()

        except PermissionError as e:
            QMessageBox.critical(
                self,
                "Erro",
                (
                    "Não foi possível apagar o arquivo do banco "
                    "de dados.\n"
                    "Certifique-se de que nenhum outro programa "
                    "está usando o arquivo.\n"
                    f"Erro: {str(e)}"
                ),
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro",
                f"Falha ao recriar banco: {str(e)}",
            )

    # ========================================================================
    # CALLBACKS DE PROGRESSO
    # ========================================================================

    def _on_progress_update(
        self,
        value: int,
        message: str,
    ) -> None:
        """Atualiza a mensagem de progresso da janela principal."""
        if (
            self.main_window
            and hasattr(self.main_window, "status_bar")
        ):
            self.main_window.status_bar.showMessage(
                message
            )

    def _on_import_finished(
        self,
        success: bool,
        message: str,
    ) -> None:
        """Finaliza uma operação de importação e atualiza a interface."""
        self._import_running = False
        self.setEnabled(True)

        if success:
            self._update_database_info()
            self._load_categories()
            self._load_profiles()
            self._apply_filters()

            self.database_updated.emit()

            QMessageBox.information(
                self,
                "Sucesso",
                message,
            )
        else:
            QMessageBox.critical(
                self,
                "Erro",
                message,
            )

    # ========================================================================
    # CONTROLES UI
    # ========================================================================

    def _update_database_info(self) -> None:
        """Atualiza as informações gerais do banco exibidas na interface."""
        try:
            cursor = self.db.conn.cursor()

            cursor.execute(
                "SELECT version FROM mame_installation "
                "ORDER BY id DESC LIMIT 1"
            )
            row = cursor.fetchone()

            if row:
                self.lbl_mame_version.setText(
                    f"Versão do MAME: {row[0]}"
                )

                cursor.execute(
                    "SELECT COUNT(*) FROM machine"
                )
                machine_count = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM rom"
                )
                rom_count = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM disk"
                )
                chd_count = cursor.fetchone()[0]

                self.lbl_db_status.setText(
                    "Status: banco criado"
                )
                self.lbl_machine_count.setText(
                    f"Máquinas: {machine_count}"
                )
                self.lbl_rom_count.setText(
                    f"ROMs: {rom_count}"
                )
                self.lbl_chd_count.setText(
                    f"CHDs: {chd_count}"
                )

                self._set_controls_enabled(True)

            else:
                self.lbl_mame_version.setText(
                    "Versão do MAME: não detectada"
                )
                self.lbl_db_status.setText(
                    "Status: banco vazio"
                )
                self.lbl_machine_count.setText(
                    "Máquinas: 0"
                )
                self.lbl_rom_count.setText(
                    "ROMs: 0"
                )
                self.lbl_chd_count.setText(
                    "CHDs: 0"
                )

                self._set_controls_enabled(False)

        except Exception as e:
            logger.error(
                f"Erro ao atualizar informações do banco: {e}",
                exc_info=True,
            )

    def _set_controls_enabled(
        self,
        enabled: bool,
    ) -> None:
        """Habilita ou desabilita os controles de filtragem."""
        for cb in self.status_checkboxes.values():
            cb.setEnabled(enabled)

        self.chk_clones.setEnabled(enabled)
        self.chk_bios.setEnabled(enabled)
        self.chk_devices.setEnabled(enabled)
        self.chk_chd.setEnabled(enabled)

        for chip in self.category_chips.values():
            chip.setEnabled(enabled)

    # ========================================================================
    # PERFIS: CRUD
    # ========================================================================

    def _create_new_profile(self) -> None:
        """Cria um novo perfil usando os critérios atuais da interface."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Novo Perfil")

        layout = QVBoxLayout(dialog)

        form = QFormLayout()

        name_edit = QLineEdit()
        name_edit.setPlaceholderText(
            "Nome do perfil"
        )

        desc_edit = QLineEdit()
        desc_edit.setPlaceholderText(
            "Descrição (opcional)"
        )

        form.addRow("Nome:", name_edit)
        form.addRow("Descrição:", desc_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        name = name_edit.text().strip()

        if not name:
            QMessageBox.warning(
                self,
                "Aviso",
                "O nome do perfil é obrigatório.",
            )
            return

        profile = FilterProfile(
            name=name,
            description=desc_edit.text().strip(),
            criteria=self._get_criteria_from_ui(),
        )

        self.filter_service.save_profile(profile)

        self._load_profiles()

        idx = self.profile_combo.findData(
            profile.id
        )

        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)

        QMessageBox.information(
            self,
            "Sucesso",
            f"Perfil '{name}' salvo.",
        )

    def _save_current_profile(self) -> None:
        """Atualiza o perfil selecionado com os critérios atuais."""
        idx = self.profile_combo.currentIndex()

        if idx <= 0:
            QMessageBox.warning(
                self,
                "Aviso",
                "Nenhum perfil selecionado.",
            )
            return

        profile_id = self.profile_combo.itemData(idx)

        if not profile_id:
            return

        profile = next(
            (
                p
                for p in self.profiles
                if p.id == profile_id
            ),
            None,
        )

        if not profile:
            return

        profile.criteria = self._get_criteria_from_ui()

        self.filter_service.save_profile(profile)

        QMessageBox.information(
            self,
            "Sucesso",
            f"Perfil '{profile.name}' atualizado.",
        )

    def _delete_profile(self) -> None:
        """Exclui o perfil atualmente selecionado."""
        idx = self.profile_combo.currentIndex()

        if idx <= 0:
            return

        profile_id = self.profile_combo.itemData(idx)

        if not profile_id:
            return

        profile = next(
            (
                p
                for p in self.profiles
                if p.id == profile_id
            ),
            None,
        )

        if not profile:
            return

        reply = QMessageBox.question(
            self,
            "Confirmar",
            f"Excluir o perfil '{profile.name}'?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.filter_service.delete_profile(
                profile_id
            )
            self._load_profiles()

            QMessageBox.information(
                self,
                "Sucesso",
                "Perfil excluído.",
            )
