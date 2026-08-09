"""Aba de filtragem de ROMs."""
import threading
import logging
import sqlite3
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QCheckBox, QComboBox, QListWidget,
    QListWidgetItem, QMessageBox, QScrollArea, QLineEdit,
    QDialog, QDialogButtonBox, QProgressBar
)

from app.core.services.filter_service import FilterService
from app.core.models.filter_profile import FilterCriteria, FilterProfile
from app.database.database import Database
from app.config.app_config import AppConfig
from app.mame.executable import MameExecutable
from app.core.services.database_service import DatabaseService

logger = logging.getLogger(__name__)


class FiltersTab(QWidget):
    """Aba para configuração de filtros e gerenciamento do banco de dados."""

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

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        form_layout = QVBoxLayout(container)
        form_layout.setSpacing(15)

        # --- Banco de Dados ---
        grp_db = QGroupBox("Banco de Dados do MAME")
        db_layout = QFormLayout()
        grp_db.setLayout(db_layout)

        self.lbl_mame_version = QLabel("Versão do MAME: não detectada")
        self.lbl_db_status = QLabel("Status: banco não criado")
        self.lbl_machine_count = QLabel("Máquinas: 0")
        self.lbl_rom_count = QLabel("ROMs: 0")

        db_layout.addRow(self.lbl_mame_version)
        db_layout.addRow(self.lbl_db_status)
        db_layout.addRow(self.lbl_machine_count)
        db_layout.addRow(self.lbl_rom_count)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        db_layout.addRow(self.progress_bar)

        btn_import = QPushButton("Importar listxml do MAME")
        btn_import.clicked.connect(self._import_listxml)
        btn_import.setToolTip("Recria o banco de dados importando todas as informações do MAME via -listxml.")
        db_layout.addRow(btn_import)

        btn_rebuild = QPushButton("Recriar banco (forçar)")
        btn_rebuild.clicked.connect(self._rebuild_database)
        btn_rebuild.setToolTip("Apaga o banco atual e recria do zero a partir do listxml.")
        db_layout.addRow(btn_rebuild)

        layout.addWidget(grp_db)

        # --- Perfis ---
        grp_profiles = QGroupBox("Perfis de Filtro")
        prof_layout = QVBoxLayout()
        grp_profiles.setLayout(prof_layout)

        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)

        btn_new = QPushButton("Novo Perfil")
        btn_new.clicked.connect(self._create_new_profile)
        btn_save = QPushButton("Salvar Perfil")
        btn_save.clicked.connect(self._save_current_profile)
        btn_delete = QPushButton("Excluir Perfil")
        btn_delete.clicked.connect(self._delete_profile)

        hbox_profiles = QHBoxLayout()
        hbox_profiles.addWidget(self.profile_combo, stretch=1)
        hbox_profiles.addWidget(btn_new)
        hbox_profiles.addWidget(btn_save)
        hbox_profiles.addWidget(btn_delete)
        prof_layout.addLayout(hbox_profiles)

        layout.addWidget(grp_profiles)

        # --- Categorias com checkbox ---
        grp_cats = QGroupBox("Categorias")
        cats_layout = QVBoxLayout()
        grp_cats.setLayout(cats_layout)

        self.cat_list = QListWidget()
        self.cat_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.cat_list.itemChanged.connect(self._on_category_toggled)
        cats_layout.addWidget(self.cat_list)

        layout.addWidget(grp_cats)

        # --- Estado de Emulação ---
        grp_status = QGroupBox("Estado de Emulação")
        status_layout = QFormLayout()
        grp_status.setLayout(status_layout)

        self.status_combo = QComboBox()
        self.status_combo.addItem("ALL", "all")
        self.status_combo.addItem("WORKING", "working")
        self.status_combo.addItem("WORKING + IMPERFECT", "working_imperfect")
        self.status_combo.addItem("IMPERFECT", "imperfect")
        self.status_combo.addItem("IMPERFECT + NOT WORKING", "imperfect_notworking")
        self.status_combo.addItem("NOT WORKING", "not_working")
        self.status_combo.setToolTip("Seleção cumulativa.")
        self.status_combo.currentIndexChanged.connect(self._on_filters_changed)
        status_layout.addRow("Status:", self.status_combo)

        layout.addWidget(grp_status)

        # --- Opções ---
        grp_options = QGroupBox("Opções")
        options_layout = QFormLayout()
        grp_options.setLayout(options_layout)

        self.chk_clones = QCheckBox("Incluir Clones")
        self.chk_clones.setChecked(True)
        self.chk_clones.toggled.connect(self._on_filters_changed)
        options_layout.addRow(self.chk_clones)

        self.chk_bios = QCheckBox("Incluir BIOS")
        self.chk_bios.setChecked(True)
        self.chk_bios.toggled.connect(self._on_filters_changed)
        options_layout.addRow(self.chk_bios)

        self.chk_devices = QCheckBox("Incluir Devices")
        self.chk_devices.setChecked(True)
        self.chk_devices.toggled.connect(self._on_filters_changed)
        options_layout.addRow(self.chk_devices)

        self.chk_chd = QCheckBox("Incluir CHD")
        self.chk_chd.setChecked(True)
        self.chk_chd.toggled.connect(self._on_filters_changed)
        options_layout.addRow(self.chk_chd)

        layout.addWidget(grp_options)

        # --- Informações ---
        grp_info = QGroupBox("Informações do Filtro")
        info_layout = QFormLayout()
        grp_info.setLayout(info_layout)

        self.lbl_machines = QLabel("0")
        self.lbl_roms_filtered = QLabel("0")
        self.lbl_size = QLabel("0 MB")
        info_layout.addRow("Máquinas:", self.lbl_machines)
        info_layout.addRow("ROMs:", self.lbl_roms_filtered)
        info_layout.addRow("Tamanho estimado:", self.lbl_size)

        layout.addWidget(grp_info)

        # --- Aplicar Filtros ---
        btn_apply = QPushButton("Aplicar Filtros")
        btn_apply.clicked.connect(self._apply_filters)
        btn_apply.setStyleSheet("font-weight: bold; padding: 8px;")
        layout.addWidget(btn_apply)

        layout.addStretch()

        scroll.setWidget(container)
        layout.addWidget(scroll)

        self._set_controls_enabled(False)

    # ============================
    # CATEGORIAS COM CHECKBOX
    # ============================

    def _load_categories(self):
        self.cat_list.clear()
        categories = self.filter_service.get_categories()
        for cat in categories:
            item = QListWidgetItem(cat)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.cat_list.addItem(item)

    def _on_category_toggled(self, item):
        self._on_filters_changed()

    # ============================
    # DEMAIS MÉTODOS (sem alterações, apenas mantidos)
    # ============================

    def _update_database_info(self):
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT version, executable_path FROM mame_installation ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                self.lbl_mame_version.setText(f"Versão do MAME: {row[0]}")
                cursor.execute("SELECT COUNT(*) FROM machine")
                machine_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM rom")
                rom_count = cursor.fetchone()[0]
                self.lbl_db_status.setText("Status: banco criado")
                self.lbl_machine_count.setText(f"Máquinas: {machine_count}")
                self.lbl_rom_count.setText(f"ROMs: {rom_count}")
                self._set_controls_enabled(True)
            else:
                self.lbl_mame_version.setText("Versão do MAME: não detectada")
                self.lbl_db_status.setText("Status: banco vazio")
                self.lbl_machine_count.setText("Máquinas: 0")
                self.lbl_rom_count.setText("ROMs: 0")
                self._set_controls_enabled(False)
        except Exception as e:
            logger.error(f"Erro ao atualizar informações do banco: {e}")
            self.lbl_db_status.setText(f"Status: erro - {str(e)[:50]}")
            self._set_controls_enabled(False)

    def _set_controls_enabled(self, enabled: bool):
        self.cat_list.setEnabled(enabled)
        self.status_combo.setEnabled(enabled)
        self.chk_clones.setEnabled(enabled)
        self.chk_bios.setEnabled(enabled)
        self.chk_devices.setEnabled(enabled)
        self.chk_chd.setEnabled(enabled)

    def _import_listxml(self):
        if self._import_running:
            QMessageBox.warning(self, "Aguarde", "Uma importação já está em andamento.")
            return

        if not self.config.mame_path or not self.config.mame_path.exists():
            QMessageBox.warning(self, "Erro", "Selecione o executável MAME na aba Diretórios primeiro.")
            return

        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM machine")
        if cursor.fetchone()[0] > 0:
            reply = QMessageBox.question(
                self,
                "Atualizar banco",
                "O banco já contém dados. Deseja atualizar com o listxml mais recente?\n"
                "Isso adicionará novas máquinas e atualizará as existentes.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self._import_running = True
        self.setEnabled(False)

        def import_task():
            try:
                logger.info("=== INICIANDO IMPORTAÇÃO DO LISTXML ===")
                self.progress_signal.emit(10, "Obtendo listxml do MAME...")
                mame = MameExecutable(self.config.mame_path)
                xml = mame.get_listxml()
                logger.info(f"listxml obtido. Tamanho: {len(xml)} caracteres.")
                version = mame.version
                logger.info(f"Versão do MAME detectada: {version}")

                self.progress_signal.emit(30, "Criando conexão com o banco...")
                db_path = self.config.db_path
                logger.info(f"Conectando ao banco: {db_path}")
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                logger.info("Conexão criada.")

                self.progress_signal.emit(50, "Importando dados para o banco...")
                logger.info("Iniciando importação...")
                service = DatabaseService(conn)
                service.import_listxml(xml, str(self.config.mame_path), version)
                conn.close()
                logger.info("Importação concluída com sucesso.")

                self.progress_signal.emit(100, "Finalizando...")
                self.finish_signal.emit(True, f"Banco de dados atualizado com sucesso!\nVersão: {version}")

            except Exception as e:
                logger.error(f"Falha na importação: {e}", exc_info=True)
                self.finish_signal.emit(False, f"Falha na importação:\n{str(e)}")

        thread = threading.Thread(target=import_task, daemon=True)
        thread.start()

    def _on_progress_update(self, value: int, message: str):
        self.progress_bar.setValue(value)
        if self.main_window and hasattr(self.main_window, 'status_bar'):
            self.main_window.status_bar.showMessage(message)

    def _on_import_finished(self, success: bool, message: str):
        self._import_running = False
        self.setEnabled(True)
        self.progress_bar.setVisible(False)

        if success:
            self._update_database_info()
            self._load_categories()
            self._apply_filters()
            QMessageBox.information(self, "Sucesso", message)
        else:
            QMessageBox.critical(self, "Erro", message)

    def _rebuild_database(self):
        if not self.config.mame_path or not self.config.mame_path.exists():
            QMessageBox.warning(self, "Erro", "Selecione o executável MAME primeiro.")
            return

        reply = QMessageBox.question(
            self,
            "Recriar banco",
            "Isso irá APAGAR todo o banco de dados atual e recriá-lo do zero a partir do listxml.\n"
            "O processo pode levar alguns minutos.\n\n"
            "Deseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.db.conn.close()
        if self.config.db_path.exists():
            self.config.db_path.unlink()

        self.db = Database(self.config.db_path)
        self.db.connect()
        self.filter_service = FilterService(self.db.conn)
        self._import_listxml()

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
        # Aplica checkboxes
        for i in range(self.cat_list.count()):
            item = self.cat_list.item(i)
            item.setCheckState(Qt.CheckState.Checked if item.text() in criteria.categories else Qt.CheckState.Unchecked)

        # Status
        if "not_working" in criteria.emulation_status and "imperfect" in criteria.emulation_status:
            status_key = "imperfect_notworking"
        elif "imperfect" in criteria.emulation_status and "working" in criteria.emulation_status:
            status_key = "working_imperfect"
        elif "not_working" in criteria.emulation_status:
            status_key = "not_working"
        elif "imperfect" in criteria.emulation_status:
            status_key = "imperfect"
        elif "working" in criteria.emulation_status:
            status_key = "working"
        else:
            status_key = "all"

        for i in range(self.status_combo.count()):
            if self.status_combo.itemData(i) == status_key:
                self.status_combo.setCurrentIndex(i)
                break

        self.chk_clones.setChecked(criteria.include_clones)
        self.chk_bios.setChecked(criteria.include_bios)
        self.chk_devices.setChecked(criteria.include_devices)
        self.chk_chd.setChecked(criteria.include_chd)

        self._apply_filters()

    def _on_filters_changed(self):
        self._apply_filters()
        self.filters_changed.emit()

    def _apply_filters(self):
        criteria = self._get_criteria_from_ui()
        self.current_criteria = criteria

        machine_count = self.filter_service.get_machine_count(criteria)
        rom_count = self.filter_service.get_rom_count(criteria)
        size_bytes = self.filter_service.get_estimated_size(criteria)

        self.lbl_machines.setText(str(machine_count))
        self.lbl_roms_filtered.setText(str(rom_count))

        if size_bytes >= 1_073_741_824:
            size_str = f"{size_bytes / 1_073_741_824:.2f} GB"
        elif size_bytes >= 1_048_576:
            size_str = f"{size_bytes / 1_048_576:.2f} MB"
        elif size_bytes >= 1024:
            size_str = f"{size_bytes / 1024:.2f} KB"
        else:
            size_str = f"{size_bytes} B"
        self.lbl_size.setText(size_str)

    def _get_criteria_from_ui(self) -> FilterCriteria:
        categories = []
        for i in range(self.cat_list.count()):
            item = self.cat_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                categories.append(item.text())

        status_data = self.status_combo.currentData()
        emulation_status = []
        if status_data == "working":
            emulation_status = ["working"]
        elif status_data == "working_imperfect":
            emulation_status = ["working", "imperfect"]
        elif status_data == "imperfect":
            emulation_status = ["imperfect"]
        elif status_data == "imperfect_notworking":
            emulation_status = ["imperfect", "not_working"]
        elif status_data == "not_working":
            emulation_status = ["not_working"]

        return FilterCriteria(
            categories=categories,
            emulation_status=emulation_status,
            include_clones=self.chk_clones.isChecked(),
            include_bios=self.chk_bios.isChecked(),
            include_devices=self.chk_devices.isChecked(),
            include_chd=self.chk_chd.isChecked(),
            arcade_systems=[]
        )

    def _apply_current_filters(self):
        self._apply_filters()

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
        QMessageBox.information(self, "Sucesso", f"Perfil '{name}' salvo com sucesso.")

    def _save_current_profile(self):
        idx = self.profile_combo.currentIndex()
        if idx <= 0:
            QMessageBox.warning(self, "Aviso", "Nenhum perfil selecionado para salvar.")
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
            QMessageBox.information(self, "Sucesso", f"Perfil '{profile.name}' excluído.")