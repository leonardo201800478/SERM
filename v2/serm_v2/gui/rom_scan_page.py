"""GUI do scanner: consome os perfis salvos pela guia de filtros."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QProgressBar, QPushButton, QTreeWidget, QVBoxLayout, QWidget

from ..runtime.paths import data_root


class RomScanPage(QWidget):
    """Seleciona um perfil salvo e prepara o scan correspondente."""

    scan_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._profiles_path = data_root() / "filter_profiles.json"
        self._selected_profile: dict | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("SERM V2 — Scan de ROMs")
        title.setProperty("role", "title")
        layout.addWidget(title)
        description = QLabel("O scanner não redefine filtros. Ele recebe exatamente um perfil salvo na guia Filtros e usa suas fontes, DAT e políticas como contrato de execução.")
        description.setWordWrap(True)
        layout.addWidget(description)

        profiles_box = QGroupBox("Perfis salvos — entrada do scan")
        profiles_layout = QVBoxLayout(profiles_box)
        self.profile_list = QListWidget()
        self.profile_list.currentItemChanged.connect(self._profile_changed)
        profiles_layout.addWidget(self.profile_list)
        profile_actions = QHBoxLayout()
        self.reload_profiles_button = QPushButton("ATUALIZAR PERFIS")
        self.reload_profiles_button.clicked.connect(self.refresh)
        profile_actions.addWidget(self.reload_profiles_button)
        profile_actions.addStretch()
        profiles_layout.addLayout(profile_actions)
        layout.addWidget(profiles_box)

        context = QGroupBox("Contexto do perfil")
        context_layout = QVBoxLayout(context)
        self.profile_label = QLabel("Perfil: nenhum selecionado")
        self.dat_label = QLabel("DAT: —")
        self.source_label = QLabel("Fontes: —")
        for label in (self.profile_label, self.dat_label, self.source_label):
            label.setWordWrap(True)
            context_layout.addWidget(label)
        layout.addWidget(context)

        actions = QHBoxLayout()
        self.scan_button = QPushButton("INICIAR SCAN DO PERFIL")
        self.scan_button.setProperty("role", "primary")
        self.scan_button.setEnabled(False)
        self.scan_button.clicked.connect(self._start_scan)
        self.cancel_button = QPushButton("CANCELAR")
        self.cancel_button.setEnabled(False)
        actions.addWidget(self.scan_button)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.status = QLabel("Nenhum perfil selecionado.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.result_tree = QTreeWidget()
        self.result_tree.setHeaderLabels(["Estado", "Set / arquivo", "Detalhe"])
        self.result_tree.setAlternatingRowColors(True)
        layout.addWidget(self.result_tree, 1)

    def _read_profiles(self) -> list[dict]:
        try:
            raw = json.loads(self._profiles_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return []
        return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []

    @staticmethod
    def _profile_text(profile: dict) -> str:
        source = str(profile.get("source", "?"))
        system = str(profile.get("system", "?"))
        folders = profile.get("source_directories") or []
        return f"{source}  ›  {system}  |  {len(folders)} fonte(s)"

    def refresh(self) -> None:
        self.profile_list.clear()
        profiles = self._read_profiles()
        for index, profile in enumerate(profiles):
            item = QListWidgetItem(self._profile_text(profile))
            item.setData(32, index)
            item.setToolTip("Perfil salvo na guia Filtros; este registro é o contrato do scan.")
            self.profile_list.addItem(item)
        if self.profile_list.count():
            self.profile_list.setCurrentRow(self.profile_list.count() - 1)
        else:
            self._selected_profile = None
            self.scan_button.setEnabled(False)
            self.status.setText(f"Nenhum perfil salvo em {self._profiles_path}.")

    def _profile_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        profiles = self._read_profiles()
        index = current.data(32)
        self._selected_profile = profiles[index] if isinstance(index, int) and 0 <= index < len(profiles) else None
        if self._selected_profile is None:
            self.scan_button.setEnabled(False)
            return
        profile = self._selected_profile
        source = str(profile.get("source", "?"))
        system = str(profile.get("system", "?"))
        dat = str(profile.get("dat_path") or "Catálogo interno / MAME")
        folders = profile.get("source_directories") or []
        self.profile_label.setText(f"Perfil: {source} › {system}")
        self.dat_label.setText(f"DAT/catálogo: {dat}")
        self.source_label.setText("Fontes: " + (" | ".join(map(str, folders)) if folders else "nenhuma configurada"))
        self.scan_button.setEnabled(bool(folders))
        self.status.setText("Perfil carregado. O scanner usará exatamente estes parâmetros.")

    def _start_scan(self) -> None:
        if self._selected_profile is None:
            return
        self.progress.setValue(0)
        self.status.setText("Perfil enviado ao motor de scan. A execução física será conectada ao scanner V2 sem alterar o perfil salvo.")
        self.scan_requested.emit(self._selected_profile)

    def selected_profile(self) -> dict | None:
        """Retorna o perfil selecionado para integração com o motor de scan."""
        return self._selected_profile


__all__ = ["RomScanPage"]
