"""Painel de filtros MAME V2 do Arcade Studio.

A interface usa somente as opções descobertas no snapshot selecionado e
aplica as regras pelo motor V2. Nenhum novo scan é executado.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
    QTabWidget, QVBoxLayout, QWidget,
)

from ..models.arcade_classification import (
    ArcadeContentType,
    ArcadeGenre,
    ArcadeHardwareFamily,
    ArcadeInputType,
    WheelAngleClass,
)
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
        "mechanical": False,
        "dance": False,
        "console": False,
        "handheld": False,
        "fruit_machines": False,
        "quiz": False,
        "tabletop": False,
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
    """Editor MAME V2 compacto, responsivo e orientado a facetas reais."""

    _LABELS = {
        "playability": {
            "fully_playable": "Totalmente jogável",
            "functional": "Funcional",
            "partially_playable": "Parcialmente jogável",
            "in_development": "Em desenvolvimento",
            "playable_elsewhere": "Jogável em outro alvo",
            "unplayable": "Não jogável",
            "unknown": "Não classificado",
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
        self._facet_widgets: dict[str, QListWidget] = {}
        self._facet_info: dict[str, QLabel] = {}
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(180)
        self._preview_timer.timeout.connect(self._start_preview)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 6)
        root.setSpacing(5)

        title = QLabel("MAME — FILTROS V2")
        title.setProperty("role", "title")
        root.addWidget(title)

        source = QGroupBox("Snapshot")
        source.setMaximumHeight(70)
        form = QFormLayout(source)
        form.setContentsMargins(8, 5, 8, 5)
        form.setVerticalSpacing(3)
        row = QHBoxLayout()
        self.scan_combo = QComboBox()
        self.scan_combo.currentIndexChanged.connect(self._scan_changed)
        row.addWidget(self.scan_combo, 1)
        refresh = QPushButton("ATUALIZAR")
        refresh.clicked.connect(self.refresh)
        row.addWidget(refresh)
        form.addRow("Scan:", row)
        self.scan_info = QLabel("Nenhum scan selecionado.")
        self.scan_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Estado:", self.scan_info)
        root.addWidget(source)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._essential_tab(), "Essencial")
        self.tabs.addTab(self._classification_tab(), "Classificação")
        self.tabs.addTab(self._technical_tab(), "Hardware / Controles")
        self.tabs.addTab(self._set_tab(), "SET")
        root.addWidget(self.tabs, 1)

        result = QGroupBox("Resultado")
        result.setMaximumHeight(125)
        rv = QVBoxLayout(result)
        rv.setContentsMargins(8, 5, 8, 6)
        self.result = QLabel("Aguardando scan…")
        self.result.setWordWrap(True)
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        rv.addWidget(self.result, 1)
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
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        box = QGroupBox("Exclusões rápidas")
        grid = QGridLayout(box)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setHorizontalSpacing(22)
        grid.setVerticalSpacing(9)
        self.fundamental: dict[str, QCheckBox] = {}
        labels = {
            "mechanical": "Mecânicas / eletromecânicas",
            "dance": "Dança",
            "console": "Consoles",
            "handheld": "Portáteis / handhelds",
            "fruit_machines": "Fruit machines / gambling / redemption",
            "quiz": "Quiz / trivia",
            "tabletop": "Tabletop",
        }
        for index, (key, label) in enumerate(labels.items()):
            check = QCheckBox(label)
            check.stateChanged.connect(self._changed)
            self.fundamental[key] = check
            grid.addWidget(check, index // 3, index % 3)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        layout.addWidget(box)
        hint = QLabel("Marque para excluir. O preview é recalculado em segundo plano.")
        hint.setProperty("role", "muted")
        layout.addWidget(hint)
        layout.addStretch()
        return page

    def _classification_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 6, 4, 4)
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        for index, (key, title) in enumerate((
            ("content", "Tipo de conteúdo"),
            ("playability", "Jogabilidade"),
            ("genre", "Gênero"),
        )):
            grid.addWidget(self._facet_box(key, title), 0, index)
        for column in range(3):
            grid.setColumnStretch(column, 1)
        layout.addLayout(grid, 1)
        return page

    def _technical_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(4, 6, 4, 4)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(0, 0, 4, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        facets = (
            ("hardware", "Hardware / plataforma"),
            ("manufacturer", "Fabricante"),
            ("series", "Série / família"),
            ("input", "Controles"),
            ("wheel", "Rotação do volante"),
        )
        for index, (key, title) in enumerate(facets):
            grid.addWidget(self._facet_box(key, title), index // 3, index % 3)
        for column in range(3):
            grid.setColumnStretch(column, 1)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return page

    def _facet_box(self, key: str, title: str) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(7, 8, 7, 7)
        layout.setSpacing(3)
        info = QLabel("Aguardando scan…")
        info.setObjectName(f"facetInfo_{key}")
        info.setProperty("role", "muted")
        info.setWordWrap(True)
        self._facet_info[key] = info
        layout.addWidget(info)
        widget = QListWidget()
        widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        widget.setMinimumHeight(78)
        widget.setMaximumHeight(118)
        widget.setAlternatingRowColors(True)
        widget.itemSelectionChanged.connect(self._changed)
        self._facet_widgets[key] = widget
        layout.addWidget(widget, 1)
        return box

    def _set_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        physical = QGroupBox("Estrutura do SET")
        pf = QFormLayout(physical)
        self.set_type = QComboBox()
        self.set_type.addItem("Split", "split")
        self.set_type.addItem("Non-Merged", "non_merged")
        self.set_type.addItem("Full-Merged", "full_merged")
        self.set_type.currentIndexChanged.connect(self._changed)
        pf.addRow("Tipo:", self.set_type)
        self.clone_policy = QComboBox()
        self.clone_policy.addItem("Parents + clones", "with_clones")
        self.clone_policy.addItem("Somente parents", "parents_only")
        self.clone_policy.currentIndexChanged.connect(self._changed)
        pf.addRow("Clones:", self.clone_policy)

        components = QGroupBox("Componentes")
        cg = QGridLayout(components)
        self.bios = QCheckBox("Incluir BIOS")
        self.devices = QCheckBox("Incluir Devices")
        self.chd = QCheckBox("Incluir CHDs")
        self.chd.setChecked(True)
        self.optional = QCheckBox("Incluir componentes opcionais")
        self.working = QCheckBox("Somente machines working")
        for index, check in enumerate((self.bios, self.devices, self.chd, self.optional, self.working)):
            check.stateChanged.connect(self._changed)
            cg.addWidget(check, index // 2, index % 2)
        cg.setColumnStretch(0, 1)
        cg.setColumnStretch(1, 1)

        grid.addWidget(physical, 0, 0)
        grid.addWidget(components, 0, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        layout.addStretch()
        return page

    def refresh(self) -> None:
        old = str(self.scan_combo.currentData() or "") if self.scan_combo.count() else ""
        root = scans_root() / "mame"
        files = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if root.is_dir() else []
        preferred = root / "MAME - 0.289_mame0289 - Arcade.json"
        if preferred.is_file():
            files = [preferred] + [p for p in files if p != preferred]
        paths = [str(p) for p in files]
        if old and old in paths and Path(old) == self._scan_path and self._facets_loaded:
            return
        self.scan_combo.blockSignals(True)
        self.scan_combo.clear()
        for path in files:
            self.scan_combo.addItem(path.name, str(path))
        if old in paths:
            self.scan_combo.setCurrentIndex(paths.index(old))
        self.scan_combo.blockSignals(False)
        self._scan_changed()

    def _scan_changed(self, *_args) -> None:
        value = self.scan_combo.currentData()
        self._scan_path = Path(str(value)) if value else None
        self._facets_loaded = False
        if self._scan_path is None or not self._scan_path.is_file():
            self.scan_info.setText("Nenhum snapshot JSON válido em data/scans/mame.")
            self.apply.setEnabled(False)
            return
        self.scan_info.setText(f"{self._scan_path}\nDescobrindo opções do snapshot…")
        self.apply.setEnabled(False)
        self._start_worker("facets")

    def _start_worker(self, operation: str) -> None:
        if self._scan_path is None or not self._scan_path.is_file() or (self._worker and self._worker.isRunning()):
            return
        self._worker = _FilterWorker(operation, self._scan_path, self._state())
        self._worker.ready.connect(self._worker_ready)
        self._worker.failed.connect(self._worker_failed)
        self._worker.finished.connect(self._worker_finished)
        self._worker.start()

    def _worker_finished(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

    def _worker_ready(self, operation: str, payload) -> None:
        if operation == "facets":
            self._populate_facets(payload)
            self._facets_loaded = True
            self.apply.setEnabled(True)
            self.scan_info.setText(f"{self._scan_path}\nOpções descobertas no snapshot.")
        elif operation == "preview":
            self.result.setText(self._format_result(payload, "Preview"))
        else:
            self.result.setText(self._format_result(payload, "Filtro gerado") + f"\nArquivo: {payload.get('filtered_file_path', '—')}")
            self.apply.setEnabled(True)

    def _worker_failed(self, message: str) -> None:
        self.result.setText(f"Falha no filtro V2: {message}")
        self.apply.setEnabled(bool(self._facets_loaded))

    def _populate_facets(self, facets: dict[str, list[dict[str, object]]]) -> None:
        for key, widget in self._facet_widgets.items():
            widget.blockSignals(True)
            widget.clear()
            values = facets.get(key, [])
            for entry in values:
                value = str(entry.get("value"))
                count = int(entry.get("count") or 0)
                label = self._LABELS.get(key, {}).get(value, value.replace("_", " ").title())
                item = QListWidgetItem(f"{label}  ({count:,})")
                item.setData(Qt.ItemDataRole.UserRole, value)
                widget.addItem(item)
            widget.blockSignals(False)
            info = self._facet_info.get(key)
            if info:
                info.setText(f"{len(values):,} opções • múltipla = OR • dimensões = AND")

    def _state(self) -> MameFilterState:
        state = MameFilterState()
        state.mame_set_type = str(self.set_type.currentData())
        state.mame_clone_policy = str(self.clone_policy.currentData())
        state.mame_include_bios = self.bios.isChecked()
        state.mame_include_devices = self.devices.isChecked()
        state.mame_include_chd = self.chd.isChecked()
        state.mame_include_optional = self.optional.isChecked()
        state.mame_working_only = self.working.isChecked()
        state.fundamental = {key: check.isChecked() for key, check in self.fundamental.items()}
        for key, widget in self._facet_widgets.items():
            setattr(state, key, [str(item.data(Qt.ItemDataRole.UserRole)) for item in widget.selectedItems()])
        return state

    def _changed(self, *_args) -> None:
        if self._facets_loaded:
            self._preview_timer.start()

    def _start_preview(self) -> None:
        self._start_worker("preview")

    @staticmethod
    def _format_result(payload: dict, prefix: str) -> str:
        stages = payload.get("stage_counts") or {}
        reasons = payload.get("filter_counts") or {}
        reason_text = " | ".join(f"{key}={value:,}" for key, value in list(reasons.items())[:8]) or "nenhum"
        return (
            f"{prefix}: {int(payload.get('input_count', 0)):,} entradas → "
            f"{int(payload.get('output_count', 0)):,} permanecem → "
            f"{int(payload.get('filtered_count', 0)):,} excluídas.\n"
            "Pipeline: " + " | ".join(f"{key}={value:,}" for key, value in stages.items())
            + f"\nMotivos: {reason_text}"
        )

    def _save_profile(self) -> None:
        if self._scan_path is None:
            QMessageBox.warning(self, "Filtros MAME", "Selecione um scan primeiro.")
            return
        path = data_root() / "mame_filter_profiles_v2.json"
        state = asdict(self._state())
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            profiles = raw if isinstance(raw, list) else []
        except (OSError, ValueError, TypeError):
            profiles = []
        profiles = [item for item in profiles if not isinstance(item, dict) or item.get("profile_id") != state["profile_id"]]
        profiles.append(state)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(profiles, indent=2, ensure_ascii=False), encoding="utf-8")
        self.result.setText(f"Perfil V2 salvo em:\n{path}")

    def _apply(self) -> None:
        if self._scan_path is None or not self._facets_loaded:
            return
        self.apply.setEnabled(False)
        self._start_worker("apply")


__all__ = ["MameFiltersPanel", "MameFilterState"]
