"""Tela de scan individual de arquivos Arcade."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models.arcade import RomStatus
from ..runtime.paths import database_path
from ..services.arcade.rom_archive_scan import RomArchiveFormatError, RomArchiveScanner
from ..services.chd_header import ChdFormatError, ChdHeaderReader


class ArcadeFileScanPage(QWidget):
    """Seleciona um arquivo Arcade e executa o scan imediatamente."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._database = database_path()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("ARCADE FILE SCAN")
        title.setProperty("role", "title")
        layout.addWidget(title)
        intro = QLabel(
            "Abra um arquivo individual e veja imediatamente a identidade física "
            "encontrada pelo SERM. O arquivo original nunca é alterado."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        controls = QHBoxLayout()
        self.machine = QLabel("Machine: —")
        controls.addWidget(self.machine, 1)
        button = QPushButton("ABRIR ARQUIVO PARA SCAN…")
        button.clicked.connect(self.open_file)
        controls.addWidget(button)
        layout.addLayout(controls)

        self.summary = QLabel("Nenhum arquivo selecionado.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Componente", "Status", "Origem física", "Hash", "Detalhes"]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir arquivo para scan",
            "",
            "Arquivos Arcade (*.zip *.chd);;ROM ZIP (*.zip);;CHD (*.chd)",
        )
        if not path:
            return
        selected = Path(path)
        if selected.suffix.casefold() == ".zip":
            self._scan_zip(selected)
        elif selected.suffix.casefold() == ".chd":
            self._scan_chd(selected)
        else:
            QMessageBox.warning(self, "Arquivo não suportado", "Selecione um ZIP ou CHD.")

    def _scan_zip(self, path: Path) -> None:
        try:
            result = RomArchiveScanner().scan(path)
        except (OSError, RomArchiveFormatError) as exc:
            QMessageBox.critical(self, "Falha no scan", str(exc))
            return

        with sqlite3.connect(self._database) as db:
            db.row_factory = sqlite3.Row
            machine = db.execute(
                "SELECT id,name,description,cloneof FROM mame_machine "
                "WHERE name=? ORDER BY id DESC LIMIT 1",
                (path.stem,),
            ).fetchone()

        if machine is None:
            self.machine.setText("Machine: não identificada")
            self.summary.setText(
                f"Arquivo: {path} | {result.entries_scanned:,} entradas | "
                "selecione a machine correspondente no Arcade Studio para o confronto com o catálogo."
            )
            self._show_inventory(result.inventory)
            return

        self.machine.setText(f"Machine: {machine['name']}")
        with sqlite3.connect(self._database) as db:
            db.row_factory = sqlite3.Row
            roms = db.execute(
                "SELECT name,size,crc,sha1 FROM mame_rom WHERE machine_id=? ORDER BY name",
                (machine["id"],),
            ).fetchall()

        rows = self._match(roms, result.inventory)
        self.table.setRowCount(len(rows))
        ok = missing = ambiguous = 0
        for index, row in enumerate(rows):
            for column, value in enumerate(row):
                self.table.setItem(index, column, QTableWidgetItem(str(value)))
            status = row[1]
            if status == RomStatus.OK:
                ok += 1
            elif status == RomStatus.MISSING:
                missing += 1
            elif status == RomStatus.REPAIRABLE:
                ambiguous += 1

        self.summary.setText(
            f"Arquivo: {path} | entradas={result.entries_scanned:,} | "
            f"catalogadas={len(roms):,} | OK={ok:,} | ausentes={missing:,} | ambíguas={ambiguous:,}"
        )

    @staticmethod
    def _match(roms, inventory) -> list[tuple[str, str, str, str, str]]:
        by_sha1: dict[str, list] = {}
        by_md5: dict[str, list] = {}
        by_crc_size: dict[tuple[str, int], list] = {}
        for item in inventory:
            if item.sha1:
                by_sha1.setdefault(item.sha1.casefold(), []).append(item)
            if item.md5:
                by_md5.setdefault(item.md5.casefold(), []).append(item)
            if item.crc:
                by_crc_size.setdefault((item.crc.casefold(), item.size), []).append(item)

        rows = []
        for rom in roms:
            candidates = []
            method = "—"
            if rom["sha1"]:
                candidates = by_sha1.get(str(rom["sha1"]).casefold(), [])
                method = "SHA1"
            if not candidates and rom["md5"]:
                candidates = by_md5.get(str(rom["md5"]).casefold(), [])
                method = "MD5"
            if not candidates and rom["crc"] and rom["size"] is not None:
                candidates = by_crc_size.get(
                    (str(rom["crc"]).casefold(), int(rom["size"])), []
                )
                method = "CRC + tamanho"

            if len(candidates) == 1:
                physical = candidates[0]
                rows.append(
                    (rom["name"], RomStatus.OK, physical.path, physical.sha1 or "—", method)
                )
            elif len(candidates) > 1:
                rows.append(
                    (
                        rom["name"],
                        RomStatus.REPAIRABLE,
                        f"{len(candidates)} candidatos",
                        "—",
                        method,
                    )
                )
            else:
                rows.append(
                    (rom["name"], RomStatus.MISSING, "—", "—", "nenhuma identidade encontrada")
                )
        return rows

    def _show_inventory(self, inventory) -> None:
        self.table.setRowCount(len(inventory))
        for index, item in enumerate(inventory):
            values = (
                Path(item.path.split("!", 1)[-1]).name,
                RomStatus.UNKNOWN,
                item.path,
                item.sha1 or "—",
                f"{item.size:,} bytes | CRC={item.crc}",
            )
            for column, value in enumerate(values):
                self.table.setItem(index, column, QTableWidgetItem(str(value)))

    def _scan_chd(self, path: Path) -> None:
        try:
            header = ChdHeaderReader().read(path)
        except (OSError, ChdFormatError) as exc:
            QMessageBox.critical(self, "Falha no scan", str(exc))
            return
        self.machine.setText("Machine: identificação pelo catálogo CHD disponível na Auditoria CHD")
        self.summary.setText(
            f"CHD: {path} | versão={header.version} | raw SHA1={header.raw_sha1 or '—'} | "
            f"parent SHA1={header.parent_sha1 or '—'}"
        )
        values = [
            ("CHD", RomStatus.OK, str(path), header.raw_sha1 or "—", f"{header.file_size:,} bytes"),
            ("Logical size", RomStatus.OK, str(path), header.sha1 or "—", f"{header.logical_bytes:,} bytes"),
            ("MD5", RomStatus.OK, str(path), header.md5 or "—", "identidade do conteúdo"),
        ]
        self.table.setRowCount(len(values))
        for row_index, row in enumerate(values):
            for column, value in enumerate(row):
                self.table.setItem(row_index, column, QTableWidgetItem(str(value)))


__all__ = ["ArcadeFileScanPage"]
