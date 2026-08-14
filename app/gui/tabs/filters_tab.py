"""Aba de filtragem de ROMs e gerenciamento de categorias."""
import threading
import logging
import sqlite3
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QCheckBox, QComboBox,
    QMessageBox, QScrollArea, QLineEdit,
    QDialog, QDialogButtonBox, QFileDialog, QGridLayout, QSplitter,
    QSizePolicy
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
    # --- Classe interna para chip de 2 estados (normal/excluir) com altura fixa ---
    class CategoryChip(QPushButton):
        STATE_NORMAL = 0
        STATE_EXCLUDE = 1

        def __init__(self, category_name, display_name, count, parent=None):
            super().__init__(f"{display_name} ({count})", parent)
            self.category_name = category_name
            self.state = self.STATE_NORMAL
            self.setCheckable(False)
            self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
            self.setFixedHeight(20)  # Altura fixa para todos os botões
            self.clicked.connect(self.toggle_state)
            self.update_style()

        def toggle_state(self):
            self.state = self.STATE_EXCLUDE if self.state == self.STATE_NORMAL else self.STATE_NORMAL
            self.update_style()
            if self.parent() and hasattr(self.parent(), 'on_category_changed'):
                self.parent().on_category_changed(self.category_name, self.state)

        def update_style(self):
            # Estilo compacto com altura reduzida
            base_style = "border: 1px solid #888; border-radius: 3px; padding: 0px 4px; font-size: 8pt;"
            if self.state == self.STATE_NORMAL:
                self.setStyleSheet(f"background-color: #e0e0e0; color: black; {base_style}")
            else:  # EXCLUDE
                self.setStyleSheet(f"background-color: #ff4d4d; color: white; {base_style}")

        def set_state(self, state):
            self.state = state
            self.update_style()

    filters_changed = Signal()
    database_updated = Signal()
    progress_signal = Signal(int, str)
    finish_signal = Signal(bool, str)

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

        self.progress_signal.connect(self._on_progress_update)
        self.finish_signal.connect(self._on_import_finished)

        self._setup_ui()
        self._load_categories()
        self._load_profiles()
        self._update_database_info()
        QTimer.singleShot(100, self._apply_current_filters)

    def _setup_ui(self):
        if self.layout():
            old_layout = self.layout()
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        outer_layout = QVBoxLayout(self)
        self.setLayout(outer_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)

        # ---------- Banco de Dados ----------
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
        db_buttons_layout.addWidget(btn_sync)

        btn_import_cat = QPushButton("Importar categorias (catver.ini)")
        btn_import_cat.clicked.connect(self._import_categories)
        db_buttons_layout.addWidget(btn_import_cat)

        btn_scan_chd = QPushButton("Escanear tamanho dos CHDs")
        btn_scan_chd.clicked.connect(self._scan_chd_sizes)
        db_buttons_layout.addWidget(btn_scan_chd)

        db_layout.addRow(db_buttons_layout)
        layout.addWidget(grp_db)

        # ---------- Perfis ----------
        grp_profiles = QGroupBox("Perfis de Filtro")
        prof_layout = QVBoxLayout()
        grp_profiles.setLayout(prof_layout)

        hbox_profiles = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)
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

        # ---------- Estado de Emulação ----------
        grp_status = QGroupBox("Estado de Emulação")
        status_layout = QHBoxLayout()
        grp_status.setLayout(status_layout)

        self.status_checkboxes = {}
        for value, label in [("working", "Working"), ("imperfect", "Imperfect"), ("not_working", "Not Working")]:
            cb = QCheckBox(label)
            cb.setChecked(False)
            cb.stateChanged.connect(self._on_status_changed)
            self.status_checkboxes[value] = cb
            status_layout.addWidget(cb)

        status_layout.addStretch()
        layout.addWidget(grp_status)

        # ---------- Opções ----------
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
        self.chk_chd.setToolTip("Desmarque para excluir máquinas que possuem CHD.")
        options_layout.addWidget(self.chk_chd)

        options_layout.addStretch()
        layout.addWidget(grp_options)

        # ---------- Informações do Filtro ----------
        grp_info = QGroupBox("Informações do Filtro")
        info_layout = QFormLayout()
        grp_info.setLayout(info_layout)

        self.lbl_machines = QLabel("0")
        self.lbl_roms_filtered = QLabel("0")
        self.lbl_chds_filtered = QLabel("0")
        self.lbl_size = QLabel("0 MB")

        info_layout.addRow("Máquinas:", self.lbl_machines)
        info_layout.addRow("ROMs:", self.lbl_roms_filtered)
        info_layout.addRow("CHDs:", self.lbl_chds_filtered)
        info_layout.addRow("Tamanho estimado:", self.lbl_size)

        layout.addWidget(grp_info)

        # ---------- Categorias (toggle vermelho/cinza) ----------
        grp_cats = QGroupBox("Categorias")
        cats_layout = QVBoxLayout()
        grp_cats.setLayout(cats_layout)

        legend = QLabel("Clique para excluir (vermelho) ou voltar ao normal (cinza)")
        legend.setAlignment(Qt.AlignCenter)
        cats_layout.addWidget(legend)

        cat_scroll = QScrollArea()
        cat_scroll.setWidgetResizable(True)
        cat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cat_scroll.setMinimumHeight(800)

        cat_container = QWidget()
        self.cat_grid = QGridLayout(cat_container)
        self.cat_grid.setContentsMargins(2, 2, 2, 2)
        self.cat_grid.setSpacing(2)

        cat_scroll.setWidget(cat_container)
        cats_layout.addWidget(cat_scroll)

        layout.addWidget(grp_cats)

        layout.addStretch()
        scroll.setWidget(container)

        # ---------- Splitter ----------
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

    def _load_categories(self):
        # Limpa chips existentes
        for chip in self.category_chips.values():
            self.cat_grid.removeWidget(chip)
            chip.deleteLater()
        self.category_chips.clear()

        # Obtém todas as categorias do banco
        all_cats = self.filter_service.get_categories_with_counts()
        if not all_cats:
            self.filter_service.seed_default_categories()
            all_cats = self.filter_service.get_categories_with_counts()

        if not all_cats:
            return

        # Filtra as categorias indesejadas (não mostrar)
        unwanted = {'bios', 'devices', 'chd', 'mature', 'mahjong', 'screenless', 'musical'}
        filtered_cats = [cat for cat in all_cats if cat['name'] not in unwanted]

        cols = 10
        for idx, cat in enumerate(filtered_cats):
            row = idx // cols
            col = idx % cols
            chip = self.CategoryChip(cat['name'], cat['display_name'], cat['count'], self)
            self.cat_grid.addWidget(chip, row, col)
            self.category_chips[cat['name']] = chip

    def _get_excluded_categories(self) -> List[str]:
        return [name for name, chip in self.category_chips.items() if chip.state == self.CategoryChip.STATE_EXCLUDE]

    def on_category_changed(self, category_name: str, state: int):
        self._on_filters_changed()

    # ========================================================================
    # EMULAÇÃO
    # ========================================================================

    def _get_selected_status(self) -> List[str]:
        return [value for value, cb in self.status_checkboxes.items() if cb.isChecked()]

    def _on_status_changed(self):
        self._on_filters_changed()

    # ========================================================================
    # IMPORTAÇÃO CATVER
    # ========================================================================

    def _import_categories(self):
        if not self.config.mame_path or not self.config.mame_path.exists():
            QMessageBox.warning(self, "Erro", "Selecione o executável MAME primeiro.")
            return

        default_ini = self.config.mame_path.parent / "folders" / "catver.ini"
        if not default_ini.exists():
            reply = QMessageBox.question(
                self,
                "Arquivo não encontrado",
                f"O arquivo padrão (catver.ini) não foi encontrado em:\n{default_ini}\n\nDeseja selecionar manualmente?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar catver.ini",
                "",
                "Arquivos INI (*.ini);;Todos os arquivos (*)"
            )
            if not file_path:
                return
            ini_path = Path(file_path)
        else:
            ini_path = default_ini

        try:
            categorias, maquinas, imported = self.filter_service.import_categories_from_catver(ini_path)
            msg = f"Categorias importadas: {categorias}\nMáquinas associadas: {maquinas}\n"
            if imported:
                msg += "\nCategorias criadas:\n" + ", ".join(sorted(imported)[:15])
                if len(imported) > 15:
                    msg += f" ... (+{len(imported)-15} outras)"
            QMessageBox.information(self, "Importação concluída", msg)
            self._load_categories()
            self._apply_filters()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao importar categorias:\n{str(e)}")

    # ========================================================================
    # SCAN CHD
    # ========================================================================

    def _scan_chd_sizes(self):
        if self._import_running:
            QMessageBox.warning(self, "Aguarde", "Uma operação já está em andamento.")
            return

        if not self.config.ini_path or not self.config.ini_path.exists():
            QMessageBox.warning(
                self, "Erro",
                "Selecione o mame.ini na aba Diretórios primeiro."
            )
            return

        try:
            ini_service = IniService(self.config.ini_path)
            rompaths = ini_service.get_paths("rompath")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao ler mame.ini:\n{e}")
            return

        if not rompaths:
            QMessageBox.warning(self, "Aviso", "Nenhum 'rompath' configurado no mame.ini.")
            return

        self._import_running = True
        self.setEnabled(False)
        self.progress_signal.emit(0, f"Escaneando CHDs em {len(rompaths)} pasta(s)...")

        def scan_task():
            try:
                chd_sizes = scan_chd_sizes(rompaths)
                self.progress_signal.emit(80, f"{len(chd_sizes)} CHD(s) encontrados, salvando...")

                conn = sqlite3.connect(str(self.config.db_path))
                conn.row_factory = sqlite3.Row
                service = DatabaseService(conn)
                updated = service.update_chd_sizes(chd_sizes)
                conn.close()

                self.progress_signal.emit(100, "Concluído.")
                self.finish_signal.emit(
                    True,
                    f"Scanner de CHD concluído.\n"
                    f"{len(chd_sizes)} arquivo(s) .chd encontrados.\n"
                    f"{updated} registro(s) atualizados."
                )
            except Exception as e:
                logger.error(f"Falha ao escanear CHDs: {e}", exc_info=True)
                self.finish_signal.emit(False, f"Erro ao escanear CHDs: {e}")

        threading.Thread(target=scan_task, daemon=True).start()

    # ========================================================================
    # PERFIS
    # ========================================================================

    def _load_profiles(self):
        self.profile_combo.clear()
        self.profiles = self.filter_service.get_profiles()
        self.profile_combo.addItem("(nenhum)", None)
        for prof in self.profiles:
            self.profile_combo.addItem(prof.name, prof.id)
        default = self.filter_service.get_default_profile()
        if default:
            idx = self.profile_combo.findData(default.id)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)

    def _on_profile_selected(self, index: int):
        if index <= 0:
            return
        profile_id = self.profile_combo.itemData(index)
        if not profile_id:
            return
        profile = next((p for p in self.profiles if p.id == profile_id), None)
        if profile:
            self._load_criteria(profile.criteria)

    def _load_criteria(self, criteria: FilterCriteria):
        for value, cb in self.status_checkboxes.items():
            cb.setChecked(value in criteria.emulation_status)

        self.chk_clones.setChecked(criteria.include_clones)
        self.chk_bios.setChecked(criteria.include_bios)
        self.chk_devices.setChecked(criteria.include_devices)
        self.chk_chd.setChecked(criteria.include_chd)

        exclude_set = set(criteria.exclude_categories)
        for name, chip in self.category_chips.items():
            if name in exclude_set:
                chip.set_state(self.CategoryChip.STATE_EXCLUDE)
            else:
                chip.set_state(self.CategoryChip.STATE_NORMAL)

        self._apply_filters()

    # ========================================================================
    # FILTROS
    # ========================================================================

    def _on_filters_changed(self):
        self._apply_filters()
        self.filters_changed.emit()

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes >= 1_073_741_824:
            return f"{size_bytes / 1_073_741_824:.2f} GB"
        if size_bytes >= 1_048_576:
            return f"{size_bytes / 1_048_576:.2f} MB"
        if size_bytes >= 1024:
            return f"{size_bytes / 1024:.2f} KB"
        return f"{size_bytes} B"

    def _apply_filters(self):
        try:
            criteria = self._get_criteria_from_ui()
            self.current_criteria = criteria

            machine_count = self.filter_service.get_machine_count(criteria)
            rom_count = self.filter_service.get_rom_count(criteria)
            chd_count = self.filter_service.get_chd_count(criteria)
            size_bytes = self.filter_service.get_estimated_size(criteria)
            unscanned_chds = self.filter_service.get_unscanned_chd_count(criteria)

            self.lbl_machines.setText(str(machine_count))
            self.lbl_roms_filtered.setText(str(rom_count))
            self.lbl_chds_filtered.setText(str(chd_count))

            size_str = self._format_size(size_bytes)
            if unscanned_chds > 0:
                size_str += f"  (⚠ {unscanned_chds} CHD(s) sem tamanho lido)"
            self.lbl_size.setText(size_str)

        except Exception as e:
            logger.error(f"Erro ao aplicar filtros: {e}", exc_info=True)
            self.lbl_machines.setText("Erro")
            self.lbl_roms_filtered.setText("Erro")
            self.lbl_chds_filtered.setText("Erro")
            self.lbl_size.setText("Erro")

    def _get_criteria_from_ui(self) -> FilterCriteria:
        return FilterCriteria(
            categories=[],
            emulation_status=self._get_selected_status(),
            include_clones=self.chk_clones.isChecked(),
            include_bios=self.chk_bios.isChecked(),
            include_devices=self.chk_devices.isChecked(),
            include_chd=self.chk_chd.isChecked(),
            arcade_systems=[],
            include_categories=[],
            exclude_categories=self._get_excluded_categories()
        )

    def _apply_current_filters(self):
        self._apply_filters()

    # ========================================================================
    # IMPORTAÇÃO/REBUILD
    # ========================================================================

    def _sync_database(self):
        if self._import_running:
            QMessageBox.warning(self, "Aguarde", "Uma importação já está em andamento.")
            return
        if not self.config.mame_path or not self.config.mame_path.exists():
            QMessageBox.warning(self, "Erro", "Selecione o executável MAME na aba Diretórios primeiro.")
            return

        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM machine")
        count = cursor.fetchone()[0]
        if count > 0:
            reply = QMessageBox.question(
                self,
                "Atualizar banco",
                "O banco já contém dados. Deseja recriar do zero (perderá dados) ou apenas atualizar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                defaultButton=QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Yes:
                self._rebuild_database()
                return
        self._import_listxml()

    def _import_listxml(self):
        if self._import_running:
            return

        self._import_running = True
        self.setEnabled(False)

        def import_task():
            try:
                self.progress_signal.emit(0, "Detectando versão do MAME...")
                mame = MameExecutable(self.config.mame_path)
                version = mame.version

                self.progress_signal.emit(5, "Criando conexão com o banco...")
                conn = sqlite3.connect(str(self.config.db_path))
                conn.row_factory = sqlite3.Row

                def on_progress(count: int, message: str):
                    self.progress_signal.emit(min(95, 5 + count // 200), message)

                service = DatabaseService(conn)
                total = service.import_from_executable(mame, progress_callback=on_progress)
                conn.close()

                self.progress_signal.emit(100, "Finalizando...")
                self.finish_signal.emit(True, f"Banco atualizado! Versão: {version} ({total} máquinas)")

            except Exception as e:
                logger.error(f"Falha na importação: {e}", exc_info=True)
                self.finish_signal.emit(False, f"Erro: {str(e)}")

        threading.Thread(target=import_task, daemon=True).start()

    def _rebuild_database(self):
        if not self.config.mame_path or not self.config.mame_path.exists():
            QMessageBox.warning(self, "Erro", "Selecione o executável MAME primeiro.")
            return

        reply = QMessageBox.question(
            self,
            "Recriar banco",
            "Isso irá APAGAR todo o banco de dados atual e recriá-lo do zero.\nDeseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
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
            self.filter_service = FilterService(self.db.conn)

            self._import_listxml()

        except PermissionError as e:
            QMessageBox.critical(
                self,
                "Erro",
                f"Não foi possível apagar o arquivo do banco de dados.\n"
                f"Certifique-se de que nenhum outro programa está usando o arquivo.\n"
                f"Erro: {str(e)}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha ao recriar banco: {str(e)}")

    # ========================================================================
    # CALLBACKS
    # ========================================================================

    def _on_progress_update(self, value: int, message: str):
        if self.main_window and hasattr(self.main_window, 'status_bar'):
            self.main_window.status_bar.showMessage(message)

    def _on_import_finished(self, success: bool, message: str):
        self._import_running = False
        self.setEnabled(True)

        if success:
            self._update_database_info()
            self._load_categories()
            self._load_profiles()
            self._apply_filters()
            QMessageBox.information(self, "Sucesso", message)
        else:
            QMessageBox.critical(self, "Erro", message)

    # ========================================================================
    # CONTROLES UI
    # ========================================================================

    def _update_database_info(self):
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT version FROM mame_installation ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                self.lbl_mame_version.setText(f"Versão do MAME: {row[0]}")
                cursor.execute("SELECT COUNT(*) FROM machine")
                machine_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM rom")
                rom_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM disk")
                chd_count = cursor.fetchone()[0]
                self.lbl_db_status.setText("Status: banco criado")
                self.lbl_machine_count.setText(f"Máquinas: {machine_count}")
                self.lbl_rom_count.setText(f"ROMs: {rom_count}")
                self.lbl_chd_count.setText(f"CHDs: {chd_count}")
                self._set_controls_enabled(True)
            else:
                self.lbl_mame_version.setText("Versão do MAME: não detectada")
                self.lbl_db_status.setText("Status: banco vazio")
                self.lbl_machine_count.setText("Máquinas: 0")
                self.lbl_rom_count.setText("ROMs: 0")
                self.lbl_chd_count.setText("CHDs: 0")
                self._set_controls_enabled(False)
        except Exception as e:
            logger.error(f"Erro ao atualizar informações do banco: {e}")

    def _set_controls_enabled(self, enabled: bool):
        for cb in self.status_checkboxes.values():
            cb.setEnabled(enabled)
        self.chk_clones.setEnabled(enabled)
        self.chk_bios.setEnabled(enabled)
        self.chk_devices.setEnabled(enabled)
        self.chk_chd.setEnabled(enabled)
        for chip in self.category_chips.values():
            chip.setEnabled(enabled)

    # ========================================================================
    # PERFIS CRUD
    # ========================================================================

    def _create_new_profile(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Novo Perfil")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("Nome do perfil")
        desc_edit = QLineEdit()
        desc_edit.setPlaceholderText("Descrição (opcional)")
        form.addRow("Nome:", name_edit)
        form.addRow("Descrição:", desc_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        name = name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Aviso", "O nome do perfil é obrigatório.")
            return

        profile = FilterProfile(
            name=name,
            description=desc_edit.text().strip(),
            criteria=self.current_criteria
        )
        self.filter_service.save_profile(profile)
        self._load_profiles()
        idx = self.profile_combo.findData(profile.id)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)
        QMessageBox.information(self, "Sucesso", f"Perfil '{name}' salvo.")

    def _save_current_profile(self):
        idx = self.profile_combo.currentIndex()
        if idx <= 0:
            QMessageBox.warning(self, "Aviso", "Nenhum perfil selecionado.")
            return
        profile_id = self.profile_combo.itemData(idx)
        if not profile_id:
            return
        profile = next((p for p in self.profiles if p.id == profile_id), None)
        if not profile:
            return
        profile.criteria = self._get_criteria_from_ui()
        self.filter_service.save_profile(profile)
        QMessageBox.information(self, "Sucesso", f"Perfil '{profile.name}' atualizado.")

    def _delete_profile(self):
        idx = self.profile_combo.currentIndex()
        if idx <= 0:
            return
        profile_id = self.profile_combo.itemData(idx)
        if not profile_id:
            return
        profile = next((p for p in self.profiles if p.id == profile_id), None)
        if not profile:
            return
        reply = QMessageBox.question(
            self, "Confirmar",
            f"Excluir o perfil '{profile.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.filter_service.delete_profile(profile_id)
            self._load_profiles()
            QMessageBox.information(self, "Sucesso", "Perfil excluído.")