"""Gerenciador dedicado de scans MAME: novo scan e histórico persistido."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import database_path
from ..services.scan_repository import ScanRepository
from .scan_phase_page import _SystemScanTab


class MameScanPage(QWidget):
    """Tela MAME com configuração de scan, histórico e ciclo de vida dos scans."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("MAME — SCANS")
        title.setProperty("role", "title")
        root.addWidget(title)
        description = QLabel(
            "Cada execução cria um novo snapshot. Um scan concluído pode ser selecionado no histórico "
            "ou excluído sem apagar os diretórios configurados para o próximo scan."
        )
        description.setWordWrap(True)
        root.addWidget(description)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._history_panel())
        self.scan_tab = _SystemScanTab("MAME", self)
        splitter.addWidget(self.scan_tab)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 900])
        root.addWidget(splitter, 1)

    def _history_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        box = QGroupBox("Scans MAME criados")
        box_layout = QVBoxLayout(box)
        self.scan_list = QListWidget()
        self.scan_list.currentItemChanged.connect(self._history_selected)
        box_layout.addWidget(self.scan_list, 1)

        self.history_info = QLabel("Nenhum scan selecionado.")
        self.history_info.setWordWrap(True)
        box_layout.addWidget(self.history_info)

        actions = QHBoxLayout()
        self.new_scan_button = QPushButton("NOVO SCAN")
        self.delete_scan_button = QPushButton("DELETAR SCAN")
        self.refresh_button = QPushButton("ATUALIZAR")
        self.new_scan_button.clicked.connect(self.new_scan)
        self.delete_scan_button.clicked.connect(self.delete_scan)
        self.refresh_button.clicked.connect(self.refresh)
        actions.addWidget(self.new_scan_button)
        actions.addWidget(self.delete_scan_button)
        actions.addWidget(self.refresh_button)
        box_layout.addLayout(actions)
        layout.addWidget(box, 1)
        return panel

    @staticmethod
    def _format_timestamp(value: object) -> str:
        try:
            return datetime.fromtimestamp(float(value)).strftime("%d/%m/%Y %H:%M:%S")
        except (TypeError, ValueError, OSError, OverflowError):
            return "data desconhecida"

    @staticmethod
    def _counts(row: dict) -> dict[str, int]:
        try:
            raw = json.loads(row.get("status_counts_json") or "{}")
            return {str(key): int(value) for key, value in raw.items()}
        except (TypeError, ValueError, AttributeError):
            return {}

    def refresh(self) -> None:
        self.scan_tab.refresh()
        repository = ScanRepository(database_path())
        rows = repository.list_for_source("MAME")
        current_id = None
        current = self.scan_list.currentItem()
        if current is not None:
            current_id = current.data(Qt.ItemDataRole.UserRole)

        self.scan_list.blockSignals(True)
        self.scan_list.clear()
        selected_item = None
        for row in rows:
            scan_id = str(row.get("scan_id") or "")
            counts = self._counts(row)
            label = str(row.get("catalog_label") or "MAME")
            scan_type = str(row.get("scan_type") or "full")
            text = (
                f"{label} • {scan_type}\n"
                f"{self._format_timestamp(row.get('started_at'))} • "
                f"C {counts.get('CURRENT', 0):,} / M {counts.get('MISSING', 0):,} / W {counts.get('WRONG', 0):,}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, scan_id)
            item.setToolTip(str(row.get("scan_file_path") or ""))
            self.scan_list.addItem(item)
            if scan_id == current_id:
                selected_item = item
        self.scan_list.blockSignals(False)
        if selected_item is not None:
            self.scan_list.setCurrentItem(selected_item)
        elif self.scan_list.count():
            self.scan_list.setCurrentRow(0)
        else:
            self.history_info.setText("Nenhum scan MAME concluído.")
        self.delete_scan_button.setEnabled(self.scan_list.currentItem() is not None)

    def _history_selected(self, current, _previous) -> None:
        if current is None:
            self.history_info.setText("Nenhum scan selecionado.")
            self.delete_scan_button.setEnabled(False)
            return
        scan_id = str(current.data(Qt.ItemDataRole.UserRole) or "")
        row = ScanRepository(database_path()).get(scan_id)
        if row is None:
            self.history_info.setText("Scan não localizado no banco de dados.")
            self.delete_scan_button.setEnabled(False)
            return
        counts = self._counts(row)
        self.history_info.setText(
            f"ID: {scan_id}\n"
            f"Tipo: {row.get('scan_type') or 'full'}\n"
            f"Catálogo: {row.get('catalog_label') or 'MAME'}\n"
            f"Início: {self._format_timestamp(row.get('started_at'))}\n"
            f"CURRENT={counts.get('CURRENT', 0):,} | MISSING={counts.get('MISSING', 0):,} | WRONG={counts.get('WRONG', 0):,}\n"
            f"Arquivo: {row.get('scan_file_path') or '—'}"
        )
        self.delete_scan_button.setEnabled(True)

    def new_scan(self) -> None:
        if self.scan_tab.worker and self.scan_tab.worker.isRunning():
            QMessageBox.information(self, "Novo scan", "Finalize ou cancele o scan em execução antes de iniciar outro.")
            return
        self.scan_list.clearSelection()
        self.scan_tab.log.clear()
        self.scan_tab.status.setText("Novo scan preparado. Configure os diretórios e clique em INICIAR SCAN COMPLETO.")
        self.scan_tab.progress.setValue(0)
        self.scan_tab.progress.setMaximum(1)
        self.scan_tab.refresh()

    def delete_scan(self) -> None:
        item = self.scan_list.currentItem()
        if item is None:
            QMessageBox.information(self, "Deletar scan", "Selecione um scan concluído.")
            return
        scan_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        row = ScanRepository(database_path()).get(scan_id)
        if row is None:
            self.refresh()
            return
        answer = QMessageBox.question(
            self,
            "Deletar scan",
            "O registro, as evidências e o arquivo bruto deste scan serão removidos.\n\n"
            "Os diretórios e as configurações do MAME não serão alterados.\n\nContinuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if ScanRepository(database_path()).delete(scan_id):
            self.history_info.setText(f"Scan {scan_id} deletado.")
        else:
            QMessageBox.warning(self, "Deletar scan", "O scan não pôde ser localizado.")
        self.refresh()


__all__ = ["MameScanPage"]
