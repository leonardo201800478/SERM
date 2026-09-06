"""Layout configurável da tela de filtros e scan."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from ..services.mame_fundamental_filter_service import DEFAULT_FILTERS, MameFundamentalFilterService
from ..services.mame_scan_settings_service import SCAN_TYPES, MameScanSettingsService
from ..services.scan_file_repository import ScanFileRepository
from ..services.scan_filter_service import ScanFilterService
from ..services.scan_repository import ScanRepository
from .filter_profiles_page import FilterProfilesPage as _BaseFilterProfilesPage
from .mame_fundamental_filters_dialog import MameFundamentalFiltersDialog


class FilterProfilesPage(_BaseFilterProfilesPage):
    """Tela de filtros/scan com pipeline explícito: SCAN bruto → FILTRO → reconstrução."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self._fundamental_filters = dict(DEFAULT_FILTERS)
        self._last_filter_result: dict | None = None
        super().__init__(parent)

    def _catalog_panel(self) -> QWidget:
        box = QGroupBox("Catálogos")
        layout = QVBoxLayout(box)
        self.source_tree = QTreeWidget()
        self.source_tree.setHeaderLabels(["Fonte / sistema"])
        self.source_tree.setMinimumWidth(270)
        self.source_tree.itemSelectionChanged.connect(self._selection_changed)
        self.profile_list = QListWidget()
        self.profile_list.currentItemChanged.connect(self._saved_profile_selected)
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
        self.source_list.setMaximumHeight(16777215)
        filter_box = QWidget()
        filter_layout = QVBoxLayout(filter_box)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Nome do perfil:"))
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
        estimate_box = QGroupBox("Catálogo do scan — resultado bruto × filtro")
        estimate_layout = QVBoxLayout(estimate_box)
        self.catalog_estimate = QLabel("Execute o primeiro scan para criar o snapshot bruto.")
        self.catalog_estimate.setWordWrap(True)
        self.catalog_estimate.setProperty("role", "subtitle")
        estimate_layout.addWidget(self.catalog_estimate)
        self.catalog_estimate_detail = QLabel("Os filtros nunca participam do scan.")
        self.catalog_estimate_detail.setWordWrap(True)
        estimate_layout.addWidget(self.catalog_estimate_detail)
        estimate_box.setMinimumHeight(85)
        scan_box = QGroupBox("1 — Scan bruto / 2 — Aplicação dos filtros")
        scan_layout = QVBoxLayout(scan_box)
        self.mame_scan_type_label = QLabel("Tipo de scan MAME:")
        self.mame_scan_type = QComboBox()
        for key, label in SCAN_TYPES.items():
            self.mame_scan_type.addItem(label, key)
        self.mame_scan_type.currentIndexChanged.connect(self._scan_type_changed)
        scan_type_row = QHBoxLayout()
        scan_type_row.addWidget(self.mame_scan_type_label)
        scan_type_row.addWidget(self.mame_scan_type, 1)
        scan_layout.addLayout(scan_type_row)
        self.scan_progress = QLabel("Nenhum scan executado.")
        self.scan_progress.setWordWrap(True)
        scan_layout.addWidget(self.scan_progress)
        buttons = QHBoxLayout()
        self.save_button = QPushButton("SALVAR PERFIL")
        self.save_button.clicked.connect(self._save_profile)
        self.scan_button = QPushButton("SALVAR E INICIAR SCAN")
        self.scan_button.clicked.connect(self._save_and_scan)
        self.cancel_button = QPushButton("CANCELAR")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_scan)
        self.apply_filter_button = QPushButton("APLICAR FILTROS AO SCAN")
        self.apply_filter_button.setEnabled(False)
        self.apply_filter_button.clicked.connect(self._apply_filters_to_scan)
        self.reconstruction_button = QPushButton("ABRIR RECONSTRUÇÃO")
        self.reconstruction_button.setEnabled(False)
        self.reconstruction_button.clicked.connect(self._open_reconstruction)
        for button in (
            self.save_button,
            self.scan_button,
            self.cancel_button,
            self.apply_filter_button,
            self.reconstruction_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch()
        scan_layout.addLayout(buttons)
        self.log_view = QListWidget()
        self.log_view.setMinimumHeight(80)
        self.log_view.setMaximumHeight(180)
        scan_layout.addWidget(self.log_view, 1)
        scan_box.setMinimumHeight(180)
        sections.addWidget(source_box)
        sections.addWidget(filter_box)
        sections.addWidget(estimate_box)
        sections.addWidget(scan_box)
        sections.setStretchFactor(0, 1)
        sections.setStretchFactor(1, 5)
        sections.setStretchFactor(2, 1)
        sections.setStretchFactor(3, 2)
        sections.setSizes([130, 430, 95, 250])
        outer.addWidget(sections, 1)
        return page

    def _build_mame_controls(self) -> None:
        super()._build_mame_controls()
        self.mame_fundamental_button = QPushButton("FILTROS FUNDAMENTAIS…")
        self.mame_fundamental_button.setToolTip(
            "Abrir em uma janela separada as exclusões fundamentais da V1."
        )
        self.mame_fundamental_button.clicked.connect(self._open_fundamental_filters)
        self.mame_fundamental_summary = QLabel()
        self.mame_fundamental_summary.setWordWrap(True)
        layout = self.mame_box.layout()
        if layout is not None:
            layout.addRow(self.mame_fundamental_button)
            layout.addRow(self.mame_fundamental_summary)
        self._update_fundamental_summary()

    def _configure_source_controls(self, source: str) -> None:
        super()._configure_source_controls(source)
        is_mame = str(source).casefold() == "mame"
        self.mame_scan_type_label.setVisible(is_mame)
        self.mame_scan_type.setVisible(is_mame)

    def _scan_type_changed(self, *_args) -> None:
        self._last_filter_result = None
        self.apply_filter_button.setEnabled(False)
        self.reconstruction_button.setEnabled(False)
        self._schedule_catalog_estimate()

    def _open_fundamental_filters(self) -> None:
        profile_id = self._current_saved_profile.profile_id if self._current_saved_profile else ""
        values = (
            MameFundamentalFilterService.load(profile_id)
            if profile_id
            else dict(self._fundamental_filters)
        )
        dialog = MameFundamentalFiltersDialog(values, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._fundamental_filters = dialog.values()
        if profile_id:
            MameFundamentalFilterService.save(profile_id, self._fundamental_filters)
        self._update_fundamental_summary()
        self._schedule_catalog_estimate()
        self.scan_progress.setText(
            "Filtros fundamentais alterados. O scan bruto não será repetido até você solicitar um novo scan."
        )

    def _update_fundamental_summary(self) -> None:
        if not hasattr(self, "mame_fundamental_summary"):
            return
        active = sum(1 for enabled in self._fundamental_filters.values() if enabled)
        self.mame_fundamental_summary.setText(
            f"{active} exclusões fundamentais ativas"
            if active
            else "Nenhuma exclusão fundamental ativa"
        )

    def _update_catalog_estimate(self) -> None:
        selected = self._selected_item_data()
        if selected is None:
            self.catalog_estimate.setText("Selecione um catálogo.")
            self.catalog_estimate_detail.setText("Nenhum scan disponível.")
            return
        source, system, _dat_path = selected
        if source != "MAME":
            self.catalog_estimate.setText(
                "A auditoria externa será identificada pela versão/data do DAT."
            )
            self.catalog_estimate_detail.setText(
                "Os filtros específicos serão executados somente depois do snapshot do DAT."
            )
            return
        profile = self._current_profile()
        if profile is None:
            return
        latest = ScanRepository(self._database_path()).latest_for_profile(profile.profile_id)
        if not latest or not latest.get("scan_file_path"):
            self.catalog_estimate.setText("Nenhum scan bruto disponível para este perfil.")
            self.catalog_estimate_detail.setText(
                "Execute o scan uma única vez. Depois disso os filtros trabalharão somente sobre o arquivo salvo."
            )
            return
        raw_path = Path(str(latest["scan_file_path"]))
        if not raw_path.is_file():
            raw_path = ScanFileRepository.latest_path(str(latest["scan_id"])) or raw_path
        if not raw_path.is_file():
            self.catalog_estimate.setText("Arquivo do scan não encontrado.")
            self.catalog_estimate_detail.setText(str(raw_path))
            return
        try:
            preview = ScanFilterService.preview_mame(raw_path, profile, self._fundamental_filters)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            self.catalog_estimate.setText("Não foi possível calcular o filtro sobre o scan.")
            self.catalog_estimate_detail.setText(str(exc))
            return
        self.catalog_estimate.setText(
            f"SCAN BRUTO: {int(preview['input_count']):,} ROMs  →  APÓS FILTROS: {int(preview['output_count']):,} ROMs  →  EXCLUÍDAS: {int(preview['filtered_count']):,}"
        )
        counts = preview.get("filter_counts", {})
        details = (
            " • ".join(f"{key}={int(value):,}" for key, value in counts.items())
            or "Nenhuma ROM excluída"
        )
        status = preview.get("status_counts", {})
        self.catalog_estimate_detail.setText(
            f"Catálogo: {preview.get('catalog_label')} | tipo: {preview.get('scan_type')} | CURRENT={status.get('CURRENT', 0):,} | MISSING={status.get('MISSING', 0):,} | WRONG={status.get('WRONG', 0):,} | DUPLICATE={status.get('DUPLICATE', 0):,}\nFiltros: {details}"
        )

    def _load_profile(self, profile) -> None:
        super()._load_profile(profile)
        self._fundamental_filters = MameFundamentalFilterService.load(profile.profile_id)
        if str(profile.source).casefold() == "mame":
            self.mame_scan_type.blockSignals(True)
            self.mame_scan_type.setCurrentIndex(
                max(
                    0,
                    self.mame_scan_type.findData(MameScanSettingsService.load(profile.profile_id)),
                )
            )
            self.mame_scan_type.blockSignals(False)
        self._update_fundamental_summary()
        self._last_filter_result = None
        self.apply_filter_button.setEnabled(False)
        self.reconstruction_button.setEnabled(False)

    def _save_profile(self):
        profile = super()._save_profile()
        if profile is not None and str(profile.source).casefold() == "mame":
            MameFundamentalFilterService.save(profile.profile_id, self._fundamental_filters)
            MameScanSettingsService.save(profile.profile_id, str(self.mame_scan_type.currentData()))
            self._update_fundamental_summary()
        return profile

    def _new_profile(self) -> None:
        super()._new_profile()
        self._fundamental_filters = dict(DEFAULT_FILTERS)
        self.mame_scan_type.blockSignals(True)
        self.mame_scan_type.setCurrentIndex(0)
        self.mame_scan_type.blockSignals(False)
        self._last_filter_result = None
        self._update_fundamental_summary()

    def _delete_selected_profile(self) -> None:
        selected = self.profile_list.selectedItems()
        current = self.profile_list.currentItem()
        item = selected[0] if selected else current
        profile_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        super()._delete_selected_profile()
        if profile_id:
            MameFundamentalFilterService.delete(str(profile_id))
            MameScanSettingsService.delete(str(profile_id))

    def _start_scan(self, profile):
        if str(profile.source).casefold() == "mame":
            MameScanSettingsService.save(profile.profile_id, str(self.mame_scan_type.currentData()))
        self._last_filter_result = None
        self.apply_filter_button.setEnabled(False)
        self.reconstruction_button.setEnabled(False)
        super()._start_scan(profile)

    def _scan_completed(self, result):
        self._last_scan_result = result
        self.apply_filter_button.setEnabled(True)
        self.reconstruction_button.setEnabled(False)
        self.scan_progress.setText(
            f"SCAN BRUTO | concluído | scan_id={result.scan_id} | catálogo={result.catalog_label} | tipo={result.scan_type} | arquivos={result.files_examined} | itens={result.items_examined}"
        )
        self._schedule_catalog_estimate()

    def _apply_filters_to_scan(self) -> None:
        profile = self._save_profile()
        if profile is None:
            return
        repository = ScanRepository(self._database_path())
        latest = repository.latest_for_profile(profile.profile_id)
        if not latest:
            QMessageBox.information(
                self, "Filtros", "Nenhum scan bruto foi encontrado para este perfil."
            )
            return
        raw_path = repository.raw_file(str(latest["scan_id"]))
        if raw_path is None or not raw_path.is_file():
            QMessageBox.warning(self, "Filtros", "O arquivo bruto do scan não foi encontrado.")
            return
        try:
            self._last_filter_result = ScanFilterService.apply_mame(
                raw_path, profile, self._fundamental_filters
            )
        except Exception as exc:  # noqa: BLE001
            self._append_log("ERROR", f"FILTRO | falha | {type(exc).__name__}: {exc}")
            QMessageBox.warning(self, "Filtros", f"Não foi possível aplicar os filtros:\n{exc}")
            return
        result = self._last_filter_result
        self.reconstruction_button.setEnabled(True)
        self.scan_progress.setText(
            f"FILTRO | concluído | bruto={result['input_count']:,} | mantidas={result['output_count']:,} | excluídas={result['filtered_count']:,}"
        )
        self._append_log("INFO", f"FILTRO | arquivo={result['filtered_file_path']}")
        if result["filter_counts"]:
            self._append_log(
                "INFO",
                "FILTRO | "
                + " | ".join(f"{key}={value:,}" for key, value in result["filter_counts"].items()),
            )
        self._schedule_catalog_estimate()
        self.reconstruction_requested.emit(
            {"profile": profile, "scan_result": self._last_scan_result, "filter_result": result}
        )

    def _open_reconstruction(self):
        if self._current_saved_profile is not None and self._last_filter_result is not None:
            self.reconstruction_requested.emit(
                {
                    "profile": self._current_saved_profile,
                    "scan_result": self._last_scan_result,
                    "filter_result": self._last_filter_result,
                }
            )

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


__all__ = ["FilterProfilesPage"]
