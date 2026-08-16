"""Widget de controle do Scan Roms.

Responsabilidades:
    * seleção/exibição do LISTXML ativo;
    * seleção de perfil de filtro;
    * origens (até 3) e destino das ROMs;
    * workers e opções (busca alternativa, verificar CHDs);
    * botões de ação (gerar XML, iniciar/parar scan).

Este widget NÃO conhece RomScanner, threads, banco de dados ou o XML
em si — apenas coleta o que o usuário configurou e emite sinais para
que quem orquestra (``ScanRomsTab``) decida o que fazer.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class ScanControlWidget(QWidget):
    """Controles de entrada do scan: XML, perfil, diretórios e opções."""

    generate_xml_requested = Signal()
    select_xml_requested = Signal()
    open_folder_requested = Signal()
    start_scan_requested = Signal()
    stop_scan_requested = Signal()
    profile_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    # ========================================================================
    # CONSTRUÇÃO DA UI
    # ========================================================================

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        layout.addLayout(self._build_actions_row())
        layout.addLayout(self._build_xml_row())
        layout.addWidget(self._build_paths_group())
        layout.addWidget(self._build_options_group())

    def _build_actions_row(self) -> QHBoxLayout:
        row = QHBoxLayout()

        self.btn_generate = QPushButton("Gerar LISTXML filtrado")
        self.btn_generate.setToolTip(
            "Gera o LISTXML contendo somente as máquinas selecionadas pelos filtros."
        )
        self.btn_generate.clicked.connect(self.generate_xml_requested.emit)

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(150)
        self.profile_combo.addItem("(usar perfil da aba Filters)", None)
        self.profile_combo.currentIndexChanged.connect(self.profile_changed.emit)
        self.profile_combo.setToolTip(
            "Selecione um perfil para filtrar as máquinas. "
            "Se '(usar perfil da aba Filters)' for selecionado, "
            "usará os filtros atuais da guia Filtragem."
        )

        self.btn_scan = QPushButton("Iniciar escaneamento")
        self.btn_scan.setToolTip(
            "Escaneia somente as máquinas e ROMs presentes no XML selecionado."
        )
        self.btn_scan.clicked.connect(self.start_scan_requested.emit)

        self.btn_stop = QPushButton("Parar")
        self.btn_stop.setToolTip("Solicita o cancelamento do escaneamento.")
        self.btn_stop.clicked.connect(self.stop_scan_requested.emit)
        self.btn_stop.setEnabled(False)

        row.addWidget(self.btn_generate)
        row.addWidget(QLabel("Perfil:"))
        row.addWidget(self.profile_combo)
        row.addWidget(self.btn_scan)
        row.addWidget(self.btn_stop)
        row.addStretch()
        return row

    def _build_xml_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel("XML ativo:"))

        self.xml_label = QLabel("Nenhum XML selecionado.")
        self.xml_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(self.xml_label, stretch=1)

        btn_select = QPushButton("Selecionar XML...")
        btn_select.clicked.connect(self.select_xml_requested.emit)
        row.addWidget(btn_select)

        btn_open = QPushButton("Abrir pasta")
        btn_open.clicked.connect(self.open_folder_requested.emit)
        row.addWidget(btn_open)
        return row

    def _build_paths_group(self) -> QGroupBox:
        group = QGroupBox("Origens das ROMs")
        layout = QGridLayout(group)

        self.source_edits: list[QLineEdit] = []
        for index in range(3):
            label = QLabel(f"Origem {index + 1}:")
            edit = QLineEdit()
            button = QPushButton("Escolher")
            button.clicked.connect(
                lambda checked=False, target=edit: self._choose_directory(target)
            )
            hbox = QHBoxLayout()
            hbox.addWidget(edit)
            hbox.addWidget(button)

            layout.addWidget(label, 0, index)
            layout.addLayout(hbox, 1, index)
            self.source_edits.append(edit)

        destination_label = QLabel("Destino:")
        self.destination_edit = QLineEdit()
        destination_button = QPushButton("Escolher")
        destination_button.clicked.connect(
            lambda: self._choose_directory(self.destination_edit)
        )
        destination_row = QHBoxLayout()
        destination_row.addWidget(self.destination_edit)
        destination_row.addWidget(destination_button)

        layout.addWidget(destination_label, 2, 0)
        layout.addLayout(destination_row, 2, 1, 1, 2)
        return group

    def _build_options_group(self) -> QGroupBox:
        group = QGroupBox("Opções do escaneamento")
        layout = QHBoxLayout(group)

        layout.addWidget(QLabel("Workers:"))
        self.worker_spin = QSpinBox()
        self.worker_spin.setRange(1, max(1, os.cpu_count() or 1))
        self.worker_spin.setValue(1)
        self.worker_spin.setToolTip("Quantidade de máquinas processadas simultaneamente.")
        layout.addWidget(self.worker_spin)

        self.alternate_search_checkbox = QCheckBox("Busca alternativa")
        self.alternate_search_checkbox.setToolTip(
            "Permite procurar uma ROM pelo nome dentro do diretório da própria máquina."
        )
        layout.addWidget(self.alternate_search_checkbox)

        self.include_chds_checkbox = QCheckBox("Verificar CHDs")
        self.include_chds_checkbox.setChecked(True)
        layout.addWidget(self.include_chds_checkbox)

        layout.addStretch()
        return group

    # ========================================================================
    # DIRETÓRIOS
    # ========================================================================

    def _choose_directory(self, target: QLineEdit) -> None:
        current = target.text().strip()
        initial = current if current else str(Path.home())
        selected = QFileDialog.getExistingDirectory(self, "Selecionar diretório", initial)
        if selected:
            target.setText(selected)

    # ========================================================================
    # XML
    # ========================================================================

    def display_xml(self, path: Path) -> None:
        """Atualiza o rótulo do XML ativo. O estado real (o Path em si)
        permanece na aba orquestradora — este widget só exibe."""
        self.xml_label.setText(str(path))
        self.xml_label.setToolTip(str(path))
        self.xml_label.setStyleSheet("color: green;")

    def clear_xml_display(self) -> None:
        self.xml_label.setText("Nenhum XML selecionado.")
        self.xml_label.setToolTip("")
        self.xml_label.setStyleSheet("")

    # ========================================================================
    # PERFIS
    # ========================================================================

    def load_profiles(self, profiles: Iterable[Any], default_id: Any = None) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("(usar perfil da aba Filters)", None)

        for profile in profiles:
            self.profile_combo.addItem(profile.name, profile.id)

        if default_id is not None:
            idx = self.profile_combo.findData(default_id)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)

        self.profile_combo.blockSignals(False)

    def current_profile_id(self) -> Any:
        return self.profile_combo.currentData()

    def current_profile_label(self) -> str:
        idx = self.profile_combo.currentIndex()
        if idx <= 0:
            return "(usando filtros da aba Filters)"
        return self.profile_combo.currentText()

    # ========================================================================
    # PATHS / OPÇÕES
    # ========================================================================

    def get_rom_paths(self) -> list[Path]:
        paths: list[Path] = []
        for edit in self.source_edits:
            text = edit.text().strip()
            if not text:
                continue
            path = Path(text).expanduser()
            if path.is_dir():
                paths.append(path)
        return paths

    def get_destination(self) -> str:
        return self.destination_edit.text().strip()

    def worker_count(self) -> int:
        return max(1, self.worker_spin.value())

    def alternate_search_enabled(self) -> bool:
        return self.alternate_search_checkbox.isChecked()

    def include_chds(self) -> bool:
        return self.include_chds_checkbox.isChecked()

    def load_paths_from_config(self, source_dirs: Iterable[Any], destination: Any) -> None:
        source_dirs = list(source_dirs or [])
        for index, edit in enumerate(self.source_edits):
            if index < len(source_dirs):
                edit.setText(str(source_dirs[index]))
        if destination:
            self.destination_edit.setText(str(destination))

    def collect_paths_for_save(self) -> tuple[list[str], str]:
        """Retorna (origens preenchidas, destino) para persistência externa."""
        paths = [edit.text().strip() for edit in self.source_edits if edit.text().strip()]
        destination = self.destination_edit.text().strip()
        return paths, destination

    # ========================================================================
    # ESTADO DE SCANNING
    # ========================================================================

    def set_scanning_state(self, scanning: bool, *, xml_ready: bool) -> None:
        self.btn_generate.setEnabled(not scanning)
        self.btn_scan.setEnabled(not scanning and xml_ready)
        self.btn_stop.setEnabled(scanning)
        self.worker_spin.setEnabled(not scanning)
        self.alternate_search_checkbox.setEnabled(not scanning)
        self.include_chds_checkbox.setEnabled(not scanning)
        for edit in self.source_edits:
            edit.setEnabled(not scanning)
        self.destination_edit.setEnabled(not scanning)
