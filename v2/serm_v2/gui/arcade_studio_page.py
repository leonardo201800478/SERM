"""Interface operacional do Arcade Studio V2.

O Studio usa o ListXML importado como fonte de verdade do conteúdo esperado e
permite selecionar qualquer snapshot JSON produzido pelo scan completo do SERM.
A comparação é feita por componente, preservando a evidência física do scan.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models.arcade import RomStatus
from ..runtime.paths import database_path, scans_root
from ..services.arcade.chd_audit import ArcadeChdAuditService, ChdAuditResult
from ..services.arcade.scan_comparison import (
    ArcadeScanComparisonService,
    ComponentComparison,
    MachineComparison,
    ScanComparisonResult,
)
from ..services.chd_header import ChdFormatError, ChdHeaderReader


_STATUS_LABELS = {
    RomStatus.OK: "OK",
    RomStatus.REPAIRABLE: "RECONSTRUÍVEL",
    RomStatus.INCOMPLETE: "INCOMPLETO",
    RomStatus.MISSING: "AUSENTE",
    RomStatus.INVALID: "INVÁLIDO",
    RomStatus.UNKNOWN: "NÃO AUDITADO",
}

_STATUS_COLORS = {
    RomStatus.OK: QColor("#36c96f"),
    RomStatus.REPAIRABLE: QColor("#f0c43c"),
    RomStatus.INCOMPLETE: QColor("#f39c3d"),
    RomStatus.MISSING: QColor("#8b9299"),
    RomStatus.INVALID: QColor("#e05252"),
    RomStatus.UNKNOWN: QColor("#737b84"),
}


def _status_icon(status: RomStatus, size: int = 16) -> QIcon:
    color = _STATUS_COLORS[status]
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("#15191d"))
    painter.setBrush(color)
    painter.drawEllipse(2, 2, size - 4, size - 4)
    painter.end()
    return QIcon(pixmap)


def _set_status_visual(item: QTableWidgetItem | QTreeWidgetItem, status: RomStatus) -> None:
    icon = _status_icon(status)
    if isinstance(item, QTreeWidgetItem):
        item.setIcon(0, icon)
    else:
        item.setIcon(icon)
    item.setForeground(QColor("#e8edf2"))
    item.setBackground(_STATUS_COLORS[status].darker(420))
    item.setToolTip(_STATUS_LABELS[status])


class ArcadeStudioPage(QWidget):
    """Painel central do catálogo MAME, comparação física e reconstrução."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._database = database_path()
        self._comparison: ScanComparisonResult | None = None
        self._last_chd_audit: ChdAuditResult | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("ARCADE STUDIO")
        title.setProperty("role", "title")
        layout.addWidget(title)
        intro = QLabel(
            "ListXML MAME = conteúdo esperado. Scan JSON = inventário físico encontrado. "
            "O Studio confronta os dois e mostra exatamente o que está OK, ausente, "
            "inválido ou reconstruível."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._catalog_tab(), "Catálogo / Comparação")
        self.tabs.addTab(self._chd_tab(), "Auditoria CHD")
        self.tabs.addTab(self._reconstruction_tab(), "Reconstrução")
        layout.addWidget(self.tabs, 1)

    def _catalog_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        source_box = QGroupBox("Fontes da comparação")
        source_form = QFormLayout(source_box)
        self.listxml_source = QLineEdit()
        self.listxml_source.setReadOnly(True)
        source_form.addRow("ListXML:", self.listxml_source)

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

        self.scan_info = QLabel("Nenhum scan físico selecionado.")
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

        self.comparison_status = QLabel("ListXML carregado pelo catálogo SERM: aguardando comparação.")
        self.comparison_status.setWordWrap(True)
        layout.addWidget(self.comparison_status)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.catalog_table = QTableWidget(0, 9)
        self.catalog_table.setHorizontalHeaderLabels([
            "Status", "Machine", "Descrição", "Parent", "Ano", "Fabricante",
            "ROMs", "CHDs", "Detalhamento",
        ])
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
        self.chd_table.setHorizontalHeaderLabels([
            "Status", "Machine", "Disco", "Arquivo", "Raw SHA1", "Versão", "Detalhes",
        ])
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
            "O plano usa parent/merge e as identidades físicas auditadas; nenhuma "
            "ferramenta externa participa do backend."
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
        self.reconstruction_result = QLabel(
            "Selecione uma machine no resultado da comparação para preparar o plano."
        )
        self.reconstruction_result.setWordWrap(True)
        layout.addWidget(self.reconstruction_result)
        layout.addStretch()
        return page

    def refresh(self) -> None:
        self._load_listxml_identity()
        self._refresh_scan_choices()
        if self._comparison is not None:
            self._apply_machine_filter()

    def _load_listxml_identity(self) -> None:
        try:
            with sqlite3.connect(self._database) as db:
                db.row_factory = sqlite3.Row
                row = db.execute(
                    """SELECT i.id,i.mame_build,i.xml_path,i.machine_count,d.xml_text
                       FROM mame_listxml_import i
                       LEFT JOIN mame_listxml_document d ON d.import_id=i.id
                       WHERE i.status='completed'
                       ORDER BY i.id DESC LIMIT 1"""
                ).fetchone()
            if row is None:
                self.listxml_source.setText("Nenhum ListXML MAME importado.")
                self._listxml_text = None
                return
            self._listxml_text = str(row["xml_text"] or "")
            source = row["xml_path"] or "documento armazenado no banco SERM"
            self.listxml_source.setText(str(source))
            self.comparison_status.setText(
                f"ListXML carregado: importação {row['id']} | MAME {row['mame_build'] or '—'} | "
                f"{row['machine_count']:,} machines | fonte: {source}"
            )
        except sqlite3.Error as exc:
            self._listxml_text = None
            self.listxml_source.setText(f"Erro ao carregar ListXML: {exc}")

    def _refresh_scan_choices(self) -> None:
        root = scans_root() / "mame"
        files = sorted(root.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True) if root.is_dir() else []
        preferred = root / "MAME - 0.289_mame0289 - Arcade.json"
        if preferred.is_file():
            self.scan_source.setText(str(preferred))
        elif files and not self.scan_source.text().strip():
            self.scan_source.setText(str(files[0]))
        elif not files and not self.scan_source.text().strip():
            self.scan_source.setText("Nenhum scan MAME JSON encontrado em data/scans/mame.")

    def _choose_scan(self) -> None:
        start = str(scans_root() / "mame")
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar snapshot JSON do scan MAME", start, "Scan SERM (*.json);;JSON (*.json)"
        )
        if path:
            self.scan_source.setText(path)
            self._compare_scan()

    def _compare_scan(self) -> None:
        if not self._listxml_text:
            self._load_listxml_identity()
        scan_text = self.scan_source.text().strip()
        if not self._listxml_text:
            self.comparison_status.setText("Não foi possível carregar o ListXML MAME.")
            return
        if not scan_text or not Path(scan_text).is_file():
            self.comparison_status.setText("Selecione um arquivo JSON de scan MAME válido.")
            return
        self.compare_button.setEnabled(False)
        self.catalog_table.setUpdatesEnabled(False)
        try:
            self._comparison = ArcadeScanComparisonService().compare(
                self._listxml_text, Path(scan_text)
            )
            self.scan_info.setText(
                f"Scan carregado: {self._comparison.scan_path} | "
                f"scan_id={self._comparison.scan_id or '—'} | "
                f"catálogo={self._comparison.catalog_label or '—'} | "
                f"machines comparadas={self._comparison.machine_count:,} | "
                f"componentes esperados={self._comparison.component_count:,} | "
                f"itens físicos fora do ListXML={self._comparison.orphan_items:,}"
            )
            counts = self._comparison.status_counts
            self.comparison_status.setText(
                "Resultado: "
                f"OK={counts[RomStatus.OK.value]:,} | "
                f"AUSENTE={counts[RomStatus.MISSING.value]:,} | "
                f"INVÁLIDO={counts[RomStatus.INVALID.value]:,} | "
                f"RECONSTRUÍVEL={counts[RomStatus.REPAIRABLE.value]:,} | "
                f"NÃO AUDITADO={counts[RomStatus.UNKNOWN.value]:,}"
            )
            self._apply_machine_filter()
        except (OSError, ValueError, sqlite3.Error) as exc:
            self._comparison = None
            self.comparison_status.setText(f"Falha ao comparar ListXML e scan: {exc}")
        finally:
            self.catalog_table.setUpdatesEnabled(True)
            self.compare_button.setEnabled(True)

    def _apply_machine_filter(self) -> None:
        if self._comparison is None:
            self.catalog_table.setRowCount(0)
            return
        text = self.search.text().strip().casefold()
        rows = [
            machine for machine in self._comparison.machines
            if not text or text in machine.machine_name.casefold()
            or text in machine.description.casefold()
            or text in (machine.manufacturer or "").casefold()
        ][:1000]
        self.catalog_table.setSortingEnabled(False)
        self.catalog_table.setRowCount(len(rows))
        for index, machine in enumerate(rows):
            status_item = QTableWidgetItem(_STATUS_LABELS[machine.status])
            status_item.setData(Qt.ItemDataRole.UserRole, machine.machine_name)
            _set_status_visual(status_item, machine.status)
            self.catalog_table.setItem(index, 0, status_item)
            ok = sum(item.status is RomStatus.OK for item in machine.components)
            missing = sum(item.status is RomStatus.MISSING for item in machine.components)
            invalid = sum(item.status is RomStatus.INVALID for item in machine.components)
            repairable = sum(item.status is RomStatus.REPAIRABLE for item in machine.components)
            values = (
                machine.machine_name, machine.description, machine.parent or "—", machine.year or "—",
                machine.manufacturer or "—", str(machine.rom_count), str(machine.chd_count),
                f"OK {ok} | ausentes {missing} | inválidos {invalid} | reconstruíveis {repairable}",
            )
            for column, value in enumerate(values, start=1):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, machine.machine_name)
                self.catalog_table.setItem(index, column, item)
        self.catalog_table.setSortingEnabled(True)
        self.catalog_table.resizeColumnsToContents()

    def _selected_machine(self) -> MachineComparison | None:
        if self._comparison is None:
            return None
        selected = self.catalog_table.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.catalog_table.item(selected[0].row(), 0)
        name = item.data(Qt.ItemDataRole.UserRole) if item else None
        return next((machine for machine in self._comparison.machines if machine.machine_name == name), None)

    def _show_machine(self) -> None:
        machine = self._selected_machine()
        if machine is None:
            return
        self.reconstruction_machine.setText(machine.machine_name)
        ok = sum(item.status is RomStatus.OK for item in machine.components)
        missing = sum(item.status is RomStatus.MISSING for item in machine.components)
        invalid = sum(item.status is RomStatus.INVALID for item in machine.components)
        repairable = sum(item.status is RomStatus.REPAIRABLE for item in machine.components)
        self.catalog_details.setText(
            f"{machine.machine_name} | parent={machine.parent or '—'} | ano={machine.year or '—'} | "
            f"fabricante={machine.manufacturer or '—'} | ROMs={machine.rom_count:,} | CHDs={machine.chd_count:,} | "
            f"OK={ok:,} | ausentes={missing:,} | inválidos={invalid:,} | reconstruíveis={repairable:,}"
        )
        self._populate_component_tree(machine)
        disks = [item for item in machine.components if item.expected.component_type == "CHD"]
        if disks:
            self.reconstruction_disk.setText(disks[0].expected.name)
        else:
            self.reconstruction_disk.clear()
        self.reconstruction_result.setText(
            f"Machine {machine.machine_name}: {ok:,} componentes confirmados, "
            f"{missing:,} ausentes, {invalid:,} inválidos e {repairable:,} reconstruíveis."
        )

    def _populate_component_tree(self, machine: MachineComparison) -> None:
        self.rom_tree.clear()
        root = QTreeWidgetItem([
            machine.machine_name, _STATUS_LABELS[machine.status], "ListXML", "scan físico", machine.description,
        ])
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
            detail = (
                f"esperado hash={expected_hash}"
                f" | físico hash={actual_hash}"
                f" | tamanho={expected.size if expected.size is not None else '—'}"
            )
            if component.expected.merge:
                detail += f" | merge={component.expected.merge}"
            if component.message:
                detail += f" | {component.message}"
            item = QTreeWidgetItem([
                expected.name,
                _STATUS_LABELS[component.status],
                expected_hash,
                physical,
                detail,
            ])
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
        self.chd_summary.setText(
            f"Arquivos: {result.files_scanned:,} | válidos: {result.valid_files:,} | "
            f"OK: {result.matched_files:,} | ausentes: {result.missing_disks:,} | "
            f"ambíguos: {result.ambiguous_disks:,} | inválidos: {result.invalid_files:,} | "
            f"órfãos: {result.orphan_files:,}"
        )
        self.chd_table.setRowCount(len(result.records))
        for row_index, record in enumerate(result.records):
            values = (
                record.status, record.machine_name or "—", record.disk_name or "—",
                record.path or "—", record.actual_sha1 or record.expected_sha1 or "—",
                record.version if record.version is not None else "—", record.message,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, record.path)
                if column == 0:
                    status_map = {
                        "OK": RomStatus.OK, "MISSING": RomStatus.MISSING,
                        "AMBIGUOUS": RomStatus.REPAIRABLE, "INVALID": RomStatus.INVALID,
                        "ORPHAN": RomStatus.INCOMPLETE,
                    }
                    _set_status_visual(item, status_map.get(str(value).upper(), RomStatus.UNKNOWN))
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
        values = (
            ("Versão", header.version), ("Tamanho lógico", f"{header.logical_bytes:,} bytes"),
            ("Hunk", f"{header.hunk_bytes:,} bytes"), ("Raw SHA1", header.raw_sha1 or "—"),
            ("SHA1 do CHD", header.sha1 or "—"), ("MD5", header.md5 or "—"),
            ("Parent SHA1", header.parent_sha1 or "—"), ("Tamanho do arquivo", f"{header.file_size:,} bytes"),
        )
        for label, value in values:
            self.chd_result.addItem(QListWidgetItem(f"{label}: {value}"))


__all__ = ["ArcadeStudioPage"]
