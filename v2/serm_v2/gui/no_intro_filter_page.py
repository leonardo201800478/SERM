"""Tela dedicada aos filtros No-Intro e à seleção 1G1R."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ..runtime.paths import data_root, database_path
from ..services.no_intro_filter_service import DEFAULT_REGION_PRIORITY, NoIntroFilterService
from ..services.scan_file_repository import ScanFileRepository


class NoIntroFilterPage(QWidget):
    """Configura conteúdo, clones, regiões, 1G1R e variantes externas."""

    SETTINGS_PATH = data_root() / "no_intro_filter.json"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("NO-INTRO — FILTROS E 1G1R")
        title.setProperty("role", "title")
        layout.addWidget(title)
        intro = QLabel("O scan bruto coleta todos os metadados. Esta tela decide o que entra no set final; o snapshot original nunca é alterado.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        scan_box = QGroupBox("1. Scan No-Intro concluído")
        sv = QVBoxLayout(scan_box)
        self.scan_combo = QComboBox()
        self.scan_combo.currentIndexChanged.connect(self._changed)
        sv.addWidget(self.scan_combo)
        self.scan_info = QLabel("Nenhum scan selecionado.")
        self.scan_info.setWordWrap(True)
        sv.addWidget(self.scan_info)
        layout.addWidget(scan_box)

        content_box = QGroupBox("2. Conteúdo")
        cv = QVBoxLayout(content_box)
        self.checks: dict[str, QCheckBox] = {}
        options = (
            ("include_bios", "BIOS"), ("include_programs", "Programs"),
            ("include_betas", "Betas"), ("include_prototypes", "Prototypes"),
            ("include_demos", "Demos"), ("include_np", "NP / Nintendo Power"),
            ("include_samples", "Samples"), ("include_aftermarket", "Aftermarket"),
            ("include_unlicensed", "Unlicensed"), ("include_clones", "Clones"),
        )
        for key, label in options:
            box = QCheckBox(label)
            box.stateChanged.connect(self._preview)
            box.setChecked(False if key != "include_clones" else True)
            self.checks[key] = box
            cv.addWidget(box)
        self.include_translations = QCheckBox("Traduções / Translated")
        self.include_hacks = QCheckBox("Hacks / ROM hacks")
        self.keep_unverified = QCheckBox("Manter variantes sem hash como UNVERIFIED_VARIANT")
        self.include_translations.stateChanged.connect(self._preview)
        self.include_hacks.stateChanged.connect(self._preview)
        self.keep_unverified.stateChanged.connect(self._preview)
        self.keep_unverified.setChecked(True)
        for box in (self.include_translations, self.include_hacks, self.keep_unverified): cv.addWidget(box)
        layout.addWidget(content_box)

        region_box = QGroupBox("3. Regiões e 1G1R")
        rv = QVBoxLayout(region_box)
        self.one_g1r = QCheckBox("Gerar 1G1R — somente uma variante por família de jogo")
        self.one_g1r.setChecked(True)
        self.one_g1r.stateChanged.connect(self._preview)
        rv.addWidget(self.one_g1r)
        rv.addWidget(QLabel("Prioridade regional (arraste para alterar):"))
        self.region_list = QListWidget()
        self.region_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.region_list.setMaximumHeight(180)
        self.region_list.model().rowsMoved.connect(self._preview)
        rv.addWidget(self.region_list)
        reset = QPushButton("RESTAURAR ORDEM PADRÃO")
        reset.clicked.connect(self._reset_regions)
        rv.addWidget(reset)
        layout.addWidget(region_box)

        self.preview = QLabel("Selecione um scan.")
        self.preview.setWordWrap(True)
        layout.addWidget(self.preview)
        actions = QHBoxLayout()
        self.save = QPushButton("SALVAR CONFIGURAÇÃO")
        self.apply = QPushButton("APLICAR FILTROS E GERAR ARQUIVO")
        self.save.clicked.connect(self._save_settings)
        self.apply.clicked.connect(self._apply)
        actions.addWidget(self.save); actions.addWidget(self.apply); actions.addStretch()
        layout.addLayout(actions)
        self.result = QLabel("Nenhum arquivo filtrado gerado.")
        self.result.setWordWrap(True)
        layout.addWidget(self.result)
        layout.addStretch()

    def refresh(self) -> None:
        self._refresh_scans()
        self._load_settings()
        self._preview()

    def _refresh_scans(self) -> None:
        self.scan_combo.blockSignals(True); self.scan_combo.clear()
        try:
            with sqlite3.connect(database_path()) as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute("SELECT * FROM scan_runs WHERE status='completed' AND lower(source)='no-intro' ORDER BY started_at DESC").fetchall()
        except sqlite3.Error:
            rows = []
        for row in rows:
            data = dict(row)
            self.scan_combo.addItem(f"{data.get('system','No-Intro')} › {data.get('catalog_label','catalog')} | {data.get('scan_id','')}", data)
        self.scan_combo.blockSignals(False)
        self._changed()

    def _changed(self, *_args) -> None:
        data = self.scan_combo.currentData()
        if not isinstance(data, dict):
            self.scan_info.setText("Nenhum scan No-Intro concluído.")
            self.apply.setEnabled(False); return
        path = Path(str(data.get("scan_file_path") or ""))
        self.apply.setEnabled(path.is_file())
        self.scan_info.setText(f"Entrada: {path}\nItens={int(data.get('items_examined') or 0):,} | {data.get('status_counts_json','{}')}")

    def _config(self):
        priority = [self.region_list.item(i).text() for i in range(self.region_list.count())]
        values = {key: box.isChecked() for key, box in self.checks.items()}
        return SimpleNamespace(profile_id="no-intro-filter", region_priority=priority, one_game_one_region=self.one_g1r.isChecked(), include_translations=self.include_translations.isChecked(), include_hacks=self.include_hacks.isChecked(), keep_unverified_variants=self.keep_unverified.isChecked(), remove_previous_versions=True, **values)

    def _preview(self, *_args) -> None:
        data = self.scan_combo.currentData()
        if not isinstance(data, dict): return
        path = Path(str(data.get("scan_file_path") or ""))
        if not path.is_file(): return
        try:
            result = NoIntroFilterService.preview(path, self._config())
            self.preview.setText(f"Preview: entrada={result['input_count']:,} | saída={result['output_count']:,} | excluídas={result['filtered_count']:,}\n" + " | ".join(f"{k}={v:,}" for k,v in result['filter_counts'].items()))
        except Exception as exc:
            self.preview.setText(f"Preview indisponível: {exc}")

    def _apply(self) -> None:
        data = self.scan_combo.currentData()
        if not isinstance(data, dict): return
        path = Path(str(data.get("scan_file_path") or ""))
        try:
            result = NoIntroFilterService.apply(path, self._config())
            self.result.setText(f"ARQUIVO FILTRADO GERADO\n{result['filtered_file_path']}\nentrada={result['input_count']:,} | saída={result['output_count']:,}")
        except Exception as exc:
            QMessageBox.critical(self, "No-Intro", f"Falha ao gerar filtro:\n{exc}")

    def _save_settings(self) -> None:
        config = self._config()
        payload = {key: getattr(config, key) for key in vars(config)}
        self.SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.SETTINGS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self.result.setText("Configuração No-Intro salva.")

    def _load_settings(self) -> None:
        priority = list(DEFAULT_REGION_PRIORITY)
        try:
            raw = json.loads(self.SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("region_priority"), list): priority = [str(x) for x in raw["region_priority"]]
            for key, box in self.checks.items():
                if key in raw: box.setChecked(bool(raw[key]))
            if isinstance(raw, dict):
                self.one_g1r.setChecked(bool(raw.get("one_game_one_region", True)))
                self.include_translations.setChecked(bool(raw.get("include_translations", False)))
                self.include_hacks.setChecked(bool(raw.get("include_hacks", False)))
                self.keep_unverified.setChecked(bool(raw.get("keep_unverified_variants", True)))
        except (OSError, ValueError, TypeError):
            pass
        self.region_list.clear()
        for value in priority: self.region_list.addItem(QListWidgetItem(value))

    def _reset_regions(self) -> None:
        self.region_list.clear()
        for value in DEFAULT_REGION_PRIORITY: self.region_list.addItem(QListWidgetItem(value))
        self._preview()


__all__ = ["NoIntroFilterPage"]
