"""Layout configurável da tela de filtros e scan."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .filter_profiles_page import FilterProfilesPage as _BaseFilterProfilesPage


class FilterProfilesPage(_BaseFilterProfilesPage):
    """Versão da tela com todas as seções verticalmente redimensionáveis."""

    def _catalog_panel(self) -> QWidget:
        box = super()._catalog_panel()
        # Substitui o layout interno rígido por um splitter entre catálogos e perfis.
        layout = box.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.setMinimumHeight(220)

        catalogs = QWidget()
        catalogs_layout = QVBoxLayout(catalogs)
        catalogs_layout.setContentsMargins(0, 0, 0, 0)
        catalogs_layout.addWidget(self.source_tree)

        profiles = QWidget()
        profiles_layout = QVBoxLayout(profiles)
        profiles_layout.setContentsMargins(0, 0, 0, 0)
        profiles_layout.addWidget(self.profile_list)
        actions = QHBoxLayout()
        new_profile = QPushButton("NOVO PERFIL")
        self.profile_delete_button = QPushButton("EXCLUIR")
        new_profile.clicked.connect(self._new_profile)
        self.profile_delete_button.clicked.connect(self._delete_selected_profile)
        self.profile_list.currentItemChanged.connect(self._update_delete_button)
        self._update_delete_button()
        actions.addWidget(new_profile)
        actions.addWidget(self.profile_delete_button)
        profiles_layout.addLayout(actions)

        splitter.addWidget(catalogs)
        splitter.addWidget(profiles)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([430, 260])
        layout.addWidget(splitter, 1)

        refresh = QPushButton("ATUALIZAR")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        return box

    def _editor_panel(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        self.selected_label = QLabel("Selecione um catálogo")
        outer.addWidget(self.selected_label)

        sections = QSplitter(Qt.Orientation.Vertical)
        sections.setChildrenCollapsible(False)
        self._editor_splitter = sections

        source_box = self._source_box()
        source_box.setMinimumHeight(85)

        filter_box = QWidget()
        filter_layout = QVBoxLayout(filter_box)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Nome do perfil:"))
        from PySide6.QtWidgets import QLineEdit
        self.profile_name = QLineEdit()
        self.profile_name.setPlaceholderText("Ex.: MAME Arcade 1G1R")
        self.profile_name.editingFinished.connect(self._profile_name_changed)
        name_layout.addWidget(self.profile_name, 1)
        filter_layout.addLayout(name_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        self.filter_layout = QVBoxLayout(body)
        self._build_generic_controls()
        self._build_mame_controls()
        self.filter_layout.addStretch()
        scroll.setWidget(body)
        filter_layout.addWidget(scroll, 1)
        filter_box.setMinimumHeight(220)

        estimate_box = self._estimate_box()
        estimate_box.setMinimumHeight(70)

        scan_box = self._scan_box()
        scan_box.setMinimumHeight(150)

        sections.addWidget(source_box)
        sections.addWidget(filter_box)
        sections.addWidget(estimate_box)
        sections.addWidget(scan_box)
        sections.setStretchFactor(0, 1)
        sections.setStretchFactor(1, 5)
        sections.setStretchFactor(2, 1)
        sections.setStretchFactor(3, 2)
        sections.setSizes([130, 430, 95, 220])
        outer.addWidget(sections, 1)
        return page

    def _estimate_box(self):
        from PySide6.QtWidgets import QGroupBox
        box = QGroupBox("Estimativa do catálogo — filtros em tempo real")
        layout = QVBoxLayout(box)
        self.catalog_estimate = QLabel("Selecione um catálogo para calcular.")
        self.catalog_estimate.setWordWrap(True)
        self.catalog_estimate.setProperty("role", "subtitle")
        layout.addWidget(self.catalog_estimate)
        self.catalog_estimate_detail = QLabel("Nenhuma consulta executada.")
        self.catalog_estimate_detail.setWordWrap(True)
        layout.addWidget(self.catalog_estimate_detail)
        return box

    def _scan_box(self):
        from PySide6.QtWidgets import QGroupBox
        box = QGroupBox("Execução do Scan")
        layout = QVBoxLayout(box)
        self.scan_progress = QLabel("Nenhum scan executado.")
        self.scan_progress.setWordWrap(True)
        layout.addWidget(self.scan_progress)
        buttons = QHBoxLayout()
        self.save_button = QPushButton("SALVAR PERFIL")
        self.save_button.clicked.connect(self._save_profile)
        self.scan_button = QPushButton("SALVAR E INICIAR SCAN")
        self.scan_button.clicked.connect(self._save_and_scan)
        self.cancel_button = QPushButton("CANCELAR")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_scan)
        self.reconstruction_button = QPushButton("ABRIR RECONSTRUÇÃO")
        self.reconstruction_button.setEnabled(False)
        self.reconstruction_button.clicked.connect(self._open_reconstruction)
        for button in (self.save_button, self.scan_button, self.cancel_button, self.reconstruction_button):
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.log_view = QListWidget()
        self.log_view.setMinimumHeight(80)
        self.log_view.setMaximumHeight(180)
        layout.addWidget(self.log_view, 1)
        return box

    def _refresh_profile_list(self, *_args):
        selected_id = None
        current = self.profile_list.currentItem() if hasattr(self, "profile_list") else None
        if current is not None:
            selected_id = current.data(Qt.ItemDataRole.UserRole)
        profiles = self._read_profiles()
        self.profile_list.blockSignals(True)
        self.profile_list.clear()
        selected_row = -1
        for row, profile in enumerate(profiles):
            item = QListWidgetItem(f"{profile.name}\n{profile.source} › {profile.system}")
            item.setData(Qt.ItemDataRole.UserRole, profile.profile_id)
            item.setToolTip(
                f"ID={profile.profile_id}\nCriado={profile.created_at}\nAtualizado={profile.updated_at}"
            )
            self.profile_list.addItem(item)
            if profile.profile_id == selected_id:
                selected_row = row
        if selected_row >= 0:
            self.profile_list.setCurrentRow(selected_row)
        self.profile_list.blockSignals(False)
        self._update_delete_button()

    def _update_delete_button(self, *_args):
        if hasattr(self, "profile_delete_button"):
            self.profile_delete_button.setEnabled(self.profile_list.currentItem() is not None)

    def _delete_selected_profile(self) -> None:
        selected = self.profile_list.selectedItems()
        if not selected:
            current = self.profile_list.currentItem()
            if current is not None:
                selected = [current]
        if not selected:
            QMessageBox.information(self, "Perfis", "Selecione um perfil para excluir.")
            return

        profile_id = selected[0].data(Qt.ItemDataRole.UserRole)
        profiles = self._read_profiles()
        profile = next((item for item in profiles if item.profile_id == profile_id), None)
        if profile is None:
            self._refresh_profile_list()
            return

        answer = QMessageBox.question(
            self,
            "Excluir perfil",
            f"Excluir o perfil '{profile.name}'?\n\nO histórico dos scans já gravados será preservado.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._write_profiles([item for item in profiles if item.profile_id != profile_id])
        if self._current_saved_profile and self._current_saved_profile.profile_id == profile_id:
            self._current_saved_profile = None
            self._last_scan_result = None
        self._refresh_profile_list()
        self.scan_progress.setText("Perfil excluído. O histórico dos scans foi preservado.")
        self._update_delete_button()


__all__ = ["FilterProfilesPage"]
