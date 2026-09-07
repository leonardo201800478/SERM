"""Painel moderno de filtragem MAME do Arcade Studio.

A UI é orientada pelas facetas realmente encontradas no scan. Ela não replica
as telas legadas: catálogo, classificação, jogabilidade, hardware, gênero,
controles e política estrutural são apresentados em um único fluxo.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QTimer, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from ..models.arcade import PlayabilityStatus
from ..models.arcade_classification import (
    ArcadeContentType, ArcadeGenre, ArcadeHardwareFamily, ArcadeInputType,
    WheelAngleClass,
)
from ..runtime.paths import data_root, database_path, scans_root
from ..services.scan_filter_service import ScanFilterService


@dataclass(slots=True)
class MameFilterState:
    profile_id: str = ""
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
        "handheld": False, "fruit_machines": False, "quiz": False,
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
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: str, path: Path, state: MameFilterState) -> None:
        super().__init__()
        self.operation = operation
        self.path = path
        self.state = state

    def run(self) -> None:
        try:
            profile = SimpleNamespace(**asdict(self.state))
            if self.operation == "facets":
                self.ready.emit(ScanFilterService.facets_mame(self.path))
                return
            fundamental = self.state.fundamental
            advanced = {
                "content": self.state.content,
                "playability": self.state.playability,
                "genre": self.state.genre,
                "hardware": self.state.hardware,
                "manufacturer": self.state.manufacturer,
                "series": self.state.series,
                "input": self.state.input,
                "wheel": self.state.wheel,
            }
            if self.operation == "preview":
                self.ready.emit(ScanFilterService.preview_mame(self.path, profile, fundamental, {"categories": self.state.categories, "subcategories": self.state.subcategories}, advanced))
            else:
                self.ready.emit(ScanFilterService.apply_mame(self.path, profile, fundamental, {"categories": self.state.categories, "subcategories": self.state.subcategories}, advanced))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class MameFiltersPanel(QWidget):
    """Editor de filtros MAME V2 orientado a dados do scan selecionado."""

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
        self._preview_timer.setInterval(140)
        self._preview_timer.timeout.connect(self._start_preview)
        self._build_ui()
        self._refresh_scans()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("MAME — FILTROS V2")
        title.setProperty("role", "title")
        root.addWidget(title)
        intro = QLabel("Configure o conteúdo que entra no set. As opções avançadas abaixo são descobertas do scan selecionado; não são uma lista fixa portada da V1.")
        intro.setWordWrap(True)
        root.addWidget(intro)

        source = QGroupBox("1. Scan físico")
        form = QFormLayout(source)
        row = QHBoxLayout()
        self.scan_combo = QComboBox()
        self.scan_combo.currentIndexChanged.connect(self._scan_changed)
        row.addWidget(self.scan_combo, 1)
        refresh = QPushButton("ATUALIZAR")
        refresh.clicked.connect(self._refresh_scans)
        row.addWidget(refresh)
        form.addRow("Snapshot:", row)
        self.scan_info = QLabel("Nenhum scan selecionado.")
        self.scan_info.setWordWrap(True)
        form.addRow("Estado:", self.scan_info)
        root.addWidget(source)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        self.body_layout = QVBoxLayout(body)
        self._build_structural()
        self._build_fundamental()
        self._build_dynamic_sections()
        self.body_layout.addStretch()
        self.scroll.setWidget(body)
        root.addWidget(self.scroll, 1)

        result = QGroupBox("Resultado")
        rv = QVBoxLayout(result)
        self.result = QLabel("Selecione um scan para carregar as facetas.")
        self.result.setWordWrap(True)
        rv.addWidget(self.result)
        actions = QHBoxLayout()
        self.save = QPushButton("SALVAR PERFIL")
        self.save.clicked.connect(self._save_profile)
        self.apply = QPushButton("APLICAR E GERAR FILTRO")
        self.apply.clicked.connect(self._apply)
        self.apply.setEnabled(False)
        actions.addWidget(self.save)
        actions.addWidget(self.apply)
        actions.addStretch()
        rv.addLayout(actions)
        root.addWidget(result)

    def _build_structural(self) -> None:
        box = QGroupBox("2. SET e estrutura")
        layout = QFormLayout(box)
        self.set_type = QComboBox()
        self.set_type.addItem("Split — cada clone mantém seu próprio conjunto", "split")
        self.set_type.addItem("Non-Merged — clone incorpora o parent", "non_merged")
        self.set_type.addItem("Full-Merged — parent concentra os componentes", "full_merged")
        self.set_type.currentIndexChanged.connect(self._changed)
        layout.addRow("Tipo de SET:", self.set_type)
        self.clone_policy = QComboBox()
        self.clone_policy.addItem("Parents + clones", "with_clones")
        self.clone_policy.addItem("Somente parents", "parents_only")
        self.clone_policy.currentIndexChanged.connect(self._changed)
        layout.addRow("Seleção:", self.clone_policy)
        self.bios = QCheckBox("Incluir BIOS")
        self.devices = QCheckBox("Incluir Devices")
        self.chd = QCheckBox("Incluir CHDs")
        self.chd.setChecked(True)
        self.optional = QCheckBox("Incluir componentes opcionais")
        self.working = QCheckBox("Somente machines working")
        for widget in (self.bios, self.devices, self.chd, self.optional, self.working):
            widget.stateChanged.connect(self._changed)
            layout.addRow(widget)
        self.body_layout.addWidget(box)

    def _build_fundamental(self) -> None:
        box = QGroupBox("3. Conteúdo — exclusões rápidas")
        layout = QVBoxLayout(box)
        self.fundamental: dict[str, QCheckBox] = {}
        labels = {
            "mechanical": "Máquinas mecânicas / eletromecânicas",
            "dance": "Máquinas de dança",
            "console": "Consoles",
            "handheld": "Portáteis / Handhelds",
            "fruit_machines": "Fruit Machines / Gambling / Redemption",
            "quiz": "Quiz / Trivia",
            "tabletop": "Tabletop",
        }
        for key, text in labels.items():
            check = QCheckBox(text)
            check.stateChanged.connect(self._changed)
            self.fundamental[key] = check
            layout.addWidget(check)
        self.body_layout.addWidget(box)

    def _build_dynamic_sections(self) -> None:
        self._facet_widgets: dict[str, QListWidget] = {}
        sections = [
            ("content", "4. Tipo de conteúdo", False),
            ("playability", "5. Jogabilidade / estado de emulação", False),
            ("genre", "6. Gênero", False),
            ("hardware", "7. Hardware / plataforma", False),
            ("manufacturer", "8. Fabricante", True),
            ("series", "9. Série / família", True),
            ("input", "10. Controles", False),
            ("wheel", "11. Volante / rotação", False),
        ]
        for key, title, searchable in sections:
            box = QGroupBox(title)
            layout = QVBoxLayout(box)
            info = QLabel("Aguardando scan…")
            info.setObjectName(f"facetInfo_{key}")
            layout.addWidget(info)
            widget = QListWidget()
            widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
            widget.setMaximumHeight(150 if key not in {"manufacturer", "series"} else 190)
            widget.itemSelectionChanged.connect(self._changed)
            layout.addWidget(widget)
            self._facet_widgets[key] = widget
            self.body_layout.addWidget(box)

    def _refresh_scans(self) -> None:
        root = scans_root() / "mame"
        files = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if root.is_dir() else []
        self.scan_combo.blockSignals(True)
        self.scan_combo.clear()
        preferred = root / "MAME - 0.289_mame0289 - Arcade.json"
        if preferred.is_file():
            files = [preferred] + [path for path in files if path != preferred]
        for path in files:
            self.scan_combo.addItem(path.name, str(path))
        self.scan_combo.blockSignals(False)
        self._scan_changed()

    def _scan_changed(self, *_args) -> None:
        value = self.scan_combo.currentData()
        self._scan_path = Path(str(value)) if value else None
        self._facets_loaded = False
        if self._scan_path is None or not self._scan_path.is_file():
            self.scan_info.setText("Nenhum snapshot JSON válido.")
            self.apply.setEnabled(False)
            return
        self.scan_info.setText(f"{self._scan_path}\nCarregando opções reais do snapshot…")
        self.apply.setEnabled(False)
        self._start_worker("facets")

    def _start_worker(self, operation: str) -> None:
        if self._scan_path is None or not self._scan_path.is_file() or (self._worker and self._worker.isRunning()):
            return
        state = self._state()
        self._worker = _FilterWorker(operation, self._scan_path, state)
        self._worker.ready.connect(self._worker_ready)
        self._worker.failed.connect(self._worker_failed)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _worker_ready(self, payload) -> None:
        if self._worker and self._worker.operation == "facets":
            self._populate_facets(payload)
            self._facets_loaded = True
            self.apply.setEnabled(True)
            self.scan_info.setText(f"{self._scan_path}\nFacetas carregadas do snapshot. Selecione as dimensões desejadas; o preview será recalculado sem bloquear a interface.")
        elif self._worker and self._worker.operation == "preview":
            self.result.setText(self._format_result(payload, "Preview"))
        elif self._worker and self._worker.operation == "apply":
            self.result.setText(self._format_result(payload, "Filtro gerado") + f"\nArquivo: {payload.get('filtered_file_path', '—')}")
        self._worker = None

    def _worker_failed(self, message: str) -> None:
        self.result.setText(f"Operação indisponível: {message}")
        self._worker = None

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
            info = self.findChild(QLabel, f"facetInfo_{key}")
            if info:
                info.setText(f"{len(values):,} opções encontradas no scan. Ctrl/Cmd + clique para múltiplas seleções.")

    def _state(self) -> MameFilterState:
        state = MameFilterState(profile_id="mame-v2")
        state.mame_set_type = str(self.set_type.currentData())
        state.mame_clone_policy = str(self.clone_policy.currentData())
        state.mame_include_bios = self.bios.isChecked()
        state.mame_include_devices = self.devices.isChecked()
        state.mame_include_chd = self.chd.isChecked()
        state.mame_include_optional = self.optional.isChecked()
        state.mame_working_only = self.working.isChecked()
        state.fundamental = {key: widget.isChecked() for key, widget in self.fundamental.items()}
        for key, widget in self._facet_widgets.items():
            values = [str(item.data(Qt.ItemDataRole.UserRole)) for item in widget.selectedItems()]
            setattr(state, key, values)
        return state

    def _changed(self, *_args) -> None:
        if self._facets_loaded:
            self._preview_timer.start()

    def _start_preview(self) -> None:
        self._start_worker("preview")

    def _format_result(self, payload: dict, prefix: str) -> str:
        counts = payload.get("filter_counts") or {}
        stages = payload.get("stage_counts") or {}
        return (
            f"{prefix}: {int(payload.get('input_count', 0)):,} entradas → "
            f"{int(payload.get('output_count', 0)):,} permanecem → "
            f"{int(payload.get('filtered_count', 0)):,} excluídas.\n"
            f"Etapas: " + " | ".join(f"{key}={value:,}" for key, value in stages.items()) + "\n"
            f"Motivos principais: " + (" | ".join(f"{key}={value:,}" for key, value in counts.most_common(8)) if hasattr(counts, "most_common") else "calculados pelo motor V2")
        )

    def _save_profile(self) -> None:
        if self._scan_path is None:
            return
        path = data_root() / "mame_filter_profiles_v2.json"
        state = asdict(self._state())
        existing = []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                existing = [item for item in raw if isinstance(item, dict) and item.get("profile_id") != "mame-v2"]
        except (OSError, ValueError, TypeError):
            pass
        existing.append(state)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
        self.result.setText(f"Perfil V2 salvo em:\n{path}")

    def _apply(self) -> None:
        if self._scan_path is None or not self._facets_loaded:
            return
        self.apply.setEnabled(False)
        self._start_worker("apply")


__all__ = ["MameFiltersPanel", "MameFilterState"]
