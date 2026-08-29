# app/gui/widgets/scan_control_widget.py
"""Widget de controle do Scan Roms com persistência e seletor de set type."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
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

from app.config.app_config import AppConfig


class ScanControlWidget(QWidget):
    """Controles de entrada do scan: XML, perfil, diretórios, opções e set type."""

    generate_xml_requested = Signal()
    select_xml_requested = Signal()
    open_folder_requested = Signal()
    start_scan_requested = Signal()
    stop_scan_requested = Signal()
    export_report_requested = Signal()
    profile_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = AppConfig()
        self._build_ui()
        self._load_from_config()

    def _build_ui(self) -> None:
        """Constrói os controles principais da aba."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(self._build_actions_row())
        layout.addLayout(self._build_xml_row())
        layout.addWidget(self._build_paths_group())
        layout.addWidget(self._build_options_group())

    def _build_actions_row(self) -> QHBoxLayout:
        """Cria a barra de ações do scanner."""
        row = QHBoxLayout()
        self.btn_generate = QPushButton("Gerar LISTXML filtrado")
        self.btn_generate.setToolTip("Gera o LISTXML contendo somente as máquinas selecionadas pelos filtros.")
        self.btn_generate.clicked.connect(self.generate_xml_requested.emit)

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(150)
        self.profile_combo.addItem("(usar perfil da aba Filters)", None)
        self.profile_combo.currentIndexChanged.connect(self.profile_changed.emit)
        self.profile_combo.setToolTip("Seleciona o perfil de filtros utilizado para gerar o LISTXML.")

        self.btn_scan = QPushButton("Iniciar escaneamento")
        self.btn_scan.setToolTip("Inicia um novo scan. A existência de current_scan.jsonl nunca impede uma nova execução.")
        self.btn_scan.clicked.connect(self.start_scan_requested.emit)

        self.btn_stop = QPushButton("Parar")
        self.btn_stop.setToolTip("Solicita o cancelamento do escaneamento.")
        self.btn_stop.clicked.connect(self.stop_scan_requested.emit)
        self.btn_stop.setEnabled(False)

        self.btn_export = QPushButton("Exportar Relatório")
        self.btn_export.setToolTip("Exporta um CSV com as ROMs ausentes/inválidas.")
        self.btn_export.clicked.connect(self.export_report_requested.emit)

        row.addWidget(self.btn_generate)
        row.addWidget(QLabel("Perfil:"))
        row.addWidget(self.profile_combo)
        row.addWidget(self.btn_scan)
        row.addWidget(self.btn_stop)
        row.addWidget(self.btn_export)
        row.addStretch()
        return row

    def _build_xml_row(self) -> QHBoxLayout:
        """Cria os controles do LISTXML ativo."""
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
        """Cria os campos das origens e do destino."""
        group = QGroupBox("Origens das ROMs")
        layout = QGridLayout(group)
        self.source_edits: list[QLineEdit] = []
        for index in range(3):
            label = QLabel(f"Origem {index + 1}:")
            edit = QLineEdit()
            button = QPushButton("Escolher")
            button.clicked.connect(lambda checked=False, target=edit: self._choose_directory(target))
            hbox = QHBoxLayout()
            hbox.addWidget(edit)
            hbox.addWidget(button)
            layout.addWidget(label, 0, index)
            layout.addLayout(hbox, 1, index)
            self.source_edits.append(edit)

        destination_label = QLabel("Destino:")
        self.destination_edit = QLineEdit()
        destination_button = QPushButton("Escolher")
        destination_button.clicked.connect(lambda: self._choose_directory(self.destination_edit))
        destination_row = QHBoxLayout()
        destination_row.addWidget(self.destination_edit)
        destination_row.addWidget(destination_button)
        layout.addWidget(destination_label, 2, 0)
        layout.addLayout(destination_row, 2, 1, 1, 2)
        return group

    def _build_options_group(self) -> QGroupBox:
        """Cria as opções de execução do scanner."""
        group = QGroupBox("Opções do escaneamento")
        layout = QHBoxLayout(group)
        layout.addWidget(QLabel("Workers:"))
        self.worker_spin = QSpinBox()
        self.worker_spin.setRange(1, max(1, os.cpu_count() or 1))
        self.worker_spin.setValue(self._config.scan_workers)
        self.worker_spin.setToolTip(f"Quantidade de máquinas processadas simultaneamente. (Máximo: {self.worker_spin.maximum()})")
        self.worker_spin.valueChanged.connect(self._save_workers)
        layout.addWidget(self.worker_spin)

        layout.addWidget(QLabel("Set:"))
        self.set_type_combo = QComboBox()
        self.set_type_combo.addItem("Split", "split")
        self.set_type_combo.addItem("Non-Merged", "non-merged")
        self.set_type_combo.addItem("Merged", "merged")
        self.set_type_combo.setToolTip("Tipo de set a ser gerado: Split, Non-Merged ou Merged.")
        self.set_type_combo.setItemData(0, "Split: arquivos separados por máquina.", Qt.ToolTipRole)
        self.set_type_combo.setItemData(1, "Non-Merged: cada máquina possui suas próprias cópias.", Qt.ToolTipRole)
        self.set_type_combo.setItemData(2, "Merged: arquivos compartilhados são reunidos.", Qt.ToolTipRole)
        index = self.set_type_combo.findData(self._config.output_layout)
        if index >= 0:
            self.set_type_combo.setCurrentIndex(index)
        self.set_type_combo.currentIndexChanged.connect(self._save_set_type)
        layout.addWidget(self.set_type_combo)

        self.alternate_search_checkbox = QCheckBox("Busca alternativa")
        self.alternate_search_checkbox.setToolTip("Permite procurar uma ROM pelo nome dentro do diretório da própria máquina.")
        layout.addWidget(self.alternate_search_checkbox)
        self.include_chds_checkbox = QCheckBox("Verificar CHDs")
        self.include_chds_checkbox.setChecked(True)
        layout.addWidget(self.include_chds_checkbox)
        layout.addStretch()
        return group

    def _load_from_config(self) -> None:
        """Carrega workers e set type do AppConfig."""
        self.worker_spin.blockSignals(True)
        self.worker_spin.setValue(self._config.scan_workers)
        self.worker_spin.blockSignals(False)
        index = self.set_type_combo.findData(self._config.output_layout)
        if index >= 0:
            self.set_type_combo.setCurrentIndex(index)

    def _save_workers(self, value: int) -> None:
        """Persiste a quantidade de workers."""
        self._config.scan_workers = value
        self._config.save()

    def _save_set_type(self, index: int) -> None:
        """Persiste o tipo de set selecionado."""
        self._config.output_layout = self.set_type_combo.currentData()
        self._config.save()

    def _choose_directory(self, target: QLineEdit) -> None:
        """Abre o seletor de diretório e grava a seleção no campo."""
        current = target.text().strip()
        initial = current if current else str(Path.home())
        selected = QFileDialog.getExistingDirectory(self, "Selecionar diretório", initial)
        if selected:
            target.setText(selected)

    def display_xml(self, path: Path) -> None:
        """Exibe o LISTXML ativo."""
        self.xml_label.setText(str(path))
        self.xml_label.setToolTip(str(path))
        self.xml_label.setStyleSheet("color: green;")

    def clear_xml_display(self) -> None:
        """Limpa a indicação do LISTXML ativo."""
        self.xml_label.setText("Nenhum XML selecionado.")
        self.xml_label.setToolTip("")
        self.xml_label.setStyleSheet("")

    def load_profiles(self, profiles: Iterable[Any], default_id: Any = None) -> None:
        """Carrega os perfis disponíveis."""
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
        """Retorna o ID do perfil selecionado."""
        return self.profile_combo.currentData()

    def current_profile_label(self) -> str:
        """Retorna o nome amigável do perfil selecionado."""
        idx = self.profile_combo.currentIndex()
        return "(usando filtros da aba Filters)" if idx <= 0 else self.profile_combo.currentText()

    def get_rom_paths(self) -> list[Path]:
        """Retorna somente as origens configuradas que existem."""
        paths: list[Path] = []
        for edit in self.source_edits:
            text = edit.text().strip()
            if text:
                path = Path(text).expanduser()
                if path.is_dir():
                    paths.append(path)
        return paths

    def get_destination(self) -> str:
        """Retorna o diretório de destino configurado."""
        return self.destination_edit.text().strip()

    def worker_count(self) -> int:
        """Retorna a quantidade de workers configurada."""
        return max(1, self.worker_spin.value())

    def set_type(self) -> str:
        """Retorna o tipo de set selecionado."""
        return self.set_type_combo.currentData()

    def alternate_search_enabled(self) -> bool:
        """Indica se a busca alternativa está habilitada."""
        return self.alternate_search_checkbox.isChecked()

    def include_chds(self) -> bool:
        """Indica se CHDs devem ser considerados."""
        return self.include_chds_checkbox.isChecked()

    def load_paths_from_config(self, source_dirs: Iterable[Any], destination: Any) -> None:
        """Carrega origens e destino do AppConfig."""
        source_dirs = list(source_dirs or [])
        for index, edit in enumerate(self.source_edits):
            edit.setText(str(source_dirs[index]) if index < len(source_dirs) else "")
        if destination:
            self.destination_edit.setText(str(destination))

    def collect_paths_for_save(self) -> tuple[list[str], str]:
        """Coleta origens e destino para persistência."""
        return [edit.text().strip() for edit in self.source_edits if edit.text().strip()], self.destination_edit.text().strip()

    def set_scanning_state(self, scanning: bool, *, xml_ready: bool) -> None:
        """Atualiza o estado dos controles sem usar current_scan.jsonl como bloqueio.

        A existência de um manifesto anterior não representa uma execução ativa.
        O botão de novo scan permanece disponível mesmo quando XML ainda não foi
        selecionado; nesse caso a aba apresenta a mensagem solicitando o XML.
        """
        self.btn_generate.setEnabled(not scanning)
        self.btn_scan.setEnabled(not scanning)
        self.btn_scan.setToolTip(
            "Inicia um novo escaneamento. current_scan.jsonl existente será substituído somente após sucesso."
            if xml_ready else
            "Inicia um novo escaneamento. Se nenhum LISTXML estiver ativo, selecione ou gere um antes de iniciar."
        )
        self.btn_stop.setEnabled(scanning)
        self.btn_export.setEnabled(not scanning)
        self.worker_spin.setEnabled(not scanning)
        self.set_type_combo.setEnabled(not scanning)
        self.alternate_search_checkbox.setEnabled(not scanning)
        self.include_chds_checkbox.setEnabled(not scanning)
        for edit in self.source_edits:
            edit.setEnabled(not scanning)
        self.destination_edit.setEnabled(not scanning)
