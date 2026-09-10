"""Fase 2: filtragem de snapshots para fontes não-Arcade."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import database_path, scans_root
from ..services.scan_repository import ScanRepository


NO_SCAN_SELECTED_TEXT = "Nenhum scan selecionado."


class _GenericFilterTab(QWidget):
    """Filtro genérico seguro para fontes sem regras específicas de classificação."""

    def __init__(self, source: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.source = source
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel(f"{self.source} — FILTRAGEM")
        title.setProperty("role", "title")
        layout.addWidget(title)

        description = QLabel(
            "Esta guia trabalha somente sobre o snapshot do scan selecionado. "
            "Não revarre o diretório e não altera o scan bruto."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        box = QGroupBox("1. Scan completo de entrada")
        form = QVBoxLayout(box)
        self.scan_combo = QComboBox()
        self.scan_combo.currentIndexChanged.connect(self._changed)
        form.addWidget(self.scan_combo)
        self.info = QLabel(NO_SCAN_SELECTED_TEXT)
        self.info.setWordWrap(True)
        form.addWidget(self.info)
        layout.addWidget(box)

        rules = QGroupBox("2. Regras disponíveis")
        rules_layout = QVBoxLayout(rules)
        self.current_only = QCheckBox("Manter somente itens CURRENT")
        self.current_only.setChecked(True)
        self.keep_duplicates = QCheckBox("Manter ocorrências DUPLICATE")
        self.keep_duplicates.setChecked(False)
        rules_layout.addWidget(self.current_only)
        rules_layout.addWidget(self.keep_duplicates)
        self.current_only.toggled.connect(self._preview)
        self.keep_duplicates.toggled.connect(self._preview)
        layout.addWidget(rules)

        self.preview = QLabel("Selecione um scan para visualizar o resultado.")
        self.preview.setWordWrap(True)
        layout.addWidget(self.preview)

        self.apply_button = QPushButton("GERAR ARQUIVO FILTRADO")
        self.apply_button.clicked.connect(self.apply)
        layout.addWidget(self.apply_button)

        self.result = QLabel("Nenhum arquivo filtrado gerado nesta sessão.")
        self.result.setWordWrap(True)
        layout.addWidget(self.result)
        layout.addStretch()

    def refresh(self) -> None:
        self.scan_combo.blockSignals(True)
        self.scan_combo.clear()
        try:
            with sqlite3.connect(database_path()) as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(
                    "SELECT * FROM scan_runs "
                    "WHERE status='completed' AND lower(source)=lower(?) "
                    "ORDER BY started_at DESC",
                    (self.source,),
                ).fetchall()
        except sqlite3.Error:
            rows = []

        for row in rows:
            data = dict(row)
            self.scan_combo.addItem(
                f"{data.get('system') or self.source} › "
                f"{data.get('catalog_label') or 'catálogo'} | {data.get('scan_id')}",
                data,
            )
        self.scan_combo.blockSignals(False)
        self._changed()

    @staticmethod
    def _counts(data: dict) -> dict[str, int]:
        try:
            raw = json.loads(data.get("status_counts_json") or "{}")
            return {str(key): int(value) for key, value in raw.items()}
        except (TypeError, ValueError, AttributeError):
            return {}

    def _changed(self, *_args) -> None:
        data = self.scan_combo.currentData()
        if not isinstance(data, dict):
            self.info.setText("Nenhum scan concluído para esta fonte.")
            self.apply_button.setEnabled(False)
            self.preview.setText("Selecione um scan para visualizar o resultado.")
            return

        counts = self._counts(data)
        self.info.setText(
            f"Entrada: {data.get('scan_file_path') or '—'}\n"
            f"Itens={int(data.get('items_examined') or 0):,} | "
            f"CURRENT={counts.get('CURRENT', 0):,} | "
            f"MISSING={counts.get('MISSING', 0):,} | "
            f"WRONG={counts.get('WRONG', 0):,}"
        )
        self.apply_button.setEnabled(Path(str(data.get("scan_file_path") or "")).is_file())
        self._preview()

    def _keep(self, evidence: dict) -> bool:
        status = str(evidence.get("status") or "").upper()
        if status == "CURRENT":
            return True
        return status == "DUPLICATE" and self.keep_duplicates.isChecked()

    def _preview(self, *_args) -> None:
        data = self.scan_combo.currentData()
        if not isinstance(data, dict):
            return
        path = Path(str(data.get("scan_file_path") or ""))
        if not path.is_file():
            self.preview.setText("Arquivo de scan não localizado.")
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            evidence = payload.get("evidence", [])
            selected = [item for item in evidence if self._keep(item)]
            self.preview.setText(
                f"Preview: entrada={len(evidence):,} | "
                f"saída={len(selected):,} | "
                f"excluídas={len(evidence) - len(selected):,}"
            )
        except (OSError, ValueError, TypeError) as exc:
            self.preview.setText(f"Preview indisponível: {exc}")

    def apply(self) -> None:
        data = self.scan_combo.currentData()
        if not isinstance(data, dict):
            return
        source_path = Path(str(data.get("scan_file_path") or ""))
        if not source_path.is_file():
            QMessageBox.warning(self, "Filtragem", "O arquivo do scan não existe mais.")
            return
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8"))
            evidence = [item for item in payload.get("evidence", []) if self._keep(item)]
            source_count = len(payload.get("evidence", []))
            run_id = uuid4().hex[:16]
            out_dir = scans_root() / "filtered" / self.source.casefold().replace("-", "_")
            out_dir.mkdir(parents=True, exist_ok=True)
            label = str(payload.get("catalog_label") or "catalog").replace("/", "_").replace("\\", "_")
            out = out_dir / (
                f"{self.source}_{label}_{payload.get('scan_type', 'full')}_FILTER_{run_id}.json"
            )
            result = {
                "format": "SERM-FILTER-V2",
                "schema_version": 2,
                "filter_run_id": run_id,
                "scan_id": payload.get("scan_id"),
                "profile_id": f"generic-{self.source.casefold()}",
                "source": payload.get("source"),
                "system": payload.get("system"),
                "scan_type": payload.get("scan_type", "full"),
                "catalog_label": payload.get("catalog_label"),
                "catalog_hash": payload.get("catalog_hash"),
                "source_scan_file": str(source_path.resolve()),
                "created_at": datetime.now(UTC).isoformat(),
                "input_count": source_count,
                "output_count": len(evidence),
                "filtered_count": source_count - len(evidence),
                "filters": {
                    "current_only": self.current_only.isChecked(),
                    "keep_duplicates": self.keep_duplicates.isChecked(),
                },
                "evidence": evidence,
            }
            out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            result["filtered_file_path"] = str(out)
            ScanRepository(database_path()).save_filter_result(result)
            self.result.setText(
                f"ARQUIVO FILTRADO GERADO\n{out}\n"
                f"entrada={source_count:,} | saída={len(evidence):,}"
            )
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.critical(self, "Filtragem", f"Falha ao gerar arquivo filtrado:\n{exc}")


class FilteringPhasePage(QWidget):
    """Fase 2 para fontes não-MAME; MAME é operado exclusivamente no Arcade Studio."""

    SYSTEMS = ("No-Intro", "Redump", "WHLoader", "C64")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("2 — FILTRAGEM DE ROMS")
        title.setProperty("role", "title")
        layout.addWidget(title)
        description = QLabel(
            "MAME é tratado integralmente no Arcade Studio. Esta fase permanece para as demais fontes "
            "e trabalha somente sobre scans já concluídos."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        self.pages: list[QWidget] = []
        from PySide6.QtWidgets import QTabWidget
        self.tabs = QTabWidget()
        self.tabs.setObjectName("filterSystemTabs")
        for source in self.SYSTEMS:
            page = _GenericFilterTab(source, self)
            self.pages.append(page)
            self.tabs.addTab(page, source)
        layout.addWidget(self.tabs, 1)

    def refresh(self) -> None:
        for page in self.pages:
            page.refresh()


__all__ = ["FilteringPhasePage"]
