"""Controles de retomada, reinício e filtros avançados do scan MAME/No-Intro."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QPushButton

from ..services.mame_category_filter_service import MameCategoryFilterService
from ..services.no_intro_scan_service import NoIntroScanService
from ..services.scan_checkpoint_service import ScanCheckpointService
from ..services.scan_file_repository import ScanFileRepository
from ..services.scan_filter_service import ScanFilterService
from ..services.scan_repository import ScanRepository
from .filter_profiles_layout import FilterProfilesPage as _FilterProfilesPage
from .mame_advanced_filters_dialog import MameAdvancedFiltersDialog


class _NoIntroScanWorker(QThread):
    """Executa o scan No-Intro fora da thread da interface."""

    progress = Signal(int, int)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, profile, database_path, parent=None) -> None:
        super().__init__(parent)
        self.profile = profile
        self.database_path = database_path
        self.service: NoIntroScanService | None = None

    def run(self) -> None:
        try:
            self.service = NoIntroScanService(progress_callback=self.progress.emit)
            result = self.service.scan(self.profile)
            ScanRepository(self.database_path).save(result, dat_path=self.profile.dat_path)
            self.completed.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def cancel(self) -> None:
        if self.service is not None:
            self.service.cancel()


class FilterProfilesPage(_FilterProfilesPage):
    """Adiciona checkpoint/filtros MAME e o scanner bruto No-Intro."""

    def __init__(self, parent=None) -> None:
        self._category_filters = {"categories": [], "subcategories": []}
        self._no_intro_worker: _NoIntroScanWorker | None = None
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
        self.mame_catlist_summary = QLabel()
        self.mame_catlist_summary.setWordWrap(True)
        layout.insertRow(layout.rowCount(), self.mame_catlist_summary)
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
        no_intro = getattr(self, "_no_intro_worker", None)
        return (worker is not None and worker.isRunning()) or (no_intro is not None and no_intro.isRunning())

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
        if self._scan_is_running():
            return
        if str(profile.source).casefold() != "no-intro":
            if hasattr(self, "resume_checkpoint_button"):
                self.resume_checkpoint_button.setEnabled(False)
                self.new_scan_button.setEnabled(False)
            super()._start_scan(profile)
            return

        self._start_no_intro_scan(profile)

    def _start_no_intro_scan(self, profile) -> None:
        self._last_scan_result = None
        self.scan_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.reconstruction_button.setEnabled(False)
        self.log_view.clear()
        self.scan_progress.setText(
            f"SCAN BRUTO | No-Intro | {profile.system} | DAT={Path(profile.dat_path).name if profile.dat_path else '—'}"
        )
        self._no_intro_worker = _NoIntroScanWorker(profile, self._database_path(), self)
        self._no_intro_worker.progress.connect(self._scan_progress)
        self._no_intro_worker.completed.connect(self._scan_completed)
        self._no_intro_worker.failed.connect(self._scan_failed)
        self._no_intro_worker.finished.connect(self._no_intro_scan_finished)
        self.scan_requested.emit(profile)
        self._no_intro_worker.start()

    def _no_intro_scan_finished(self) -> None:
        self.scan_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self._no_intro_worker = None

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
        profile_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        super()._delete_selected_profile()
        if profile_id:
            MameCategoryFilterService.delete(str(profile_id))

    def _scan_completed(self, result):
        self._last_scan_result = result
        self.reconstruction_button.setEnabled(True)
        self.scan_progress.setText(
            f"SCAN BRUTO | concluído | scan_id={result.scan_id} | catálogo={result.catalog_label} | tipo={result.scan_type} | "
            f"arquivos={result.files_examined} | itens={result.items_examined} | "
            + " | ".join(f"{key}={value:,}" for key, value in result.status_counts.items())
        )
        self._schedule_catalog_estimate()
        self._update_checkpoint_controls()

    def _raw_scan_path(self):
        profile = self._current_profile()
        if profile is None:
            return None
        latest = ScanRepository(self._database_path()).latest_for_profile(profile.profile_id)
        if not latest:
            return None
        path = ScanRepository(self._database_path()).raw_file(str(latest["scan_id"]))
        return path if path is not None and path.is_file() else None

    def _apply_filters_to_scan(self) -> None:
        profile = self._save_profile()
        if profile is None:
            return
        raw_path = self._raw_scan_path()
        if raw_path is None:
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
        if result.get("filter_counts"):
            self._append_log("INFO", "FILTRO | " + " | ".join(f"{key}={value:,}" for key, value in result["filter_counts"].items()))

    def _update_catalog_estimate(self) -> None:
        selected = self._selected_item_data()
        if selected is None or selected[0] != "MAME":
            return super()._update_catalog_estimate()
        profile = self._current_profile()
        raw_path = self._raw_scan_path()
        if profile is None or raw_path is None:
            return super()._update_catalog_estimate()
        try:
            preview = ScanFilterService.preview_mame(raw_path, profile, self._fundamental_filters, self._category_filters)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            self.catalog_estimate.setText("Não foi possível calcular o filtro sobre o scan.")
            self.catalog_estimate_detail.setText(str(exc))
            return
        self.catalog_estimate.setText(
            f"SCAN BRUTO: {int(preview['input_count']):,} ROMs  →  APÓS FILTROS: {int(preview['output_count']):,} ROMs  →  EXCLUÍDAS: {int(preview['filtered_count']):,}"
        )
        counts = preview.get("filter_counts", {})
        details = " • ".join(f"{key}={int(value):,}" for key, value in counts.items()) or "Nenhuma ROM excluída"
        status = preview.get("status_counts", {})
        self.catalog_estimate_detail.setText(
            f"Catálogo: {preview.get('catalog_label')} | tipo: {preview.get('scan_type')} | "
            f"CURRENT={status.get('CURRENT', 0):,} | MISSING={status.get('MISSING', 0):,} | "
            f"WRONG={status.get('WRONG', 0):,} | DUPLICATE={status.get('DUPLICATE', 0):,}\n"
            f"Filtros: {details}"
        )


__all__ = ["FilterProfilesPage"]
