"""Hub visual compacto de sistemas não-MAME e suas filtragens V2."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox, QLabel, QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget

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
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        title = QLabel(f"{self.source} — FILTRAGEM")
        title.setProperty("role", "title")
        layout.addWidget(title)
        description = QLabel("Trabalha somente sobre snapshots concluídos; o scan bruto permanece preservado.")
        description.setWordWrap(True)
        layout.addWidget(description)
        box = QGroupBox("Entrada")
        form = QVBoxLayout(box)
        form.setContentsMargins(8, 8, 8, 7)
        self.scan_combo = QComboBox()
        self.scan_combo.currentIndexChanged.connect(self._changed)
        form.addWidget(self.scan_combo)
        self.info = QLabel(NO_SCAN_SELECTED_TEXT)
        self.info.setWordWrap(True)
        form.addWidget(self.info)
        layout.addWidget(box)
        rules = QGroupBox("Curadoria")
        rules_layout = QVBoxLayout(rules)
        rules_layout.setContentsMargins(8, 8, 8, 7)
        self.current_only = QCheckBox("Manter somente itens CURRENT")
        self.current_only.setChecked(True)
        self.keep_duplicates = QCheckBox("Manter ocorrências DUPLICATE")
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
                    "SELECT * FROM scan_runs WHERE status='completed' AND lower(source)=lower(?) ORDER BY started_at DESC",
                    (self.source,),
                ).fetchall()
        except sqlite3.Error:
            rows = []
        for row in rows:
            data = dict(row)
            self.scan_combo.addItem(
                f"{data.get('system') or self.source} › {data.get('catalog_label') or 'catálogo'} | {data.get('scan_id')}",
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
            f"Itens={int(data.get('items_examined') or 0):,} | CURRENT={counts.get('CURRENT', 0):,} | "
            f"MISSING={counts.get('MISSING', 0):,} | WRONG={counts.get('WRONG', 0):,}"
        )
        self.apply_button.setEnabled(Path(str(data.get("scan_file_path") or "")).is_file())
        self._preview()

    def _keep(self, evidence: dict) -> bool:
        status = str(evidence.get("status") or "").upper()
        return status == "CURRENT" or (status == "DUPLICATE" and self.keep_duplicates.isChecked())

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
            self.preview.setText(f"Preview: entrada={len(evidence):,} | saída={len(selected):,} | excluídas={len(evidence) - len(selected):,}")
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
            out = out_dir / f"{self.source}_{label}_{payload.get('scan_type', 'full')}_FILTER_{run_id}.json"
            result = {
                "format": "SERM-FILTER-V2", "schema_version": 2, "filter_run_id": run_id,
                "scan_id": payload.get("scan_id"), "profile_id": f"generic-{self.source.casefold()}",
                "source": payload.get("source"), "system": payload.get("system"),
                "scan_type": payload.get("scan_type", "full"), "catalog_label": payload.get("catalog_label"),
                "catalog_hash": payload.get("catalog_hash"), "source_scan_file": str(source_path.resolve()),
                "created_at": datetime.now(UTC).isoformat(), "input_count": source_count,
                "output_count": len(evidence), "filtered_count": source_count - len(evidence),
                "filters": {"current_only": self.current_only.isChecked(), "keep_duplicates": self.keep_duplicates.isChecked()},
                "evidence": evidence,
            }
            out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            result["filtered_file_path"] = str(out)
            ScanRepository(database_path()).save_filter_result(result)
            self.result.setText(f"ARQUIVO FILTRADO GERADO\n{out}\nentrada={source_count:,} | saída={len(evidence):,}")
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.critical(self, "Filtragem", f"Falha ao gerar arquivo filtrado:\n{exc}")


class _SystemCard(QFrame):
    """Card visual compacto de um sistema não-MAME."""

    def __init__(self, number: str, title: str, description: str, action, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("systemCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(4)
        number_label = QLabel(number)
        number_label.setObjectName("systemCardNumber")
        title_label = QLabel(title)
        title_label.setObjectName("systemCardTitle")
        description_label = QLabel(description)
        description_label.setObjectName("systemCardDescription")
        description_label.setWordWrap(True)
        button = QPushButton("ABRIR")
        button.clicked.connect(action)
        layout.addWidget(number_label)
        layout.addWidget(title_label)
        layout.addWidget(description_label, 1)
        layout.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)


class FilteringPhasePage(QWidget):
    """Bibliotecas não-MAME em uma navegação compacta por sistema."""

    SYSTEMS = ("No-Intro", "Redump", "WHLoader", "C64")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.pages: list[QWidget] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(7)
        title = QLabel("OUTROS SISTEMAS")
        title.setProperty("role", "title")
        root.addWidget(title)
        description = QLabel("Bibliotecas fora do fluxo MAME. Cada sistema mantém seu próprio scan e filtragem.")
        description.setWordWrap(True)
        root.addWidget(description)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("systemLibraryTabs")
        for source in self.SYSTEMS:
            page = _GenericFilterTab(source, self)
            self.pages.append(page)
            self.tabs.addTab(page, source)
        self.tabs.hide()
        cards = QGridLayout()
        cards.setContentsMargins(0, 0, 0, 0)
        cards.setHorizontalSpacing(7)
        cards.setVerticalSpacing(7)
        descriptions = {
            "No-Intro": "Consoles e portáteis por catálogo e região.",
            "Redump": "Catálogos ópticos e identidade física.",
            "WHLoader": "Biblioteca WHDLoad para Amiga.",
            "C64": "Catálogo C64/TOSEC e snapshots.",
        }
        for index, source in enumerate(self.SYSTEMS):
            cards.addWidget(
                _SystemCard(f"0{index + 1}", source, descriptions[source], lambda i=index: self._open(i), self),
                0, index,
            )
        root.addLayout(cards)
        root.addWidget(self.tabs, 1)
        self.tabs.currentChanged.connect(lambda _index: self._refresh_current())
        self._open(0)

    def _open(self, index: int) -> None:
        self.tabs.show()
        self.tabs.setCurrentIndex(index)
        self._refresh_current()

    def _refresh_current(self) -> None:
        page = self.tabs.currentWidget()
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            refresh()

    def refresh(self) -> None:
        self._refresh_current()


__all__ = ["FilteringPhasePage"]
