"""Interface de filtros MAME V2 orientada a machines.

A interface separa explicitamente INCLUIR de EXCLUIR e nunca apresenta
contagens de ROM/CHD como resultado do filtro. O snapshot continua sendo a
fonte física, mas a unidade lógica do filtro é sempre a machine.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
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
        self.operation = operation
        self.path = path
        self.state = state

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
    """Editor MAME V2 com semântica explícita e layout compacto."""

    _FACETS = (
        ("content", "Tipo de conteúdo"),
        ("playability", "Jogabilidade"),
        ("genre", "Gênero"),
        ("hardware", "Hardware / plataforma"),
        ("manufacturer", "Fabricante"),
        ("series", "Série / família"),
        ("input", "Controles"),
        ("wheel", "Rotação do volante"),
    )

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
        "content": {
            item.value: item.value.replace("_", " ").title()
            for item in ArcadeContentType
        },
        "genre": {
            item.value: item.value.replace("_", " ").title()
            for item in ArcadeGenre
        },
        "hardware": {
            item.value: item.value.replace("_", " ").upper()
            for item in ArcadeHardwareFamily
        },
        "input": {
            item.value: item.value.replace("_", " ").title()
            for item in ArcadeInputType
        },
        "wheel": {
            item.value: f"{item.value}°"
            for item in WheelAngleClass
        },
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scan_path: Path | None = None
        self._worker: _FilterWorker | None = None
        self._facets_loaded = False
        self._pending_preview = False
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

        source = QGroupBox("SNAPSHOT DE ENTRADA")
        source.setMaximumHeight(68)
        form = QFormLayout(source)
        form.setContentsMargins(8, 5, 8, 5)
        form.setVerticalSpacing(3)
        row = QHBoxLayout()
        self.scan_combo = QComboBox()
        self.scan_combo.setMinimumHeight(28)
        self.scan_combo.currentIndexChanged.connect(self._scan_changed)
        row.addWidget(self.scan_combo, 1)
        refresh = QPushButton("ATUALIZAR")
        refresh.setMinimumHeight(28)
        refresh.clicked.connect(self.refresh)
        row.addWidget(refresh)
        form.addRow("Scan:", row)
        root.addWidget(source)

        self.summary = self._summary_bar()
        root.addWidget(self.summary)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._essential_tab(), "EXCLUSÕES")
        self.tabs.addTab(self._classification_tab(), "CLASSIFICAÇÃO")
        self.tabs.addTab(self._technical_tab(), "HARDWARE / CONTROLES")
        self.tabs.addTab(self._set_tab(), "SET")
        root.addWidget(self.tabs, 1)

        result = QGroupBox("RESULTADO DO FILTRO — MACHINES")
        result.setMaximumHeight(86)
        rv = QVBoxLayout(result)
        rv.setContentsMargins(8, 5, 8, 5)
        self.result = QLabel("Selecione um snapshot para iniciar.")
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

    @staticmethod
    def _summary_bar() -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        return widget

    def _set_summary(self, total: int, kept: int, excluded: int) -> None:
        layout = self.summary.layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        values = (
            ("MACHINES NO SNAPSHOT", total),
            ("MACHINES INCLUÍDAS", kept),
            ("MACHINES EXCLUÍDAS", excluded),
        )
        for label, value in values:
            box = QGroupBox(label)
            box.setMinimumHeight(48)
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(8, 4, 8, 4)
            text = QLabel(f"{value:,}")
            text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text.setProperty("role", "title")
            box_layout.addWidget(text)
            layout.addWidget(box, 1)

    def _essential_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        box = QGroupBox("EXCLUIR MACHINES POR CLASSIFICAÇÃO")
        grid = QGridLayout(box)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(7)
        self.fundamental: dict[str, QCheckBox] = {}
        labels = (
            ("mechanical", "Mecânicas / eletromecânicas"),
            ("dance", "Dança"),
            ("console", "Consoles"),
            ("handheld", "Portáteis / handhelds"),
            ("fruit_machines", "Fruit machines / gambling / redemption"),
            ("quiz", "Quiz / trivia"),
            ("tabletop", "Tabletop"),
        )
        for index, (key, label) in enumerate(labels):
            check = QCheckBox(label)
            check.stateChanged.connect(self._changed)
            self.fundamental[key] = check
            grid.addWidget(check, index // 3, index % 3)
        layout.addWidget(box)

        explanation = QGroupBox("SEMÂNTICA DOS FILTROS")
        ev = QVBoxLayout(explanation)
        ev.addWidget(QLabel("EXCLUSÕES: marque uma classe para RETIRAR machines."))
        ev.addWidget(QLabel("INCLUSÕES: selecione uma opção nas outras abas para MANTER somente machines que atendam a ela."))
        ev.addWidget(QLabel("Sem seleção de inclusão em uma dimensão = essa dimensão não restringe as machines."))
        layout.addWidget(explanation)
        layout.addStretch()
        return page

    def _classification_tab(self) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        for index, (key, title) in enumerate(self._FACETS[:3]):
            grid.addWidget(self._facet_box(key, f"INCLUIR • {title}"), 0, index)
            grid.setColumnStretch(index, 1)
        grid.setRowStretch(0, 1)
        return page

    def _technical_tab(self) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        for index, (key, title) in enumerate(self._FACETS[3:]):
            row, column = divmod(index, 3)
            grid.addWidget(self._facet_box(key, f"INCLUIR • {title}"), row, column)
        for column in range(3):
            grid.setColumnStretch(column, 1)
        for row in range(2):
            grid.setRowStretch(row, 1)
        return page

    def _facet_box(self, key: str, title: str) -> QGroupBox:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(4)
        info = QLabel("Carregando…")
        self._facet_info[key] = info
        layout.addWidget(info)
        widget = QListWidget()
        widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        widget.setMinimumHeight(110)
        widget.setMaximumHeight(220)
        widget.itemSelectionChanged.connect(self._changed)
        self._facet_widgets[key] = widget
        layout.addWidget(widget, 1)
        hint = QLabel("Selecionar = INCLUIR")
        layout.addWidget(hint)
        return box

    def _set_tab(self) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        structure = QGroupBox("ESTRUTURA DO SET")
        form = QFormLayout(structure)
        self.set_type = QComboBox()
        self.set_type.addItem("Split — cada clone separado", "split")
        self.set_type.addItem("Non-Merged — componentes incorporados", "non_merged")
        self.set_type.addItem("Full-Merged — parent concentra o conjunto", "full_merged")
        self.set_type.currentIndexChanged.connect(self._changed)
        form.addRow("Formato:", self.set_type)
        self.clone_policy = QComboBox()
        self.clone_policy.addItem("Parents + clones", "with_clones")
        self.clone_policy.addItem("Somente parents", "parents_only")
        self.clone_policy.currentIndexChanged.connect(self._changed)
        form.addRow("Machines:", self.clone_policy)

        components = QGroupBox("COMPONENTES DO CONJUNTO")
        cg = QGridLayout(components)
        self.bios = QCheckBox("Incluir BIOS")
        self.devices = QCheckBox("Incluir Devices")
        self.chd = QCheckBox("Incluir CHDs")
        self.chd.setChecked(True)
        self.optional = QCheckBox("Incluir componentes opcionais")
        self.working = QCheckBox("Somente machines working")
        checks = (self.bios, self.devices, self.chd, self.optional, self.working)
        for index, check in enumerate(checks):
            check.stateChanged.connect(self._changed)
            cg.addWidget(check, index // 2, index % 2)

        grid.addWidget(structure, 0, 0)
        grid.addWidget(components, 0, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(1, 1)
        return page

    def refresh(self) -> None:
        old = str(self.scan_combo.currentData() or "") if self.scan_combo.count() else ""
        root = scans_root() / "mame"
        files = (
            sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if root.is_dir()
            else []
        )
        preferred = root / "MAME - 0.289_mame0289 - Arcade.json"
        if preferred.is_file():
            files = [preferred] + [p for p in files if p != preferred]
        paths = [str(path) for path in files]
        self.scan_combo.blockSignals(True)
        self.scan_combo.clear()
        for path in files:
            self.scan_combo.addItem(path.name, str(path))
        if old in paths:
            self.scan_combo.setCurrentIndex(paths.index(old))
        elif files:
            self.scan_combo.setCurrentIndex(0)
        self.scan_combo.blockSignals(False)
        self._scan_changed()

    def _scan_changed(self, *_args) -> None:
        value = self.scan_combo.currentData()
        self._scan_path = Path(str(value)) if value else None
        self._facets_loaded = False
        self._pending_preview = False
        if self._scan_path is None or not self._scan_path.is_file():
            self.result.setText("Nenhum snapshot JSON válido em data/scans/mame.")
            self.apply.setEnabled(False)
            return
        self.result.setText("Lendo machines e descobrindo classificações…")
        self._start_worker("facets")

    def _start_worker(self, operation: str) -> None:
        if (
            self._scan_path is None
            or not self._scan_path.is_file()
            or (self._worker and self._worker.isRunning())
        ):
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
        if self._pending_preview and self._facets_loaded:
            self._pending_preview = False
            self._start_preview()

    def _worker_ready(self, operation: str, payload) -> None:
        if operation == "facets":
            self._populate_facets(payload)
            self._facets_loaded = True
            self.apply.setEnabled(True)
            total = sum(
                int(entry.get("count") or 0)
                for entry in payload.get("content", [])
            )
            self._set_summary(total, total, 0)
            self._pending_preview = True
            self.result.setText(
                f"{total:,} MACHINES carregadas. "
                "EXCLUSÕES estão na primeira aba; INCLUSÕES nas demais."
            )
        elif operation in {"preview", "apply"}:
            total = int(payload.get("input_count", 0))
            kept = int(payload.get("output_count", 0))
            excluded = int(payload.get("filtered_count", 0))
            self._set_summary(total, kept, excluded)
            self.result.setText(self._format_preview(payload))
            if operation == "apply":
                self.result.setText(
                    self._format_preview(payload)
                    + f"\nFILTER JSON: {payload.get('filtered_file_path', '—')}"
                )
                self.apply.setEnabled(True)

    def _worker_failed(self, message: str) -> None:
        self.result.setText(f"Falha no filtro MAME V2: {message}")
        self.apply.setEnabled(bool(self._facets_loaded))

    def _populate_facets(self, facets: dict[str, list[dict[str, object]]]) -> None:
        for key, widget in self._facet_widgets.items():
            widget.blockSignals(True)
            widget.clear()
            values = facets.get(key, [])
            for entry in values:
                value = str(entry.get("value"))
                count = int(entry.get("count") or 0)
                label = self._LABELS.get(key, {}).get(
                    value,
                    value.replace("_", " ").title(),
                )
                item = QListWidgetItem(f"{label}   [{count:,} machines]")
                item.setData(Qt.ItemDataRole.UserRole, value)
                widget.addItem(item)
            widget.blockSignals(False)
            self._facet_info[key].setText(
                f"{len(values):,} opções • contagem exclusivamente em MACHINES"
                if values
                else "Nenhuma classificação disponível no snapshot"
            )

    def _machine_count(self) -> int:
        if self._scan_path is None:
            return 0
        payload = MameFilterV2Service._payload(self._scan_path)
        return len(MameFilterV2Service._games(payload))

    def _state(self) -> MameFilterState:
        state = MameFilterState()
        state.mame_set_type = str(self.set_type.currentData())
        state.mame_clone_policy = str(self.clone_policy.currentData())
        state.mame_include_bios = self.bios.isChecked()
        state.mame_include_devices = self.devices.isChecked()
        state.mame_include_chd = self.chd.isChecked()
        state.mame_include_optional = self.optional.isChecked()
        state.mame_working_only = self.working.isChecked()
        state.fundamental = {
            key: check.isChecked()
            for key, check in self.fundamental.items()
        }
        for key, widget in self._facet_widgets.items():
            setattr(
                state,
                key,
                [
                    str(item.data(Qt.ItemDataRole.UserRole))
                    for item in widget.selectedItems()
                ],
            )
        return state

    def _changed(self, *_args) -> None:
        if self._facets_loaded:
            self._preview_timer.start()

    def _start_preview(self) -> None:
        if self._worker and self._worker.isRunning():
            self._pending_preview = True
            return
        self._start_worker("preview")

    @staticmethod
    def _format_preview(payload: dict) -> str:
        total = int(payload.get("input_count", 0))
        kept = int(payload.get("output_count", 0))
        excluded = int(payload.get("filtered_count", 0))
        reasons = payload.get("filter_counts") or {}
        reason_text = ", ".join(
            f"{key.replace('_', ' ')}: {value:,}"
            for key, value in list(reasons.items())[:6]
        ) or "nenhuma"
        return (
            f"MACHINES: {total:,} → {kept:,} incluídas → {excluded:,} excluídas. "
            f"Motivos das exclusões: {reason_text}."
        )

    def _save_profile(self) -> None:
        if self._scan_path is None:
            QMessageBox.warning(self, "Filtros MAME", "Selecione um snapshot primeiro.")
            return
        path = data_root() / "mame_filter_profiles_v2.json"
        state = asdict(self._state())
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            profiles = raw if isinstance(raw, list) else []
        except (OSError, ValueError, TypeError):
            profiles = []
        profiles = [
            item
            for item in profiles
            if not isinstance(item, dict)
            or item.get("profile_id") != state["profile_id"]
        ]
        profiles.append(state)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(profiles, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.result.setText(f"Perfil V2 salvo em: {path}")

    def _apply(self) -> None:
        if self._scan_path is None or not self._facets_loaded:
            return
        self.apply.setEnabled(False)
        self._start_worker("apply")


__all__ = ["MameFiltersPanel", "MameFilterState"]
