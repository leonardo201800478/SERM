"""Controles de retomada e reinício do scan MAME."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QPushButton

from ..services.scan_checkpoint_service import ScanCheckpointService
from .filter_profiles_layout import FilterProfilesPage as _FilterProfilesPage


class FilterProfilesPage(_FilterProfilesPage):
    """Adiciona retomada explícita por checkpoint e novo scan do zero."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._install_checkpoint_controls()
        self._update_checkpoint_controls()

    def _install_checkpoint_controls(self) -> None:
        if hasattr(self, "resume_checkpoint_button"):
            return
        layout = self.scan_button.parentWidget().layout()
        if layout is None:
            return
        self.resume_checkpoint_button = QPushButton("RETOMAR CHECKPOINT")
        self.resume_checkpoint_button.setToolTip(
            "Retoma o último scan MAME interrompido a partir das machines já confirmadas."
        )
        self.resume_checkpoint_button.clicked.connect(self._resume_checkpoint_scan)
        self.new_scan_button = QPushButton("NOVO SCAN DO ZERO")
        self.new_scan_button.setToolTip(
            "Preserva o checkpoint atual e inicia um novo scan completo."
        )
        self.new_scan_button.clicked.connect(self._start_new_scan)
        layout.insertWidget(max(0, layout.count() - 1), self.resume_checkpoint_button)
        layout.insertWidget(max(0, layout.count() - 1), self.new_scan_button)

    def _profile_for_checkpoint(self):
        profile = self._current_profile()
        if profile is None:
            return None
        if str(profile.source).casefold() != "mame":
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
            self.resume_checkpoint_button.setToolTip(
                f"Retomar {summary['completed']:,} machines já confirmadas; "
                f"última machine: {summary['last_machine'] or '-'}"
            )

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
        self.scan_progress.setText(
            f"RETOMADA | {summary['completed']:,} machines já concluídas | "
            f"última={summary['last_machine'] or '-'}"
        )
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
            self.scan_progress.setText(
                "NOVO SCAN | checkpoint anterior preservado; iniciando do zero."
            )
        else:
            self.scan_progress.setText("NOVO SCAN | nenhum checkpoint anterior encontrado; iniciando do zero.")
        self._start_scan(profile)

    def _start_scan(self, profile):
        if hasattr(self, "resume_checkpoint_button"):
            self.resume_checkpoint_button.setEnabled(False)
            self.new_scan_button.setEnabled(False)
        super()._start_scan(profile)

    def _scan_completed(self, result):
        super()._scan_completed(result)
        self._update_checkpoint_controls()

    def _load_profile(self, profile) -> None:
        super()._load_profile(profile)
        self._update_checkpoint_controls()

    def _new_profile(self) -> None:
        super()._new_profile()
        self._update_checkpoint_controls()


__all__ = ["FilterProfilesPage"]
