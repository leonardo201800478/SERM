"""Interface operacional do Arcade Studio V2.

A página centraliza catálogo, auditoria física de CHDs e preparação da
reconstrução sem depender de RomVault ou de outro backend externo.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import database_path
from ..services.arcade.chd_audit import ArcadeChdAuditService, ChdAuditResult
from ..services.chd_header import ChdFormatError, ChdHeaderReader


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
        self.catalog_table = QTableWidget(0, 6)
        self.catalog_table.setHorizontalHeaderLabels(
            ["Machine", "Descrição", "Ano", "Fabricante", "Parent", "ROMs / CHDs"]
        )
        self.catalog_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.catalog_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.catalog_table.horizontalHeader().setStretchLastSection(True)
        self.catalog_table.itemSelectionChanged.connect(self._show_machine)
        layout.addWidget(self.catalog_table, 1)

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
        self.reconstruction_result = QLabel(
            "Selecione uma machine no catálogo para preparar o plano."
        )
        self.reconstruction_result.setWordWrap(True)
        layout.addWidget(self.reconstruction_result)
        layout.addStretch()
        return page

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
                    f"{import_row['machine_count']:,} machines | exibindo {len(rows):,}"
                )
                self.catalog_table.setRowCount(len(rows))
                for index, row in enumerate(rows):
                    values = (
                        row["name"], row["description"], row["year"],
                        row["manufacturer"], row["cloneof"],
                        f"{row['rom_count']:,} / {row['disk_count']:,}",
                    )
                    for column, value in enumerate(values):
                        item = QTableWidgetItem("" if value is None else str(value))
                        item.setData(Qt.ItemDataRole.UserRole, int(row["id"]))
                        self.catalog_table.setItem(index, column, item)
                self.catalog_table.resizeColumnsToContents()
        except sqlite3.Error as exc:
            self.catalog_status.setText(f"Erro ao consultar catálogo: {exc}")

    def _show_machine(self) -> None:
        rows = self.catalog_table.selectionModel().selectedRows()
        if not rows:
            return
        machine_id = self.catalog_table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
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
            self.catalog_details.setText(
                f"{machine['name']} | parent={machine['cloneof'] or '—'} | romof={machine['romof'] or '—'} | "
                f"ROMs={len(roms):,} | CHDs={len(disks):,}"
            )
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
            result = ArcadeChdAuditService().audit(
                source=Path(source_text),
                database=self._database,
            )
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
                record.status,
                record.machine_name or "—",
                record.disk_name or "—",
                record.path or "—",
                record.actual_sha1 or record.expected_sha1 or "—",
                record.version if record.version is not None else "—",
                record.message,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, record.path)
                self.chd_table.setItem(row_index, column, item)
        self.chd_table.resizeColumnsToContents()
        self.chd_table.itemSelectionChanged.connect(self._show_chd_audit_selection)

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
            ("Versão", header.version),
            ("Tamanho lógico", f"{header.logical_bytes:,} bytes"),
            ("Hunk", f"{header.hunk_bytes:,} bytes"),
            ("Raw SHA1", header.raw_sha1 or "—"),
            ("SHA1 do CHD", header.sha1 or "—"),
            ("MD5", header.md5 or "—"),
            ("Parent SHA1", header.parent_sha1 or "—"),
            ("Tamanho do arquivo", f"{header.file_size:,} bytes"),
        )
        for label, value in values:
            self.chd_result.addItem(QListWidgetItem(f"{label}: {value}"))
        self.chd_progress.setValue(1)


__all__ = ["ArcadeStudioPage"]
