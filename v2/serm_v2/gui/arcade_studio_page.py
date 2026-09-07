"""Interface operacional do Arcade Studio V2."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QProgressBar, QPushButton,
    QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..models.arcade import RomStatus
from ..runtime.paths import database_path, scans_root
from ..services.arcade.chd_audit import ArcadeChdAuditService, ChdAuditResult
from ..services.arcade.scan_comparison import ArcadeScanComparisonService, MachineComparison, ScanComparisonResult
from ..services.chd_header import ChdFormatError, ChdHeaderReader
from .mame_filters_panel import MameFiltersPanel

_STATUS_LABELS = {
    RomStatus.OK: "OK", RomStatus.REPAIRABLE: "RECONSTRUÍVEL", RomStatus.INCOMPLETE: "INCOMPLETO",
    RomStatus.MISSING: "AUSENTE", RomStatus.INVALID: "INVÁLIDO", RomStatus.UNKNOWN: "NÃO AUDITADO",
}
_STATUS_COLORS = {
    RomStatus.OK: QColor("#36c96f"), RomStatus.REPAIRABLE: QColor("#f0c43c"),
    RomStatus.INCOMPLETE: QColor("#f39c3d"), RomStatus.MISSING: QColor("#8b9299"),
    RomStatus.INVALID: QColor("#e05252"), RomStatus.UNKNOWN: QColor("#737b84"),
}


def _status_icon(status: RomStatus, size: int = 16) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("#15191d"))
    painter.setBrush(_STATUS_COLORS[status])
    painter.drawEllipse(2, 2, size - 4, size - 4)
    painter.end()
    return QIcon(pixmap)


def _set_status_visual(item: QTableWidgetItem | QTreeWidgetItem, status: RomStatus) -> None:
    if isinstance(item, QTreeWidgetItem):
        item.setIcon(0, _status_icon(status))
        item.setForeground(0, QColor("#e8edf2"))
        item.setBackground(0, _STATUS_COLORS[status].darker(420))
        item.setToolTip(0, _STATUS_LABELS[status])
    else:
        item.setIcon(_status_icon(status))
        item.setForeground(QColor("#e8edf2"))
        item.setBackground(_STATUS_COLORS[status].darker(420))
        item.setToolTip(_STATUS_LABELS[status])


class _ArcadeStudioWorker(QObject):
    imports_ready = Signal(object)
    comparison_ready = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, database: Path, operation: str, import_id: int | None = None, scan_path: Path | None = None) -> None:
        super().__init__()
        self.database = database
        self.operation = operation
        self.import_id = import_id
        self.scan_path = scan_path

    def run(self) -> None:
        try:
            if self.operation == "imports":
                self.imports_ready.emit(self._load_imports())
            elif self.operation == "compare":
                if self.import_id is None or self.scan_path is None:
                    raise ValueError("Importação ListXML ou scan não selecionado.")
                self.comparison_ready.emit(self._compare())
            else:
                raise ValueError(f"Operação desconhecida: {self.operation}")
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()

    def _connect(self) -> sqlite3.Connection:
        if not self.database.is_file():
            raise RuntimeError(f"Banco SERM não encontrado: {self.database}")
        db = sqlite3.connect(self.database)
        db.row_factory = sqlite3.Row
        return db

    def _load_imports(self) -> list[dict[str, object]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT i.id,i.mame_build,i.xml_path,i.machine_count,i.byte_length,i.imported_at,i.source_hash,i.status
                   FROM mame_listxml_import i ORDER BY i.id DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    def _compare(self) -> ScanComparisonResult:
        with self._connect() as db:
            row = db.execute(
                """SELECT i.id,i.mame_build,i.xml_path,i.machine_count,d.xml_text
                   FROM mame_listxml_import i
                   LEFT JOIN mame_listxml_document d ON d.import_id=i.id
                   WHERE i.id=? AND i.status='completed'""",
                (self.import_id,),
            ).fetchone()
        if row is None:
            raise ValueError("A importação ListXML selecionada não está disponível no banco SERM.")
        xml_text = str(row["xml_text"] or "")
        if not xml_text:
            xml_path = Path(str(row["xml_path"] or ""))
            if not xml_path.is_file():
                raise ValueError("A importação selecionada não possui o documento ListXML armazenado.")
            xml_text = xml_path.read_text(encoding="utf-8")
        return ArcadeScanComparisonService().compare(xml_text, self.scan_path)


class ArcadeStudioPage(QWidget):
    """Painel central do catálogo MAME, filtros, comparação física e reconstrução."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._database = database_path()
        self._comparison: ScanComparisonResult | None = None
        self._last_chd_audit: ChdAuditResult | None = None
        self._worker_thread: QThread | None = None
        self._worker: _ArcadeStudioWorker | None = None
        self._build_ui()
        self._start_import_load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("ARCADE STUDIO")
        title.setProperty("role", "title")
        layout.addWidget(title)
        intro = QLabel(
            "ListXML MAME = conteúdo esperado. Scan JSON = inventário físico. "
            "O Studio concentra catálogo, comparação, filtros, auditoria CHD e reconstrução V2."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._catalog_tab(), "Catálogo / Comparação")
        self.mame_filter_tab = MameFiltersPanel(self)
        self.tabs.addTab(self.mame_filter_tab, "Filtros MAME")
        self.tabs.addTab(self._chd_tab(), "Auditoria CHD")
        self.tabs.addTab(self._reconstruction_tab(), "Reconstrução")
        self.tabs.currentChanged.connect(self._tab_changed)
        layout.addWidget(self.tabs, 1)

    def _catalog_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        source_box = QGroupBox("Fontes da comparação")
        source_form = QFormLayout(source_box)
        listxml_row = QHBoxLayout()
        self.listxml_choice = QComboBox()
        self.listxml_choice.setMinimumWidth(500)
        self.listxml_choice.currentIndexChanged.connect(self._listxml_changed)
        reload_catalog = QPushButton("ATUALIZAR LISTXML")
        reload_catalog.clicked.connect(self._start_import_load)
        listxml_row.addWidget(self.listxml_choice, 1)
        listxml_row.addWidget(reload_catalog)
        source_form.addRow("ListXML / banco SERM:", listxml_row)
        self.listxml_source = QLineEdit()
        self.listxml_source.setReadOnly(True)
        source_form.addRow("Documento:", self.listxml_source)
        scan_row = QHBoxLayout()
        self.scan_source = QLineEdit()
        self.scan_source.setReadOnly(True)
        choose_scan = QPushButton("ESCOLHER SCAN JSON…")
        choose_scan.clicked.connect(self._choose_scan)
        scan_row.addWidget(self.scan_source, 1)
        scan_row.addWidget(choose_scan)
        source_form.addRow("Scan físico:", scan_row)
        actions = QHBoxLayout()
        self.compare_button = QPushButton("CARREGAR LISTXML + COMPARAR SCAN")
        self.compare_button.clicked.connect(self._compare_scan)
        refresh_scans = QPushButton("ATUALIZAR LISTA DE SCANS")
        refresh_scans.clicked.connect(self._refresh_scan_choices)
        actions.addWidget(self.compare_button)
        actions.addWidget(refresh_scans)
        actions.addStretch()
        source_form.addRow("Ação:", actions)
        layout.addWidget(source_box)
        self.load_progress = QProgressBar()
        self.load_progress.setRange(0, 1)
        self.load_progress.setValue(0)
        layout.addWidget(self.load_progress)
        self.scan_info = QLabel("Lendo catálogo MAME do banco SERM…")
        self.scan_info.setWordWrap(True)
        layout.addWidget(self.scan_info)
        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filtrar machine, descrição ou fabricante…")
        self.search.returnPressed.connect(self._apply_machine_filter)
        controls.addWidget(self.search, 1)
        filter_button = QPushButton("FILTRAR")
        filter_button.clicked.connect(self._apply_machine_filter)
        controls.addWidget(filter_button)
        layout.addLayout(controls)
        self.comparison_status = QLabel("Aguardando leitura do banco SERM…")
        self.comparison_status.setWordWrap(True)
        layout.addWidget(self.comparison_status)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.catalog_table = QTableWidget(0, 9)
        self.catalog_table.setHorizontalHeaderLabels(["Status", "Machine", "Descrição", "Parent", "Ano", "Fabricante", "ROMs", "CHDs", "Detalhamento"])
        self.catalog_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.catalog_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.catalog_table.setAlternatingRowColors(True)
        self.catalog_table.setSortingEnabled(True)
        self.catalog_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.catalog_table.horizontalHeader().setStretchLastSection(True)
        self.catalog_table.itemSelectionChanged.connect(self._show_machine)
        splitter.addWidget(self.catalog_table)
        tree_box = QGroupBox("Árvore de componentes — ListXML × físico")
        tree_layout = QVBoxLayout(tree_box)
        self.rom_tree = QTreeWidget()
        self.rom_tree.setHeaderLabels(["Componente", "Status", "Esperado", "Físico", "Detalhes"])
        self.rom_tree.setAlternatingRowColors(True)
        self.rom_tree.setRootIsDecorated(True)
        self.rom_tree.header().setStretchLastSection(True)
        tree_layout.addWidget(self.rom_tree)
        splitter.addWidget(tree_box)
        splitter.setSizes([430, 300])
        layout.addWidget(splitter, 1)
        self.catalog_details = QLabel("Selecione uma machine após carregar um scan.")
        self.catalog_details.setWordWrap(True)
        layout.addWidget(self.catalog_details)
        return page

    def _chd_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        box = QGroupBox("Auditoria da origem física")
        form = QFormLayout(box)
        self.chd_source = QLineEdit()
        self.chd_source.setReadOnly(True)
        choose_source = QPushButton("SELECIONAR PASTA…")
        choose_source.clicked.connect(self._choose_chd_source)
        source_row = QHBoxLayout()
        source_row.addWidget(self.chd_source, 1)
        source_row.addWidget(choose_source)
        form.addRow("Pasta CHD:", source_row)
        self.chd_audit_button = QPushButton("AUDITAR CHDS")
        self.chd_audit_button.clicked.connect(self._audit_chds)
        form.addRow("Ação:", self.chd_audit_button)
        layout.addWidget(box)
        self.chd_summary = QLabel("Selecione uma pasta contendo CHDs para iniciar a auditoria.")
        self.chd_summary.setWordWrap(True)
        layout.addWidget(self.chd_summary)
        self.chd_table = QTableWidget(0, 7)
        self.chd_table.setHorizontalHeaderLabels(["Status", "Machine", "Disco", "Arquivo", "Raw SHA1", "Versão", "Detalhes"])
        self.chd_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.chd_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.chd_table.horizontalHeader().setStretchLastSection(True)
        self.chd_table.setAlternatingRowColors(True)
        self.chd_table.itemSelectionChanged.connect(self._show_chd_audit_selection)
        layout.addWidget(self.chd_table, 1)
        self.chd_progress = QProgressBar()
        self.chd_progress.setRange(0, 1)
        self.chd_progress.setValue(0)
        layout.addWidget(self.chd_progress)
        detail_box = QGroupBox("Validação individual")
        detail_form = QFormLayout(detail_box)
        self.chd_path = QLineEdit()
        self.chd_path.setReadOnly(True)
        choose_file = QPushButton("SELECIONAR CHD…")
        choose_file.clicked.connect(self._choose_chd)
        file_row = QHBoxLayout()
        file_row.addWidget(self.chd_path, 1)
        file_row.addWidget(choose_file)
        detail_form.addRow("Arquivo:", file_row)
        self.chd_result = QListWidget()
        detail_form.addRow("Cabeçalho:", self.chd_result)
        layout.addWidget(detail_box)
        return page

    def _reconstruction_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        warning = QLabel(
            "A reconstrução física será executada exclusivamente pelo SERM. "
            "O plano usa parent/merge e as identidades físicas auditadas; nenhuma ferramenta externa participa do backend."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)
        self.reconstruction_machine = QLineEdit()
        self.reconstruction_machine.setPlaceholderText("machine")
        self.reconstruction_disk = QLineEdit()
        self.reconstruction_disk.setPlaceholderText("nome do disco/CHD")
        form = QFormLayout()
        form.addRow("Machine:", self.reconstruction_machine)
        form.addRow("Disco:", self.reconstruction_disk)
        layout.addLayout(form)
        self.reconstruction_result = QLabel("Selecione uma machine no resultado da comparação para preparar o plano.")
        self.reconstruction_result.setWordWrap(True)
        layout.addWidget(self.reconstruction_result)
        layout.addStretch()
        return page

    def _tab_changed(self, index: int) -> None:
        if index == 1 and hasattr(self, "mame_filter_tab"):
            self.mame_filter_tab.refresh()

    def closeEvent(self, event) -> None:
        if self._worker_thread is not None and self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait(2000)
        super().closeEvent(event)

    def _start_worker(self, operation: str, import_id: int | None = None, scan_path: Path | None = None) -> None:
        if self._worker_thread is not None and self._worker_thread.isRunning():
            return
        self._worker_thread = QThread(self)
        self._worker = _ArcadeStudioWorker(self._database, operation, import_id, scan_path)
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.finished.connect(self._worker_finished)
        self._worker.failed.connect(self._worker_failed)
        if operation == "imports":
            self._worker.imports_ready.connect(self._imports_loaded)
        else:
            self._worker.comparison_ready.connect(self._comparison_loaded)
        self._worker_thread.start()

    def _worker_finished(self) -> None:
        self._worker = None
        self._worker_thread = None
        self.load_progress.setRange(0, 1)
        self.load_progress.setValue(1)
        self.compare_button.setEnabled(True)

    def _worker_failed(self, message: str) -> None:
        self._comparison = None
        self.catalog_table.setRowCount(0)
        self.rom_tree.clear()
        self.comparison_status.setText(f"Falha: {message}")
        self.scan_info.setText("Operação não concluída.")

    def _start_import_load(self) -> None:
        self.compare_button.setEnabled(False)
        self.load_progress.setRange(0, 0)
        self.scan_info.setText("Lendo as importações ListXML persistidas no banco SERM…")
        self._start_worker("imports")

    def _imports_loaded(self, rows: list[dict[str, object]]) -> None:
        self.listxml_choice.blockSignals(True)
        self.listxml_choice.clear()
        for row in rows:
            label = f"ID {row['id']} | MAME {row.get('mame_build') or 'desconhecido'} | {int(row.get('machine_count') or 0):,} machines | {row.get('status') or '?'} | {row.get('imported_at') or ''}"
            self.listxml_choice.addItem(label, int(row['id']))
        self.listxml_choice.blockSignals(False)
        if rows:
            self.listxml_choice.setCurrentIndex(0)
            self._listxml_changed(0)
            self.scan_info.setText(f"Banco SERM: {len(rows):,} importação(ões) ListXML disponível(is). Selecione a versão desejada e depois o snapshot físico.")
        else:
            self.listxml_source.setText("Nenhuma importação ListXML MAME no banco SERM.")
            self.comparison_status.setText("Nenhum catálogo MAME disponível.")
        self._refresh_scan_choices()

    def _listxml_changed(self, index: int) -> None:
        if index < 0:
            return
        import_id = self.listxml_choice.itemData(index)
        if import_id is None:
            return
        try:
            with sqlite3.connect(self._database) as db:
                row = db.execute(
                    "SELECT xml_path,mame_build,machine_count,source_hash FROM mame_listxml_import WHERE id=?",
                    (int(import_id),),
                ).fetchone()
        except sqlite3.Error as exc:
            self.listxml_source.setText(f"Erro ao ler banco SERM: {exc}")
            return
        if row is None:
            self.listxml_source.setText("Importação não encontrada.")
            return
        self.listxml_source.setText(str(row[0] or "documento lossless armazenado em mame_listxml_document"))
        self.comparison_status.setText(f"ListXML selecionado: importação {import_id} | MAME {row[1] or '—'} | {int(row[2] or 0):,} machines | SHA-256={str(row[3] or '')[:16]}")

    def _refresh_scan_choices(self) -> None:
        root = scans_root() / "mame"
        files = sorted(root.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True) if root.is_dir() else []
        preferred = root / "MAME - 0.289_mame0289 - Arcade.json"
        selected = preferred if preferred.is_file() else (files[0] if files else None)
        self.scan_source.setText(str(selected) if selected else "Nenhum scan MAME JSON encontrado em data/scans/mame.")

    def _choose_scan(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar snapshot JSON do scan MAME", str(scans_root() / "mame"), "Scan SERM (*.json);;JSON (*.json)")
        if path:
            self.scan_source.setText(path)
            self._compare_scan()

    def _compare_scan(self) -> None:
        import_id = self.listxml_choice.itemData(self.listxml_choice.currentIndex())
        scan_text = self.scan_source.text().strip()
        if import_id is None:
            self.comparison_status.setText("Selecione uma importação ListXML no banco SERM.")
            return
        if not scan_text or not Path(scan_text).is_file():
            self.comparison_status.setText("Selecione um arquivo JSON de scan MAME válido.")
            return
        self.compare_button.setEnabled(False)
        self.load_progress.setRange(0, 0)
        self.scan_info.setText("Lendo o ListXML selecionado e comparando o snapshot físico. A interface continuará responsiva…")
        self._start_worker("compare", int(import_id), Path(scan_text))

    def _comparison_loaded(self, comparison: ScanComparisonResult) -> None:
        self._comparison = comparison
        self.scan_info.setText(f"Scan carregado: {comparison.scan_path} | scan_id={comparison.scan_id or '—'} | catálogo={comparison.catalog_label or '—'} | machines comparadas={comparison.machine_count:,} | componentes esperados={comparison.component_count:,} | itens físicos fora do ListXML={comparison.orphan_items:,}")
        counts = comparison.status_counts
        self.comparison_status.setText(f"Resultado: OK={counts[RomStatus.OK.value]:,} | AUSENTE={counts[RomStatus.MISSING.value]:,} | INVÁLIDO={counts[RomStatus.INVALID.value]:,} | RECONSTRUÍVEL={counts[RomStatus.REPAIRABLE.value]:,} | NÃO AUDITADO={counts[RomStatus.UNKNOWN.value]:,}")
        self._apply_machine_filter(select_first=True)

    def _apply_machine_filter(self, select_first: bool = False) -> None:
        if self._comparison is None:
            self.catalog_table.setRowCount(0)
            self.rom_tree.clear()
            return
        text = self.search.text().strip().casefold()
        rows = [m for m in self._comparison.machines if not text or text in m.machine_name.casefold() or text in m.description.casefold() or text in (m.manufacturer or "").casefold()][:1000]
        self.catalog_table.setSortingEnabled(False)
        self.catalog_table.clearContents()
        self.catalog_table.setRowCount(len(rows))
        for index, machine in enumerate(rows):
            status_item = QTableWidgetItem(_STATUS_LABELS[machine.status])
            status_item.setData(Qt.ItemDataRole.UserRole, machine.machine_name)
            _set_status_visual(status_item, machine.status)
            self.catalog_table.setItem(index, 0, status_item)
            ok = sum(i.status is RomStatus.OK for i in machine.components)
            missing = sum(i.status is RomStatus.MISSING for i in machine.components)
            invalid = sum(i.status is RomStatus.INVALID for i in machine.components)
            repairable = sum(i.status is RomStatus.REPAIRABLE for i in machine.components)
            values = (machine.machine_name, machine.description, machine.parent or "—", machine.year or "—", machine.manufacturer or "—", str(machine.rom_count), str(machine.chd_count), f"OK {ok} | ausentes {missing} | inválidos {invalid} | reconstruíveis {repairable}")
            for column, value in enumerate(values, start=1):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, machine.machine_name)
                self.catalog_table.setItem(index, column, item)
        self.catalog_table.setSortingEnabled(True)
        self.catalog_table.resizeColumnsToContents()
        if select_first and rows:
            self.catalog_table.setCurrentCell(0, 0)
            self.catalog_table.selectRow(0)
            self._show_machine()
        elif not rows:
            self.rom_tree.clear()

    def _selected_machine(self) -> MachineComparison | None:
        if self._comparison is None:
            return None
        selected = self.catalog_table.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.catalog_table.item(selected[0].row(), 0)
        name = item.data(Qt.ItemDataRole.UserRole) if item else None
        return next((m for m in self._comparison.machines if m.machine_name == name), None)

    def _show_machine(self) -> None:
        machine = self._selected_machine()
        if machine is None:
            return
        self.reconstruction_machine.setText(machine.machine_name)
        ok = sum(i.status is RomStatus.OK for i in machine.components)
        missing = sum(i.status is RomStatus.MISSING for i in machine.components)
        invalid = sum(i.status is RomStatus.INVALID for i in machine.components)
        repairable = sum(i.status is RomStatus.REPAIRABLE for i in machine.components)
        self.catalog_details.setText(f"{machine.machine_name} | parent={machine.parent or '—'} | ano={machine.year or '—'} | fabricante={machine.manufacturer or '—'} | ROMs={machine.rom_count:,} | CHDs={machine.chd_count:,} | OK={ok:,} | ausentes={missing:,} | inválidos={invalid:,} | reconstruíveis={repairable:,}")
        self._populate_component_tree(machine)
        disks = [i for i in machine.components if i.expected.component_type == "CHD"]
        self.reconstruction_disk.setText(disks[0].expected.name if disks else "")
        self.reconstruction_result.setText(f"Machine {machine.machine_name}: {ok:,} componentes confirmados, {missing:,} ausentes, {invalid:,} inválidos e {repairable:,} reconstruíveis.")

    def _populate_component_tree(self, machine: MachineComparison) -> None:
        self.rom_tree.clear()
        root = QTreeWidgetItem([machine.machine_name, _STATUS_LABELS[machine.status], "ListXML", "scan físico", machine.description])
        _set_status_visual(root, machine.status)
        root.setExpanded(True)
        self.rom_tree.addTopLevelItem(root)
        rom_group = QTreeWidgetItem([f"ROMs ({machine.rom_count:,})", "", "esperadas", "", ""])
        root.addChild(rom_group)
        rom_group.setExpanded(True)
        chd_group = QTreeWidgetItem([f"CHDs ({machine.chd_count:,})", "", "esperados", "", ""])
        root.addChild(chd_group)
        chd_group.setExpanded(True)
        for component in machine.components:
            target = rom_group if component.expected.component_type == "ROM" else chd_group
            expected = component.expected
            expected_hash = expected.sha1 or expected.md5 or expected.crc or "—"
            physical = component.physical_path or "—"
            actual_hash = component.actual_sha1 or component.actual_md5 or component.actual_crc or "—"
            detail = f"esperado hash={expected_hash} | físico hash={actual_hash} | tamanho={expected.size if expected.size is not None else '—'}"
            detail += f" | merge={expected.merge}" if expected.merge else ""
            detail += f" | {component.message}" if component.message else ""
            item = QTreeWidgetItem([expected.name, _STATUS_LABELS[component.status], expected_hash, physical, detail])
            _set_status_visual(item, component.status)
            target.addChild(item)

    def _choose_chd_source(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Selecionar pasta de CHDs")
        if path:
            self.chd_source.setText(path)

    def _audit_chds(self) -> None:
        source_text = self.chd_source.text().strip()
        if not source_text:
            self.chd_summary.setText("Selecione primeiro a pasta de CHDs.")
            return
        self.chd_audit_button.setEnabled(False)
        self.chd_progress.setRange(0, 0)
        try:
            result = ArcadeChdAuditService().audit(source=Path(source_text), database=self._database)
            self._last_chd_audit = result
            self._show_chd_audit(result)
        except (OSError, RuntimeError, sqlite3.Error) as exc:
            self.chd_summary.setText(f"Erro na auditoria: {exc}")
        finally:
            self.chd_progress.setRange(0, 1)
            self.chd_progress.setValue(1)
            self.chd_audit_button.setEnabled(True)

    def _show_chd_audit(self, result: ChdAuditResult) -> None:
        self.chd_summary.setText(f"Arquivos: {result.files_scanned:,} | válidos: {result.valid_files:,} | OK: {result.matched_files:,} | ausentes: {result.missing_disks:,} | ambíguos: {result.ambiguous_disks:,} | inválidos: {result.invalid_files:,} | órfãos: {result.orphan_files:,}")
        self.chd_table.setRowCount(len(result.records))
        for row_index, record in enumerate(result.records):
            values = (record.status, record.machine_name or "—", record.disk_name or "—", record.path or "—", record.actual_sha1 or record.expected_sha1 or "—", record.version if record.version is not None else "—", record.message)
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, record.path)
                if column == 0:
                    visual = {"OK": RomStatus.OK, "MISSING": RomStatus.MISSING, "AMBIGUOUS": RomStatus.REPAIRABLE, "INVALID": RomStatus.INVALID, "ORPHAN": RomStatus.INCOMPLETE}.get(str(value).upper(), RomStatus.UNKNOWN)
                    _set_status_visual(item, visual)
                self.chd_table.setItem(row_index, column, item)
        self.chd_table.resizeColumnsToContents()

    def _show_chd_audit_selection(self) -> None:
        selected = self.chd_table.selectionModel().selectedRows()
        if not selected:
            return
        path = self.chd_table.item(selected[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if path:
            self.chd_path.setText(str(path))

    def _choose_chd(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar CHD", "", "CHD (*.chd)")
        if not path:
            return
        self.chd_path.setText(path)
        self.chd_result.clear()
        try:
            header = ChdHeaderReader().read(Path(path))
        except (OSError, ChdFormatError) as exc:
            self.chd_result.addItem(QListWidgetItem(f"ERRO: {exc}"))
            return
        values = (("Versão", header.version), ("Tamanho lógico", f"{header.logical_bytes:,} bytes"), ("Hunk", f"{header.hunk_bytes:,} bytes"), ("Raw SHA1", header.raw_sha1 or "—"), ("SHA1 do CHD", header.sha1 or "—"), ("MD5", header.md5 or "—"), ("Parent SHA1", header.parent_sha1 or "—"), ("Tamanho do arquivo", f"{header.file_size:,} bytes"))
        for label, value in values:
            self.chd_result.addItem(QListWidgetItem(f"{label}: {value}"))


__all__ = ["ArcadeStudioPage"]
