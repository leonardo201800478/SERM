"""Interface operacional do Arcade Studio V2.

A página centraliza catálogo, auditoria física de CHDs e preparação da
reconstrução sem depender de RomVault ou de outro backend externo.
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
    QLineEdit,
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
from ..runtime.paths import database_path
from ..services.arcade.chd_audit import ArcadeChdAuditService, ChdAuditResult
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
    """Cria um ícone vetorial simples e consistente sem assets externos."""
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
    """Aplica ícone, texto auxiliar e cor conforme o estado da reconstrução."""
    icon = _status_icon(status)
    if isinstance(item, QTreeWidgetItem):
        item.setIcon(0, icon)
    else:
        item.setIcon(icon)
    item.setForeground(QColor("#e8edf2"))
    item.setBackground(_STATUS_COLORS[status].darker(420))
    item.setToolTip(_STATUS_LABELS[status])


class ArcadeStudioPage(QWidget):
    """Painel operacional do Arcade Studio."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._database = database_path()
        self._last_chd_audit: ChdAuditResult | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("ARCADE STUDIO")
        title.setProperty("role", "title")
        layout.addWidget(title)
        intro = QLabel(
            "Catálogo MAME → auditoria → reconstrução. V2 usa a identidade lógica "
            "do conteúdo e executa a reconstrução dentro do SERM."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._catalog_tab(), "Catálogo")
        self.tabs.addTab(self._chd_tab(), "Auditoria CHD")
        self.tabs.addTab(self._reconstruction_tab(), "Reconstrução")
        layout.addWidget(self.tabs, 1)

    def _catalog_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        controls = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Pesquisar machine, descrição ou fabricante…")
        self.search.returnPressed.connect(self.refresh)
        controls.addWidget(self.search, 1)
        button = QPushButton("ATUALIZAR")
        button.clicked.connect(self.refresh)
        controls.addWidget(button)
        layout.addLayout(controls)
        self.catalog_status = QLabel("Nenhum catálogo carregado.")
        layout.addWidget(self.catalog_status)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.catalog_table = QTableWidget(0, 7)
        self.catalog_table.setHorizontalHeaderLabels(
            ["Status", "Machine", "Descrição", "Ano", "Fabricante", "Parent", "ROMs / CHDs"]
        )
        self.catalog_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.catalog_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.catalog_table.setAlternatingRowColors(True)
        self.catalog_table.setSortingEnabled(True)
        self.catalog_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.catalog_table.horizontalHeader().setStretchLastSection(True)
        self.catalog_table.itemSelectionChanged.connect(self._show_machine)
        splitter.addWidget(self.catalog_table)

        tree_box = QGroupBox("Árvore de ROMs / CHDs — status da reconstrução")
        tree_layout = QVBoxLayout(tree_box)
        self.rom_tree = QTreeWidget()
        self.rom_tree.setHeaderLabels(["Componente", "Status", "Origem / Hash", "Detalhes"])
        self.rom_tree.setAlternatingRowColors(True)
        self.rom_tree.setRootIsDecorated(True)
        self.rom_tree.header().setStretchLastSection(True)
        tree_layout.addWidget(self.rom_tree)
        splitter.addWidget(tree_box)
        splitter.setSizes([430, 300])
        layout.addWidget(splitter, 1)

        self.catalog_details = QLabel("Selecione uma machine para visualizar os componentes.")
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
        self.chd_table.setHorizontalHeaderLabels(
            ["Status", "Machine", "Disco", "Arquivo", "Raw SHA1", "Versão", "Detalhes"]
        )
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
        self.reconstruction_machine.setPlaceholderText("machine (ex.: sf2, outrun, etc.)")
        self.reconstruction_disk = QLineEdit()
        self.reconstruction_disk.setPlaceholderText("nome do disco/CHD")
        form = QFormLayout()
        form.addRow("Machine:", self.reconstruction_machine)
        form.addRow("Disco:", self.reconstruction_disk)
        layout.addLayout(form)
        self.reconstruction_result = QLabel("Selecione uma machine no catálogo para preparar o plano.")
        self.reconstruction_result.setWordWrap(True)
        layout.addWidget(self.reconstruction_result)
        layout.addStretch()
        return page

    @staticmethod
    def _catalog_status() -> RomStatus:
        """Sem inventário físico, o catálogo não afirma que uma ROM existe."""
        return RomStatus.UNKNOWN

    def refresh(self) -> None:
        """Atualiza o catálogo da última importação MAME concluída."""
        try:
            with sqlite3.connect(self._database) as db:
                db.row_factory = sqlite3.Row
                import_row = db.execute(
                    "SELECT id,mame_build,machine_count FROM mame_listxml_import "
                    "WHERE status='completed' ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if import_row is None:
                    self.catalog_status.setText("Nenhuma importação MAME concluída.")
                    self.catalog_table.setRowCount(0)
                    self.rom_tree.clear()
                    return
                import_id = int(import_row["id"])
                text = self.search.text().strip()
                pattern = f"%{text}%" if text else "%"
                rows = db.execute(
                    """SELECT m.id,m.name,m.description,m.year,m.manufacturer,m.cloneof,
                              (SELECT COUNT(*) FROM mame_rom r WHERE r.machine_id=m.id) AS rom_count,
                              (SELECT COUNT(*) FROM mame_disk d WHERE d.machine_id=m.id) AS disk_count
                       FROM mame_machine m
                       WHERE m.import_id=?
                         AND (m.name LIKE ? OR m.description LIKE ? OR m.manufacturer LIKE ?)
                       ORDER BY m.name LIMIT 1000""",
                    (import_id, pattern, pattern, pattern),
                ).fetchall()
                self.catalog_status.setText(
                    f"Importação {import_id} | MAME {import_row['mame_build'] or '—'} | "
                    f"{import_row['machine_count']:,} machines | exibindo {len(rows):,} | "
                    "status físico: não auditado"
                )
                self.catalog_table.setSortingEnabled(False)
                self.catalog_table.setRowCount(len(rows))
                status = self._catalog_status()
                for index, row in enumerate(rows):
                    status_item = QTableWidgetItem(_STATUS_LABELS[status])
                    _set_status_visual(status_item, status)
                    self.catalog_table.setItem(index, 0, status_item)
                    values = (
                        row["name"], row["description"], row["year"],
                        row["manufacturer"], row["cloneof"],
                        f"{row['rom_count']:,} / {row['disk_count']:,}",
                    )
                    for column, value in enumerate(values, start=1):
                        item = QTableWidgetItem("" if value is None else str(value))
                        item.setData(Qt.ItemDataRole.UserRole, int(row["id"]))
                        self.catalog_table.setItem(index, column, item)
                self.catalog_table.setSortingEnabled(True)
                self.catalog_table.resizeColumnsToContents()
        except sqlite3.Error as exc:
            self.catalog_status.setText(f"Erro ao consultar catálogo: {exc}")

    def _show_machine(self) -> None:
        rows = self.catalog_table.selectionModel().selectedRows()
        if not rows:
            return
        machine_id = self.catalog_table.item(rows[0].row(), 1).data(Qt.ItemDataRole.UserRole)
        try:
            with sqlite3.connect(self._database) as db:
                db.row_factory = sqlite3.Row
                machine = db.execute(
                    "SELECT name,description,cloneof,romof FROM mame_machine WHERE id=?",
                    (machine_id,),
                ).fetchone()
                if machine is None:
                    return
                roms = db.execute(
                    "SELECT name,size,crc,sha1,merge FROM mame_rom WHERE machine_id=? ORDER BY name",
                    (machine_id,),
                ).fetchall()
                disks = db.execute(
                    "SELECT name,sha1,md5,merge FROM mame_disk WHERE machine_id=? ORDER BY name",
                    (machine_id,),
                ).fetchall()
            self.reconstruction_machine.setText(str(machine["name"]))
            status = self._catalog_status()
            self.catalog_details.setText(
                f"{machine['name']} | parent={machine['cloneof'] or '—'} | romof={machine['romof'] or '—'} | "
                f"ROMs={len(roms):,} | CHDs={len(disks):,} | reconstrução={_STATUS_LABELS[status]}"
            )
            self._populate_rom_tree(machine, roms, disks)
            if disks:
                self.reconstruction_disk.setText(str(disks[0]["name"]))
                self.reconstruction_result.setText(
                    "CHDs catalogados: " + ", ".join(
                        f"{disk['name']} [SHA1={disk['sha1'] or '—'}]" for disk in disks
                    )
                )
            else:
                self.reconstruction_disk.clear()
                self.reconstruction_result.setText("A machine selecionada não possui CHD catalogado.")
        except sqlite3.Error as exc:
            self.catalog_details.setText(f"Erro: {exc}")

    def _populate_rom_tree(self, machine: sqlite3.Row, roms: list[sqlite3.Row], disks: list[sqlite3.Row]) -> None:
        self.rom_tree.clear()
        status = self._catalog_status()
        root = QTreeWidgetItem([str(machine["name"]), _STATUS_LABELS[status], "machine", str(machine["description"] or "")])
        _set_status_visual(root, status)
        root.setExpanded(True)
        self.rom_tree.addTopLevelItem(root)

        rom_group = QTreeWidgetItem([f"ROMs ({len(roms):,})", _STATUS_LABELS[status], "catálogo MAME", ""])
        _set_status_visual(rom_group, status)
        rom_group.setExpanded(True)
        root.addChild(rom_group)
        for rom in roms:
            item = QTreeWidgetItem([
                str(rom["name"]), _STATUS_LABELS[status],
                str(rom["sha1"] or rom["crc"] or "—"),
                f"{rom['size'] or 0:,} bytes | merge={rom['merge'] or '—'}",
            ])
            _set_status_visual(item, status)
            rom_group.addChild(item)

        disk_group = QTreeWidgetItem([f"CHDs ({len(disks):,})", _STATUS_LABELS[status], "catálogo MAME", ""])
        _set_status_visual(disk_group, status)
        disk_group.setExpanded(True)
        root.addChild(disk_group)
        for disk in disks:
            item = QTreeWidgetItem([
                str(disk["name"]), _STATUS_LABELS[status],
                str(disk["sha1"] or "—"),
                f"MD5={disk['md5'] or '—'} | merge={disk['merge'] or '—'}",
            ])
            _set_status_visual(item, status)
            disk_group.addChild(item)

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
                        "OK": RomStatus.OK,
                        "MISSING": RomStatus.MISSING,
                        "AMBIGUOUS": RomStatus.REPAIRABLE,
                        "INVALID": RomStatus.INVALID,
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
        self.chd_progress.setRange(0, 1)
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
        self.chd_progress.setValue(1)


__all__ = ["ArcadeStudioPage"]
