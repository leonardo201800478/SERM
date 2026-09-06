"""Fase 2: filtragem de snapshots já concluídos, separada por sistema."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from ..runtime.paths import data_root, database_path, scans_root
from ..services.mame_fundamental_filter_service import DEFAULT_FILTERS, FILTER_DEFINITIONS, MameFundamentalFilterService
from ..services.scan_filter_service import ScanFilterService
from ..services.scan_repository import ScanRepository
from .filter_profiles_page import FilterProfileData


class _GenericFilterTab(QWidget):
    """Filtro mínimo e seguro para fontes sem regras específicas ainda definidas."""

    def __init__(self, source: str, parent=None) -> None:
        super().__init__(parent)
        self.source = source
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel(f"{self.source} — FILTRAGEM")
        title.setProperty("role", "title")
        layout.addWidget(title)
        description = QLabel("Esta guia trabalha somente sobre o arquivo de scan selecionado. Não revarre o diretório e não altera o snapshot bruto.")
        description.setWordWrap(True)
        layout.addWidget(description)
        box = QGroupBox("1. Scan completo de entrada")
        form = QVBoxLayout(box)
        self.scan_combo = QComboBox()
        self.scan_combo.currentIndexChanged.connect(self._changed)
        form.addWidget(self.scan_combo)
        self.info = QLabel("Nenhum scan selecionado.")
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
                rows = connection.execute("SELECT * FROM scan_runs WHERE status='completed' AND lower(source)=lower(?) ORDER BY started_at DESC", (self.source,)).fetchall()
        except sqlite3.Error:
            rows = []
        for row in rows:
            data = dict(row)
            self.scan_combo.addItem(f"{data['system']} › {data['catalog_label'] or 'catalogo'} | {data['scan_id']}", data)
        self.scan_combo.blockSignals(False)
        self._changed()

    def _changed(self, *_args) -> None:
        data = self.scan_combo.currentData()
        if not isinstance(data, dict):
            self.info.setText("Nenhum scan concluído para esta fonte.")
            self.apply_button.setEnabled(False)
            return
        counts = self._counts(data)
        self.info.setText(f"Entrada: {data.get('scan_file_path') or '—'}\nItens={int(data.get('items_examined') or 0):,} | CURRENT={counts.get('CURRENT', 0):,} | MISSING={counts.get('MISSING', 0):,} | WRONG={counts.get('WRONG', 0):,}")
        self.apply_button.setEnabled(Path(str(data.get('scan_file_path') or '')).is_file())
        self._preview()

    @staticmethod
    def _counts(data: dict) -> dict:
        try:
            return json.loads(data.get("status_counts_json") or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    def _preview(self) -> None:
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
            selected = [e for e in evidence if self._keep(e)]
            self.preview.setText(f"Preview: entrada={len(evidence):,} | saída={len(selected):,} | excluídas={len(evidence)-len(selected):,}")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self.preview.setText(f"Preview indisponível: {exc}")

    def _keep(self, evidence: dict) -> bool:
        status = str(evidence.get("status") or "").upper()
        if status == "CURRENT":
            return True
        return status == "DUPLICATE" and self.keep_duplicates.isChecked()

    def apply(self) -> None:
        data = self.scan_combo.currentData()
        if not isinstance(data, dict):
            return
        source_path = Path(str(data.get("scan_file_path") or ""))
        if not source_path.is_file():
            QMessageBox.warning(self, "Filtragem", "O arquivo de scan não existe mais.")
            return
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8"))
            evidence = [e for e in payload.get("evidence", []) if self._keep(e)]
            run_id = uuid4().hex[:16]
            out_dir = scans_root() / "filtered" / str(self.source).casefold().replace("-", "_")
            out_dir.mkdir(parents=True, exist_ok=True)
            label = str(payload.get("catalog_label") or "catalog").replace("/", "_").replace("\\", "_")
            out = out_dir / f"{self.source}_{label}_{payload.get('scan_type', 'full')}_FILTER_{run_id}.json"
            source_count = len(payload.get("evidence", []))
            result = {
                "format": "SERM-FILTER-V1", "filter_run_id": run_id, "scan_id": payload.get("scan_id"),
                "profile_id": f"generic-{self.source.casefold()}", "source": payload.get("source"), "system": payload.get("system"),
                "scan_type": payload.get("scan_type", "full"), "catalog_label": payload.get("catalog_label"), "catalog_hash": payload.get("catalog_hash"),
                "source_scan_file": str(source_path.resolve()), "created_at": datetime.now(timezone.utc).timestamp(),
                "input_count": source_count, "output_count": len(evidence), "filtered_count": source_count - len(evidence),
                "filter_counts": {"status": "current_or_duplicate" if self.keep_duplicates.isChecked() else "current_only"},
                "filters": {"current_only": self.current_only.isChecked(), "keep_duplicates": self.keep_duplicates.isChecked()}, "evidence": evidence,
            }
            out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            result["filtered_file_path"] = str(out)
            ScanRepository(database_path()).save_filter_result(result)
            self.result.setText(f"ARQUIVO FILTRADO GERADO\n{out}\nentrada={source_count:,} | saída={len(evidence):,}")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "Filtragem", f"Falha ao gerar arquivo filtrado:\n{exc}")


class _MameFilterTab(QWidget):
    """Guia MAME com as regras específicas já implementadas na V2."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._profiles_path = data_root() / "filter_profiles.json"
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("MAME — FILTRAGEM")
        title.setProperty("role", "title")
        layout.addWidget(title)
        desc = QLabel("Entrada: somente scan MAME concluído. Saída: novo snapshot filtrado. O scan bruto permanece imutável.")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        box = QGroupBox("1. Scan completo")
        v = QVBoxLayout(box)
        self.scan_combo = QComboBox()
        self.scan_combo.currentIndexChanged.connect(self._scan_changed)
        v.addWidget(self.scan_combo)
        self.scan_info = QLabel("Nenhum scan selecionado.")
        self.scan_info.setWordWrap(True)
        v.addWidget(self.scan_info)
        layout.addWidget(box)
        profile_box = QGroupBox("2. Perfil")
        pv = QVBoxLayout(profile_box)
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        pv.addWidget(self.profile_combo)
        self.save_profile_button = QPushButton("SALVAR PERFIL")
        self.save_profile_button.clicked.connect(self._save_profile)
        pv.addWidget(self.save_profile_button)
        layout.addWidget(profile_box)
        fundamental = QGroupBox("Filtros fundamentais")
        fv = QVBoxLayout(fundamental)
        self.fundamental_checks: dict[str, QCheckBox] = {}
        for key, definition in FILTER_DEFINITIONS.items():
            check = QCheckBox(str(definition["label"]))
            check.setToolTip(str(definition["description"]))
            check.setChecked(DEFAULT_FILTERS[key])
            self.fundamental_checks[key] = check
            fv.addWidget(check)
        layout.addWidget(fundamental)
        advanced = QGroupBox("Seleção de set")
        av = QVBoxLayout(advanced)
        self.clone_policy = QComboBox()
        self.clone_policy.addItem("Com clones", "with_clones")
        self.clone_policy.addItem("Somente parents", "parents_only")
        av.addWidget(self.clone_policy)
        self.include_bios = QCheckBox("Incluir BIOS")
        self.include_devices = QCheckBox("Incluir Devices")
        self.include_optional = QCheckBox("Incluir ROMs opcionais")
        self.working_only = QCheckBox("Somente máquinas working")
        for check in (self.include_bios, self.include_devices, self.include_optional, self.working_only):
            av.addWidget(check)
        layout.addWidget(advanced)
        self.preview = QLabel("Selecione um scan para calcular o resultado.")
        self.preview.setWordWrap(True)
        layout.addWidget(self.preview)
        self.apply_button = QPushButton("APLICAR FILTROS E GERAR ARQUIVO FILTRADO")
        self.apply_button.clicked.connect(self.apply_filters)
        layout.addWidget(self.apply_button)
        self.result_label = QLabel("Nenhum arquivo filtrado gerado nesta sessão.")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        layout.addStretch()

    def refresh(self) -> None:
        self._refresh_scans(); self._refresh_profiles(); self._scan_changed()

    def _refresh_scans(self) -> None:
        self.scan_combo.blockSignals(True); self.scan_combo.clear()
        try:
            with sqlite3.connect(database_path()) as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute("SELECT * FROM scan_runs WHERE status='completed' AND lower(source)='mame' ORDER BY started_at DESC").fetchall()
        except sqlite3.Error:
            rows = []
        for row in rows:
            data = dict(row); self.scan_combo.addItem(f"{data['catalog_label'] or 'MAME'} › {data['scan_type']} | {data['scan_id']}", data)
        self.scan_combo.blockSignals(False)

    def _refresh_profiles(self) -> None:
        profiles: list[FilterProfileData] = []
        try:
            raw = json.loads(self._profiles_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict):
                        try: profiles.append(FilterProfileData(**{k: v for k, v in item.items() if k in FilterProfileData.__dataclass_fields__}))
                        except (TypeError, ValueError): pass
        except (OSError, ValueError, TypeError, json.JSONDecodeError): pass
        self.profile_combo.blockSignals(True); self.profile_combo.clear(); self.profile_combo.addItem("Perfil novo / configuração atual", None)
        for profile in profiles:
            if str(profile.source).casefold() == "mame": self.profile_combo.addItem(f"{profile.name} | {profile.system}", profile)
        self.profile_combo.blockSignals(False)

    @staticmethod
    def _status_count(data: dict, status: str) -> int:
        try: return int(json.loads(data.get("status_counts_json") or "{}").get(status, 0))
        except (TypeError, ValueError, json.JSONDecodeError): return 0

    def _scan_changed(self, *_args) -> None:
        data = self.scan_combo.currentData()
        if not isinstance(data, dict):
            self.scan_info.setText("Nenhum scan selecionado."); self.apply_button.setEnabled(False); return
        self.scan_info.setText(f"Entrada: {data.get('scan_file_path')}\nCURRENT={self._status_count(data,'CURRENT'):,} | MISSING={self._status_count(data,'MISSING'):,} | WRONG={self._status_count(data,'WRONG'):,}")
        self.apply_button.setEnabled(Path(str(data.get('scan_file_path') or '')).is_file()); self._update_preview()

    def _profile_changed(self, *_args) -> None:
        profile = self.profile_combo.currentData()
        if isinstance(profile, FilterProfileData):
            values = MameFundamentalFilterService.load(profile.profile_id)
            for key, check in self.fundamental_checks.items(): check.setChecked(values[key])
            index = self.clone_policy.findData(profile.mame_clone_policy)
            if index >= 0: self.clone_policy.setCurrentIndex(index)
            self.include_bios.setChecked(profile.mame_include_bios); self.include_devices.setChecked(profile.mame_include_devices)
            self.include_optional.setChecked(profile.mame_include_optional); self.working_only.setChecked(profile.mame_working_only)
        self._update_preview()

    def _current_profile(self) -> FilterProfileData | None:
        data = self.scan_combo.currentData()
        if not isinstance(data, dict): return None
        existing = self.profile_combo.currentData()
        if isinstance(existing, FilterProfileData): profile = existing
        else:
            now = datetime.now(timezone.utc).isoformat()
            profile = FilterProfileData(source="MAME", system=str(data.get("system", "MAME")), dat_path=data.get("dat_path"), profile_id=uuid4().hex, name=f"MAME — {data.get('system', 'MAME')} — filtro", created_at=now, updated_at=now)
        profile.mame_clone_policy = str(self.clone_policy.currentData()); profile.mame_include_bios = self.include_bios.isChecked()
        profile.mame_include_devices = self.include_devices.isChecked(); profile.mame_include_optional = self.include_optional.isChecked(); profile.mame_working_only = self.working_only.isChecked()
        return profile

    def _save_profile(self) -> None:
        profile = self._current_profile()
        if profile is None: return
        profiles: list[FilterProfileData] = []
        try:
            raw = json.loads(self._profiles_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict):
                        try: profiles.append(FilterProfileData(**{k: v for k, v in item.items() if k in FilterProfileData.__dataclass_fields__}))
                        except (TypeError, ValueError): pass
        except (OSError, ValueError, TypeError, json.JSONDecodeError): pass
        profiles = [item for item in profiles if item.profile_id != profile.profile_id]; profiles.append(profile)
        self._profiles_path.parent.mkdir(parents=True, exist_ok=True)
        self._profiles_path.write_text(json.dumps([asdict(item) for item in profiles], indent=2, ensure_ascii=False), encoding="utf-8")
        MameFundamentalFilterService.save(profile.profile_id, {key: check.isChecked() for key, check in self.fundamental_checks.items()})

    def _update_preview(self) -> None:
        data = self.scan_combo.currentData()
        if not isinstance(data, dict): return
        path = Path(str(data.get("scan_file_path") or ""))
        if not path.is_file(): self.preview.setText("Arquivo de scan não localizado."); return
        profile = self._current_profile()
        if profile is None: return
        values = {key: check.isChecked() for key, check in self.fundamental_checks.items()}
        try:
            result = ScanFilterService.preview_mame(path, profile, values)
            self.preview.setText(f"Preview: entrada={result['input_count']:,} | selecionadas={result['output_count']:,} | excluídas={result['filtered_count']:,}")
        except Exception as exc: self.preview.setText(f"Preview indisponível: {type(exc).__name__}: {exc}")

    def apply_filters(self) -> None:
        data = self.scan_combo.currentData()
        if not isinstance(data, dict): return
        path = Path(str(data.get("scan_file_path") or ""))
        if not path.is_file(): QMessageBox.warning(self, "Filtragem", "O arquivo de scan não existe mais."); return
        profile = self._current_profile()
        if profile is None: return
        values = {key: check.isChecked() for key, check in self.fundamental_checks.items()}
        try:
            result = ScanFilterService.apply_mame(path, profile, values); self._save_profile(); ScanRepository(database_path()).save_filter_result(result)
            self.result_label.setText(f"ARQUIVO FILTRADO GERADO\n{result['filtered_file_path']}\nentrada={result['input_count']:,} | saída={result['output_count']:,}")
        except Exception as exc: QMessageBox.critical(self, "Filtragem", f"Falha ao gerar arquivo filtrado:\n{exc}")


class FilteringPhasePage(QWidget):
    """Fase 2 independente, com uma subguia para cada família de sistema."""
    SYSTEMS = ("MAME", "No-Intro", "Redump", "WHLoader", "C64")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        title = QLabel("2 — FILTRAGEM DE ROMS"); title.setProperty("role", "title"); layout.addWidget(title)
        description = QLabel("DAT completo → Scan bruto → esta fase seleciona o que deve seguir para a reconstrução. Nenhuma guia de filtragem executa novo scan."); description.setWordWrap(True); layout.addWidget(description)
        self.tabs = QTabWidget(); self.tabs.setObjectName("filterSystemTabs"); self.pages: list[QWidget] = []
        mame = _MameFilterTab(self); self.pages.append(mame); self.tabs.addTab(mame, "MAME")
        for source in self.SYSTEMS[1:]:
            page = _GenericFilterTab(source, self); self.pages.append(page); self.tabs.addTab(page, source)
        layout.addWidget(self.tabs, 1)

    def refresh(self) -> None:
        for page in self.pages:
            if hasattr(page, "refresh"): page.refresh()


__all__ = ["FilteringPhasePage"]
