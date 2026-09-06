"""Controles de retomada, reinício e filtros avançados do scan MAME."""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QPushButton, QDialog

from ..services.mame_category_filter_service import MameCategoryFilterService
from ..services.scan_checkpoint_service import ScanCheckpointService
from ..services.scan_filter_service import ScanFilterService
from .filter_profiles_layout import FilterProfilesPage as _FilterProfilesPage
from .mame_advanced_filters_dialog import MameAdvancedFiltersDialog


class FilterProfilesPage(_FilterProfilesPage):
    """Adiciona checkpoint e uma camada de filtragem CATLIST sobre o snapshot bruto."""

    def __init__(self, parent=None) -> None:
        self._category_filters = {"categories": [], "subcategories": []}
        super().__init__(parent)
        self._install_checkpoint_controls()
        self._install_advanced_filter_controls()
        self._update_checkpoint_controls()

    def _install_checkpoint_controls(self) -> None:
        if hasattr(self, "resume_checkpoint_button"):
            return
        layout = self.scan_button.parentWidget().layout()
        if layout is None:
            return
        self.resume_checkpoint_button = QPushButton("RETOMAR CHECKPOINT")
        self.resume_checkpoint_button.setToolTip("Retoma o último scan MAME interrompido a partir das machines já confirmadas.")
        self.resume_checkpoint_button.clicked.connect(self._resume_checkpoint_scan)
        self.new_scan_button = QPushButton("NOVO SCAN DO ZERO")
        self.new_scan_button.setToolTip("Preserva o checkpoint atual e inicia um novo scan completo.")
        self.new_scan_button.clicked.connect(self._start_new_scan)
        layout.insertWidget(max(0, layout.count() - 1), self.resume_checkpoint_button)
        layout.insertWidget(max(0, layout.count() - 1), self.new_scan_button)

    def _install_advanced_filter_controls(self) -> None:
        if not hasattr(self, "mame_fundamental_button"):
            return
        layout = self.mame_fundamental_button.parentWidget().layout()
        if layout is None or hasattr(self, "mame_catlist_button"):
            return
        self.mame_catlist_button = QPushButton("FILTROS CATLIST…")
        self.mame_catlist_button.setToolTip("Abrir o catálogo completo de categorias e subcategorias importadas do CATLIST.")
        self.mame_catlist_button.clicked.connect(self._open_catlist_filters)
        layout.insertRow(layout.rowCount(), self.mame_catlist_button)
        self.mame_catlist_summary = getattr(self, "mame_fundamental_summary", None)
        self._update_catlist_summary()

    def _open_catlist_filters(self) -> None:
        profile_id = self._current_saved_profile.profile_id if self._current_saved_profile else ""
        values = MameCategoryFilterService.load(profile_id) if profile_id else self._category_filters
        dialog = MameAdvancedFiltersDialog(values, self._database_path(), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._category_filters = dialog.values()
        if profile_id:
            MameCategoryFilterService.save(profile_id, self._category_filters)
        self._update_catlist_summary()
        self._schedule_catalog_estimate()
        self.scan_progress.setText("Filtros CATLIST alterados. O scan bruto não será repetido.")

    def _update_catlist_summary(self) -> None:
        label = getattr(self, "mame_catlist_summary", None)
        if label is None:
            return
        categories = len(self._category_filters.get("categories", []))
        subcategories = len(self._category_filters.get("subcategories", []))
        label.setText(f"CATLIST: {categories} categorias + {subcategories} subcategorias selecionadas para exclusão")

    def _profile_for_checkpoint(self):
        profile = self._current_profile()
        if profile is None or str(profile.source).casefold() != "mame":
            return None
        return profile

    def _update_checkpoint_controls(self) -> None:
        if not hasattr(self, "resume_checkpoint_button"):
            return
        profile = self._profile_for_checkpoint()
        summary = ScanCheckpointService.summary(profile) if profile is not None else None
        available = summary is not None
        self.resume_checkpoint_button.setEnabled(available and not self._scan_is_running())
        self.new_scan_button.setEnabled(profile is not None and not self._scan_is_running())
        if available:
            self.resume_checkpoint_button.setToolTip(f"Retomar {summary['completed']:,} machines já confirmadas; última machine: {summary['last_machine'] or '-'}")

    def _scan_is_running(self) -> bool:
        worker = getattr(self, "_scan_worker", None)
        return worker is not None and worker.isRunning()

    def _resume_checkpoint_scan(self) -> None:
        profile = self._save_profile()
        if profile is None or str(profile.source).casefold() != "mame":
            QMessageBox.information(self, "Retomada", "Selecione um perfil MAME para retomar o checkpoint.")
            return
        summary = ScanCheckpointService.summary(profile)
        if summary is None:
            QMessageBox.information(self, "Retomada", "Nenhum checkpoint MAME disponível para este perfil.")
            return
        self.scan_progress.setText(f"RETOMADA | {summary['completed']:,} machines já concluídas | última={summary['last_machine'] or '-'}")
        self._start_scan(profile)

    def _start_new_scan(self) -> None:
        profile = self._save_profile()
        if profile is None or str(profile.source).casefold() != "mame":
            QMessageBox.information(self, "Novo scan", "Selecione um perfil MAME para iniciar um novo scan.")
            return
        if self._scan_is_running():
            return
        archived = ScanCheckpointService.archive_latest(profile)
        if archived is not None:
            self._append_log("INFO", f"SCAN | checkpoint preservado em {archived.name}")
            self.scan_progress.setText("NOVO SCAN | checkpoint anterior preservado; iniciando do zero.")
        else:
            self.scan_progress.setText("NOVO SCAN | nenhum checkpoint anterior encontrado; iniciando do zero.")
        self._start_scan(profile)

    def _start_scan(self, profile):
        if hasattr(self, "resume_checkpoint_button"):
            self.resume_checkpoint_button.setEnabled(False)
            self.new_scan_button.setEnabled(False)
        super()._start_scan(profile)

    def _load_profile(self, profile) -> None:
        super()._load_profile(profile)
        self._category_filters = MameCategoryFilterService.load(profile.profile_id) if str(profile.source).casefold() == "mame" else {"categories": [], "subcategories": []}
        self._update_catlist_summary()
        self._update_checkpoint_controls()

    def _save_profile(self):
        profile = super()._save_profile()
        if profile is not None and str(profile.source).casefold() == "mame":
            MameCategoryFilterService.save(profile.profile_id, self._category_filters)
        return profile

    def _new_profile(self) -> None:
        super()._new_profile()
        self._category_filters = {"categories": [], "subcategories": []}
        self._update_catlist_summary()
        self._update_checkpoint_controls()

    def _delete_selected_profile(self) -> None:
        selected = self.profile_list.selectedItems()
        current = self.profile_list.currentItem()
        item = selected[0] if selected else current
        profile_id = item.data(256) if item is not None else None
        super()._delete_selected_profile()
        if profile_id:
            MameCategoryFilterService.delete(str(profile_id))

    def _scan_completed(self, result):
        self._last_scan_result = result
        self.apply_filter_button.setEnabled(True)
        self.reconstruction_button.setEnabled(False)
        self.scan_progress.setText(f"SCAN BRUTO | concluído | scan_id={result.scan_id} | catálogo={result.catalog_label} | tipo={result.scan_type} | arquivos={result.files_examined} | itens={result.items_examined}")
        self._schedule_catalog_estimate()
        self._update_checkpoint_controls()

    def _apply_filters_to_scan(self) -> None:
        profile = self._save_profile()
        if profile is None:
            return
        repository = self._database_path()
        latest = __import__("serm_v2.services.scan_repository", fromlist=["ScanRepository"]).ScanRepository(repository).latest_for_profile(profile.profile_id)
        if not latest:
            QMessageBox.information(self, "Filtros", "Nenhum scan bruto foi encontrado para este perfil.")
            return
        raw_path = __import__("serm_v2.services.scan_repository", fromlist=["ScanRepository"]).ScanRepository(repository).raw_file(str(latest["scan_id"]))
        if raw_path is None or not raw_path.is_file():
            QMessageBox.warning(self, "Filtros", "O arquivo bruto do scan não foi encontrado.")
            return
        try:
            self._last_filter_result = ScanFilterService.apply_mame(raw_path, profile, self._fundamental_filters, self._category_filters)
        except Exception as exc:  # noqa: BLE001
            self._append_log("ERROR", f"FILTRO | falha | {type(exc).__name__}: {exc}")
            QMessageBox.warning(self, "Filtros", f"Não foi possível aplicar os filtros:\n{exc}")
            return
        result = self._last_filter_result
        self.reconstruction_button.setEnabled(True)
        self.scan_progress.setText(f"FILTRO | concluído | bruto={result['input_count']:,} | mantidas={result['output_count']:,} | excluídas={result['filtered_count']:,}")
        self._append_log("INFO", f"FILTRO | arquivo={result['filtered_file_path']}")

    def _update_catalog_estimate(self) -> None:
        super()._update_catalog_estimate()
        # A estimativa base já considera o snapshot; esta linha mantém o resumo CATLIST visível.
        self._update_catlist_summary()


__all__ = ["FilterProfilesPage"]
