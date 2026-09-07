"""Gerenciador dedicado de scans MAME e aquisição do catálogo ListXML."""

from __future__ import annotations

import json
from datetime import datetime

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from ..runtime.paths import database_path
from ..services.mame_catalog_service import MameCatalogError, MameCatalogService
from ..services.scan_repository import ScanRepository
from .scan_phase_page import _SystemScanTab


class _MameCatalogWorker(QThread):
    """Executa a captura/normalização do catálogo fora da thread da interface."""

    completed = Signal(object)
    failed = Signal(str)
    log = Signal(str)

    def __init__(self, force: bool, parent=None) -> None:
        super().__init__(parent)
        self.force = force

    def run(self) -> None:
        try:
            service = MameCatalogService(logger=self.log.emit)
            result = service.ingest(force=self.force)
            self.completed.emit(result)
        except (MameCatalogError, OSError, RuntimeError, ValueError) as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class MameScanPage(QWidget):
    """Tela MAME com aquisição do catálogo, scans físicos e histórico."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._catalog_worker: _MameCatalogWorker | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("MAME — CATÁLOGO E SCANS")
        title.setProperty("role", "title")
        root.addWidget(title)
        description = QLabel(
            "O catálogo é a fonte estrutural do SERM. A aquisição usa mame.exe -listxml sem padrões, "
            "preserva o XML bruto e normaliza máquinas, ROMs, CHDs, displays, input, chips, dispositivos, "
            "slots, BIOS e demais elementos. Depois sincroniza folders/*.ini e hash/*.xml."
        )
        description.setWordWrap(True)
        root.addWidget(description)
        root.addWidget(self._catalog_panel())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._history_panel())
        self.scan_tab = _SystemScanTab("MAME", self)
        splitter.addWidget(self.scan_tab)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 900])
        root.addWidget(splitter, 1)

    def _catalog_panel(self) -> QWidget:
        box = QGroupBox("Construção do banco MAME / ListXML")
        layout = QVBoxLayout(box)
        options = QHBoxLayout()
        self.catalog_complete = QCheckBox("Catálogo completo — todos os sistemas e dispositivos")
        self.catalog_complete.setChecked(True)
        self.catalog_complete.setEnabled(False)
        self.catalog_force = QCheckBox("Forçar reimportação mesmo com o mesmo SHA-256")
        self.catalog_auxiliary = QCheckBox("Sincronizar folders/*.ini e hash/*.xml")
        self.catalog_auxiliary.setChecked(True)
        self.catalog_auxiliary.setEnabled(False)
        options.addWidget(self.catalog_complete)
        options.addWidget(self.catalog_auxiliary)
        options.addWidget(self.catalog_force)
        options.addStretch()
        layout.addLayout(options)
        actions = QHBoxLayout()
        self.catalog_button = QPushButton("CRIAR / ATUALIZAR BANCO MAME")
        self.catalog_button.clicked.connect(self.build_catalog)
        actions.addWidget(self.catalog_button)
        self.catalog_refresh_button = QPushButton("ATUALIZAR STATUS")
        self.catalog_refresh_button.clicked.connect(self._catalog_status)
        actions.addWidget(self.catalog_refresh_button)
        actions.addStretch()
        layout.addLayout(actions)
        self.catalog_status = QLabel(
            "Pronto. A operação completa é a recomendada para alimentar o banco relacional do SERM."
        )
        self.catalog_status.setWordWrap(True)
        layout.addWidget(self.catalog_status)
        self.catalog_log = QListWidget()
        self.catalog_log.setMaximumHeight(105)
        layout.addWidget(self.catalog_log)
        return box

    def build_catalog(self) -> None:
        if self._catalog_worker is not None and self._catalog_worker.isRunning():
            return
        self.catalog_button.setEnabled(False)
        self.catalog_refresh_button.setEnabled(False)
        self.catalog_log.clear()
        self.catalog_status.setText("Executando mame.exe -listxml e construindo o banco relacional…")
        self._catalog_worker = _MameCatalogWorker(self.catalog_force.isChecked(), self)
        self._catalog_worker.log.connect(self._catalog_log)
        self._catalog_worker.completed.connect(self._catalog_completed)
        self._catalog_worker.failed.connect(self._catalog_failed)
        self._catalog_worker.finished.connect(self._catalog_finished)
        self._catalog_worker.start()

    def _catalog_log(self, message: str) -> None:
        self.catalog_log.addItem(message)
        self.catalog_log.scrollToBottom()

    def _catalog_completed(self, result: dict[str, object]) -> None:
        ini_results = result.get("ini_results") or []
        self.catalog_status.setText(
            f"Catálogo concluído: MAME {result.get('mame_build') or 'desconhecido'} | "
            f"máquinas={int(result.get('machine_count') or 0):,} | import_id={result.get('import_id')} | "
            f"fontes auxiliares={len(ini_results):,} | deduplicado={bool(result.get('deduplicated'))}."
        )
        self.refresh()

    def _catalog_failed(self, message: str) -> None:
        self.catalog_status.setText(f"Falha na construção do catálogo: {message}")
        self._catalog_log(f"ERRO | {message}")

    def _catalog_finished(self) -> None:
        worker = self._catalog_worker
        self._catalog_worker = None
        self.catalog_button.setEnabled(True)
        self.catalog_refresh_button.setEnabled(True)
        if worker is not None:
            worker.deleteLater()

    def _catalog_status(self) -> None:
        try:
            with __import__("sqlite3").connect(database_path()) as db:
                row = db.execute(
                    "SELECT mame_build,machine_count,imported_at,source_hash,status FROM mame_listxml_import ORDER BY id DESC LIMIT 1"
                ).fetchone()
            if row is None:
                self.catalog_status.setText("Nenhum ListXML MAME foi persistido ainda.")
                return
            self.catalog_status.setText(
                f"Último catálogo: MAME {row[0] or '—'} | máquinas={int(row[1] or 0):,} | "
                f"status={row[4] or '—'} | importado={row[2] or '—'} | SHA-256={str(row[3] or '')[:16]}"
            )
        except Exception as exc:  # noqa: BLE001
            self.catalog_status.setText(f"Não foi possível consultar o catálogo: {exc}")

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
        self._catalog_status()
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
            f"ID: {scan_id}\nTipo: {row.get('scan_type') or 'full'}\n"
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
            self, "Deletar scan",
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
