"""GUI principal para os scanners de ROM do SERM V2."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QProgressBar, QPushButton, QTabWidget, QTreeWidget, QVBoxLayout, QWidget,
)

from ..runtime.paths import data_root


class RomScanPage(QWidget):
    """Superfície dedicada ao scan MAME e aos demais scans."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("SERM V2 — Scan de ROMs")
        title.setProperty("role", "title")
        layout.addWidget(title)
        description = QLabel(
            "Scanner físico baseado em catálogo canônico. MAME é a primeira "
            "implementação; No-Intro, Redump, WHLoader e C64 compartilham o motor."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._mame_tab(), "MAME")
        self.tabs.addTab(self._other_tab(), "Outros Scans")
        layout.addWidget(self.tabs, 1)

    @staticmethod
    def _directory_row(edit: QLineEdit, parent: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(edit, 1)
        button = QPushButton("Selecionar pasta")
        button.setProperty("role", "folder")
        button.clicked.connect(lambda: RomScanPage._choose_directory(edit, parent))
        row.addWidget(button)
        return row

    @staticmethod
    def _choose_directory(edit: QLineEdit, parent: QWidget) -> None:
        selected = QFileDialog.getExistingDirectory(parent, "Selecionar diretório", edit.text() or str(Path.home()))
        if selected:
            edit.setText(str(Path(selected).resolve()))

    @staticmethod
    def _result_tree() -> QTreeWidget:
        tree = QTreeWidget()
        tree.setHeaderLabels(["Estado", "Sistema / Set", "Arquivo", "Detalhe"])
        tree.setAlternatingRowColors(True)
        return tree

    def _mame_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        paths = QGroupBox("Fontes do scan")
        paths_layout = QVBoxLayout(paths)
        self.mame_rom_path = QLineEdit()
        self.mame_rom_path.setPlaceholderText("Diretório raiz das ROMs MAME")
        paths_layout.addWidget(QLabel("ROM path:"))
        paths_layout.addLayout(self._directory_row(self.mame_rom_path, page))
        self.mame_executable = QLineEdit()
        self.mame_executable.setReadOnly(True)
        self.mame_executable.setPlaceholderText("mame.exe configurado em Diretórios")
        paths_layout.addWidget(QLabel("Catálogo:"))
        paths_layout.addWidget(self.mame_executable)
        layout.addWidget(paths)

        options = QGroupBox("Política do scan MAME")
        row = QHBoxLayout(options)
        self.mame_recursive = QCheckBox("Scan recursivo")
        self.mame_recursive.setChecked(True)
        self.mame_archives = QCheckBox("Inspecionar ZIP sem extração")
        self.mame_archives.setChecked(True)
        self.mame_hash_crc = QCheckBox("CRC32")
        self.mame_hash_crc.setChecked(True)
        self.mame_hash_sha1 = QCheckBox("SHA-1")
        self.mame_hash_sha1.setChecked(True)
        self.mame_include_chd = QCheckBox("CHD / disks")
        self.mame_include_chd.setChecked(True)
        for widget in (self.mame_recursive, self.mame_archives, self.mame_hash_crc, self.mame_hash_sha1, self.mame_include_chd):
            row.addWidget(widget)
        row.addStretch()
        layout.addWidget(options)

        actions = QHBoxLayout()
        self.mame_scan_button = QPushButton("INICIAR SCAN MAME")
        self.mame_scan_button.setProperty("role", "primary")
        self.mame_scan_button.clicked.connect(lambda: self._not_ready("MAME"))
        self.mame_cancel_button = QPushButton("CANCELAR")
        self.mame_cancel_button.setEnabled(False)
        self.mame_reuse_button = QPushButton("REUTILIZAR ÚLTIMO SCAN")
        self.mame_reuse_button.clicked.connect(self._reuse_last_scan)
        actions.addWidget(self.mame_scan_button)
        actions.addWidget(self.mame_cancel_button)
        actions.addWidget(self.mame_reuse_button)
        actions.addStretch()
        layout.addLayout(actions)
        self.mame_progress = QProgressBar()
        layout.addWidget(self.mame_progress)
        self.mame_summary = QLabel("Nenhum scan executado nesta sessão.")
        layout.addWidget(self.mame_summary)
        layout.addWidget(self._result_tree(), 1)
        return page

    def _other_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        sources = QGroupBox("Scans disponíveis")
        source_layout = QVBoxLayout(sources)
        self.other_checks: dict[str, QCheckBox] = {}
        descriptions = {
            "No-Intro": "ROMs em ZIP; catálogo No-Intro.",
            "Redump": "CHD prioritário; CUE/BIN com conversão opcional.",
            "WHLoader": "Pacotes WHDLoad em .lha.",
            "C64": "Jogos C64 em ZIP conforme TOSEC.",
        }
        for name, description in descriptions.items():
            check = QCheckBox(f"{name} — {description}")
            self.other_checks[name] = check
            source_layout.addWidget(check)
        layout.addWidget(sources)

        redump = QGroupBox("Redump — mídia óptica")
        redump_layout = QVBoxLayout(redump)
        self.redump_chd_path = QLineEdit()
        self.redump_chd_path.setPlaceholderText("Diretório com CHDs")
        redump_layout.addLayout(self._directory_row(self.redump_chd_path, page))
        self.redump_cue_path = QLineEdit()
        self.redump_cue_path.setPlaceholderText("Diretório com CUE/BIN")
        redump_layout.addLayout(self._directory_row(self.redump_cue_path, page))
        self.redump_convert_chd = QCheckBox("Converter CUE/BIN para CHD via chdman.exe do diretório exe do MAME")
        self.redump_convert_chd.setChecked(True)
        redump_layout.addWidget(self.redump_convert_chd)
        self.redump_keep_source = QCheckBox("Manter CUE/BIN original após conversão")
        self.redump_keep_source.setChecked(True)
        redump_layout.addWidget(self.redump_keep_source)
        layout.addWidget(redump)

        actions = QHBoxLayout()
        self.other_scan_button = QPushButton("INICIAR SCANS SELECIONADOS")
        self.other_scan_button.setProperty("role", "primary")
        self.other_scan_button.clicked.connect(lambda: self._not_ready("fontes externas"))
        self.other_cancel_button = QPushButton("CANCELAR")
        self.other_cancel_button.setEnabled(False)
        actions.addWidget(self.other_scan_button)
        actions.addWidget(self.other_cancel_button)
        actions.addStretch()
        layout.addLayout(actions)
        self.other_progress = QProgressBar()
        layout.addWidget(self.other_progress)
        self.other_summary = QLabel("Selecione as fontes que participarão do scan.")
        layout.addWidget(self.other_summary)
        layout.addWidget(self._result_tree(), 1)
        return page

    def _not_ready(self, target: str) -> None:
        self.mame_summary.setText(
            f"Superfície preparada para {target}. O motor V2 será conectado após a adaptação dos algoritmos funcionais da V1."
        )

    def _reuse_last_scan(self) -> None:
        manifest = data_root() / "scans" / "current_scan.jsonl"
        self.mame_summary.setText(
            f"Manifesto disponível: {manifest}" if manifest.is_file() else f"Nenhum manifesto encontrado: {manifest}"
        )

    def refresh(self) -> None:
        try:
            raw = (data_root() / "emulator_paths.json").read_text(encoding="utf-8")
            paths = json.loads(raw)
        except (OSError, ValueError, TypeError):
            paths = {}
        executable = paths.get("mame_executable") if isinstance(paths, dict) else None
        self.mame_executable.setText(str(executable) if executable else "")
        manifest = data_root() / "scans" / "current_scan.jsonl"
        if manifest.is_file():
            self.mame_summary.setText(f"Último manifesto disponível: {manifest}")


__all__ = ["RomScanPage"]
