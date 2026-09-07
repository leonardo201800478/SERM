"""Painel de filtros MAME V2 do Arcade Studio.

As opções de classificação são descobertas no snapshot selecionado. O painel
não reproduz a tela legada nem executa novo scan.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QTabWidget,
    QVBoxLayout, QWidget,
)

from ..models.arcade_classification import ArcadeContentType, ArcadeGenre, ArcadeHardwareFamily, ArcadeInputType, WheelAngleClass
from ..runtime.paths import data_root, scans_root
from ..services.arcade.mame_filter_v2_service import MameFilterV2Service


@dataclass(slots=True)
class MameFilterState:
    profile_id: str = "mame-v2"
    name: str = "MAME Arcade"
    mame_set_type: str = "split"
    mame_clone_policy: str = "with_clones"
    mame_include_bios: bool = False
    mame_include_devices: bool = False
    mame_include_chd: bool = True
    mame_include_optional: bool = True
    mame_working_only: bool = False
    fundamental: dict[str, bool] = field(default_factory=lambda: {
        "mechanical": False, "dance": False, "console": False,
        "handheld": False, "fruit_machines": False, "quiz": False, "tabletop": False,
    })
    categories: list[str] = field(default_factory=list)
    subcategories: list[str] = field(default_factory=list)
    content: list[str] = field(default_factory=list)
    playability: list[str] = field(default_factory=list)
    genre: list[str] = field(default_factory=list)
    hardware: list[str] = field(default_factory=list)
    manufacturer: list[str] = field(default_factory=list)
    series: list[str] = field(default_factory=list)
    input: list[str] = field(default_factory=list)
    wheel: list[str] = field(default_factory=list)


class _FilterWorker(QThread):
    ready = Signal(str, object)
    failed = Signal(str)

    def __init__(self, operation: str, path: Path, state: MameFilterState) -> None:
        super().__init__()
        self.operation, self.path, self.state = operation, path, state

    def run(self) -> None:
        try:
            if self.operation == "facets":
                result = MameFilterV2Service.facets(self.path)
            elif self.operation == "preview":
                result = MameFilterV2Service.preview(self.path, self.state)
            else:
                result = MameFilterV2Service.apply(self.path, self.state)
            self.ready.emit(self.operation, result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class MameFiltersPanel(QWidget):
    """Editor MAME V2 com facetas reais, preview assíncrono e estado explícito."""

    _LABELS = {
        "playability": {
            "fully_playable": "Totalmente jogável", "functional": "Funcional",
            "partially_playable": "Parcialmente jogável", "in_development": "Em desenvolvimento",
            "playable_elsewhere": "Jogável em outro alvo", "unplayable": "Não jogável", "unknown": "Não classificado",
        },
        "content": {item.value: item.value.replace("_", " ").title() for item in ArcadeContentType},
        "genre": {item.value: item.value.replace("_", " ").title() for item in ArcadeGenre},
        "hardware": {item.value: item.value.replace("_", " ").upper() for item in ArcadeHardwareFamily},
        "input": {item.value: item.value.replace("_", " ").title() for item in ArcadeInputType},
        "wheel": {item.value: f"{item.value}°" for item in WheelAngleClass},
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scan_path: Path | None = None
        self._worker: _FilterWorker | None = None
        self._facets_loaded = False
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(180)
        self._preview_timer.timeout.connect(self._start_preview)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("MAME — FILTROS V2")
        title.setProperty("role", "title")
        root.addWidget(title)
        intro = QLabel("Selecione um snapshot já escaneado. O SERM descobre as opções existentes e aplica as regras no motor V2. Nenhum novo scan é executado.")
        intro.setWordWrap(True)
        root.addWidget(intro)

        source = QGroupBox("Entrada")
        form = QFormLayout(source)
        row = QHBoxLayout()
        self.scan_combo = QComboBox()
        self.scan_combo.currentIndexChanged.connect(self._scan_changed)
        row.addWidget(self.scan_combo, 1)
        refresh = QPushButton("ATUALIZAR")
        refresh.clicked.connect(self.refresh)
        row.addWidget(refresh)
        form.addRow("Scan:", row)
        self.scan_info = QLabel("Nenhum scan selecionado.")
        self.scan_info.setWordWrap(True)
        form.addRow("Estado:", self.scan_info)
        root.addWidget(source)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._essential_tab(), "Essencial")
        self.tabs.addTab(self._classification_tab(), "Classificação")
        self.tabs.addTab(self._technical_tab(), "Hardware / Controles")
        self.tabs.addTab(self._set_tab(), "SET")
        root.addWidget(self.tabs, 1)

        result = QGroupBox("Resultado em tempo real")
        rv = QVBoxLayout(result)
        self.result = QLabel("Aguardando scan…")
        self.result.setWordWrap(True)
        rv.addWidget(self.result)
        actions = QHBoxLayout()
        self.save = QPushButton("SALVAR PERFIL")
        self.save.clicked.connect(self._save_profile)
        self.apply = QPushButton("APLICAR E GERAR FILTER JSON")
        self.apply.clicked.connect(self._apply)
        self.apply.setEnabled(False)
        actions.addWidget(self.save)
        actions.addWidget(self.apply)
        actions.addStretch()
        rv.addLayout(actions)
        root.addWidget(result)

    def _essential_tab(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page)
        box = QGroupBox("Exclusões rápidas"); v = QVBoxLayout(box)
        self.fundamental: dict[str, QCheckBox] = {}
        labels = {
            "mechanical": "Mecânicas / eletromecânicas", "dance": "Dança", "console": "Consoles",
            "handheld": "Portáteis / handhelds", "fruit_machines": "Fruit machines / gambling / redemption",
            "quiz": "Quiz / trivia", "tabletop": "Tabletop",
        }
        for key, label in labels.items():
            check = QCheckBox(label); check.stateChanged.connect(self._changed)
            self.fundamental[key] = check; v.addWidget(check)
        layout.addWidget(box)
        hint = QLabel("Marcado = excluir. Alterações recalculam somente o preview do motor V2 em background.")
        hint.setWordWrap(True); layout.addWidget(hint); layout.addStretch(); return page

    def _classification_tab(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page)
        for key, title in (("content", "Tipo de conteúdo"), ("playability", "Jogabilidade"), ("genre", "Gênero")):
            layout.addWidget(self._facet_box(key, title))
        layout.addStretch(); return page

    def _technical_tab(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page)
        for key, title in (("hardware", "Hardware / plataforma"), ("manufacturer", "Fabricante"), ("series", "Série / família"), ("input", "Controles"), ("wheel", "Rotação do volante")):
            layout.addWidget(self._facet_box(key, title))
        layout.addStretch(); return page

    def _facet_box(self, key: str, title: str) -> QGroupBox:
        box = QGroupBox(title); v = QVBoxLayout(box)
        info = QLabel("Aguardando scan…"); info.setObjectName(f"facetInfo_{key}"); v.addWidget(info)
        widget = QListWidget(); widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection); widget.setMaximumHeight(165); widget.itemSelectionChanged.connect(self._changed)
        self._facet_widgets[key] = widget; v.addWidget(widget); return box

    def _set_tab(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page)
        box = QGroupBox("Política física do conjunto"); form = QFormLayout(box)
        self.set_type = QComboBox(); self.set_type.addItem("Split", "split"); self.set_type.addItem("Non-Merged", "non_merged"); self.set_type.addItem("Full-Merged", "full_merged"); self.set_type.currentIndexChanged.connect(self._changed); form.addRow("Tipo de SET:", self.set_type)
        self.clone_policy = QComboBox(); self.clone_policy.addItem("Parents + clones", "with_clones"); self.clone_policy.addItem("Somente parents", "parents_only"); self.clone_policy.currentIndexChanged.connect(self._changed); form.addRow("Clones:", self.clone_policy)
        self.bios = QCheckBox("Incluir BIOS"); self.devices = QCheckBox("Incluir Devices"); self.chd = QCheckBox("Incluir CHDs"); self.chd.setChecked(True); self.optional = QCheckBox("Incluir componentes opcionais"); self.working = QCheckBox("Somente machines working")
        for check in (self.bios, self.devices, self.chd, self.optional, self.working): check.stateChanged.connect(self._changed); form.addRow(check)
        layout.addWidget(box); layout.addStretch(); return page

    def refresh(self) -> None:
        old = str(self.scan_combo.currentData() or "") if self.scan_combo.count() else ""
        root = scans_root() / "mame"
        files = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if root.is_dir() else []
        preferred = root / "MAME - 0.289_mame0289 - Arcade.json"
        if preferred.is_file(): files = [preferred] + [p for p in files if p != preferred]
        paths = [str(p) for p in files]
        if old and old in paths and Path(old) == self._scan_path and self._facets_loaded:
            return
        self.scan_combo.blockSignals(True); self.scan_combo.clear()
        for path in files: self.scan_combo.addItem(path.name, str(path))
        if old in paths: self.scan_combo.setCurrentIndex(paths.index(old))
        self.scan_combo.blockSignals(False); self._scan_changed()

    def _scan_changed(self, *_args) -> None:
        value = self.scan_combo.currentData(); self._scan_path = Path(str(value)) if value else None; self._facets_loaded = False
        if self._scan_path is None or not self._scan_path.is_file(): self.scan_info.setText("Nenhum snapshot JSON válido em data/scans/mame."); self.apply.setEnabled(False); return
        self.scan_info.setText(f"{self._scan_path}\nDescobrindo as opções existentes no scan…"); self.apply.setEnabled(False); self._start_worker("facets")

    def _start_worker(self, operation: str) -> None:
        if self._scan_path is None or not self._scan_path.is_file() or (self._worker and self._worker.isRunning()): return
        self._worker = _FilterWorker(operation, self._scan_path, self._state())
        self._worker.ready.connect(self._worker_ready); self._worker.failed.connect(self._worker_failed); self._worker.finished.connect(self._worker_finished); self._worker.start()

    def _worker_finished(self) -> None:
        worker = self._worker; self._worker = None
        if worker is not None: worker.deleteLater()

    def _worker_ready(self, operation: str, payload) -> None:
        if operation == "facets":
            self._populate_facets(payload); self._facets_loaded = True; self.apply.setEnabled(True); self.scan_info.setText(f"{self._scan_path}\nOpções descobertas no snapshot. Nenhum catálogo fixo da V1 está sendo usado.")
        elif operation == "preview":
            self.result.setText(self._format_result(payload, "Preview"))
        else:
            self.result.setText(self._format_result(payload, "Filtro gerado") + f"\nArquivo: {payload.get('filtered_file_path', '—')}"); self.apply.setEnabled(True)

    def _worker_failed(self, message: str) -> None:
        self.result.setText(f"Falha no filtro V2: {message}"); self.apply.setEnabled(bool(self._facets_loaded))

    def _populate_facets(self, facets: dict[str, list[dict[str, object]]]) -> None:
        for key, widget in self._facet_widgets.items():
            widget.blockSignals(True); widget.clear(); values = facets.get(key, [])
            for entry in values:
                value = str(entry.get("value")); count = int(entry.get("count") or 0); label = self._LABELS.get(key, {}).get(value, value.replace("_", " ").title())
                item = QListWidgetItem(f"{label}  ({count:,})"); item.setData(Qt.ItemDataRole.UserRole, value); widget.addItem(item)
            widget.blockSignals(False)
            info = self.findChild(QLabel, f"facetInfo_{key}")
            if info: info.setText(f"{len(values):,} opções encontradas. Seleção múltipla = OR nesta dimensão; dimensões diferentes = AND.")

    def _state(self) -> MameFilterState:
        state = MameFilterState(); state.mame_set_type = str(self.set_type.currentData()); state.mame_clone_policy = str(self.clone_policy.currentData()); state.mame_include_bios = self.bios.isChecked(); state.mame_include_devices = self.devices.isChecked(); state.mame_include_chd = self.chd.isChecked(); state.mame_include_optional = self.optional.isChecked(); state.mame_working_only = self.working.isChecked(); state.fundamental = {key: check.isChecked() for key, check in self.fundamental.items()}
        for key, widget in self._facet_widgets.items(): setattr(state, key, [str(item.data(Qt.ItemDataRole.UserRole)) for item in widget.selectedItems()])
        return state

    def _changed(self, *_args) -> None:
        if self._facets_loaded: self._preview_timer.start()

    def _start_preview(self) -> None:
        self._start_worker("preview")

    @staticmethod
    def _format_result(payload: dict, prefix: str) -> str:
        stages = payload.get("stage_counts") or {}; reasons = payload.get("filter_counts") or {}
        reason_text = " | ".join(f"{key}={value:,}" for key, value in list(reasons.items())[:8]) or "nenhum"
        return f"{prefix}: {int(payload.get('input_count', 0)):,} entradas → {int(payload.get('output_count', 0)):,} permanecem → {int(payload.get('filtered_count', 0)):,} excluídas.\nPipeline: " + " | ".join(f"{key}={value:,}" for key, value in stages.items()) + f"\nMotivos: {reason_text}"

    def _save_profile(self) -> None:
        if self._scan_path is None: QMessageBox.warning(self, "Filtros MAME", "Selecione um scan primeiro."); return
        path = data_root() / "mame_filter_profiles_v2.json"; state = asdict(self._state())
        try: raw = json.loads(path.read_text(encoding="utf-8")); profiles = raw if isinstance(raw, list) else []
        except (OSError, ValueError, TypeError): profiles = []
        profiles = [item for item in profiles if not isinstance(item, dict) or item.get("profile_id") != state["profile_id"]]; profiles.append(state); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(profiles, indent=2, ensure_ascii=False), encoding="utf-8"); self.result.setText(f"Perfil V2 salvo em:\n{path}")

    def _apply(self) -> None:
        if self._scan_path is None or not self._facets_loaded: return
        self.apply.setEnabled(False); self._start_worker("apply")


__all__ = ["MameFiltersPanel", "MameFilterState"]
