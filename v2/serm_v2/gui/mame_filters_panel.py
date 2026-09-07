"""Interface de filtros MAME V2 inspirada no fluxo de busca do Arcade Italia.

A interface usa a mesma ideia de pesquisa rápida + filtros adicionais em abas,
mas mantém a execução local do SERM e a unidade lógica de filtragem como machine.
"""

from __future__ import annotations

import json
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models.arcade import PlayabilityStatus
from ..models.arcade_classification import (
    ArcadeContentType,
    ArcadeGenre,
    ArcadeHardwareFamily,
    ArcadeInputType,
    WheelAngleClass,
)
from ..runtime.paths import data_root, scans_root
from ..services.arcade.mame_filter_v2_service import MameFilterV2Service
from ..services.mame_category_filter_service import MameCategoryFilterService


@dataclass(slots=True)
class MameFilterState:
    profile_id: str = "mame-v2"
    name: str = "MAME Arcade"
    title_query: str = ""
    full_text: str = ""
    rom_query: str = ""
    parent_query: str = ""
    clone_query: str = ""
    year_from: int | None = None
    year_to: int | None = None
    type_filter: str = "all"
    video_query: str = ""
    audio_query: str = ""
    screen_query: str = ""
    orientation: str = "all"
    cabinet_query: str = ""
    channels_query: str = ""
    mamecab_only: bool = True
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


class MameAdvancedFiltersDialog(QDialog):
    """Editor avançado em abas, inspirado na busca detalhada do Arcade Italia."""

    _LABELS = {
        "playability": {
            "fully_playable": "Totalmente jogável", "functional": "Funcional",
            "partially_playable": "Parcialmente jogável", "in_development": "Em desenvolvimento",
            "playable_elsewhere": "Jogável em outro alvo", "unplayable": "Não jogável",
            "unknown": "Não classificado",
        },
        "content": {x.value: x.value.replace("_", " ").title() for x in ArcadeContentType},
        "genre": {x.value: x.value.replace("_", " ").title() for x in ArcadeGenre},
        "hardware": {x.value: x.value.replace("_", " ").upper() for x in ArcadeHardwareFamily},
        "input": {x.value: x.value.replace("_", " ").title() for x in ArcadeInputType},
        "wheel": {x.value: f"{x.value}°" for x in WheelAngleClass},
    }

    def __init__(self, parent: "MameFiltersPanel") -> None:
        super().__init__(parent)
        self.panel = parent
        self.setWindowTitle("Filtros avançados — MAME")
        self.setModal(True)
        self.setMinimumSize(820, 600)
        self.resize(980, 720)
        self._lists: dict[str, QListWidget] = {}
        self._category_tree: QTreeWidget | None = None
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        title = QLabel("FILTROS ADICIONAIS — MAME")
        title.setProperty("role", "title")
        outer.addWidget(title)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.addTab(self._general_tab(), "Geral")
        tabs.addTab(self._driver_tab(), "Driver")
        tabs.addTab(self._input_tab(), "Input")
        tabs.addTab(self._video_tab(), "Vídeo")
        tabs.addTab(self._audio_tab(), "Áudio")
        tabs.addTab(self._categories_tab(), "Categorias")
        tabs.addTab(self._extra_tab(), "Extra")
        tabs.addTab(self._other_tab(), "Outro")
        outer.addWidget(tabs, 1)

        hint = QLabel("Seleções múltiplas são OR dentro da dimensão e AND entre dimensões.")
        hint.setWordWrap(True)
        outer.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    @staticmethod
    def _field(label: str, placeholder: str = "") -> tuple[QLabel, QLineEdit]:
        widget = QLineEdit()
        widget.setPlaceholderText(placeholder)
        return QLabel(label), widget

    def _general_tab(self) -> QWidget:
        page = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        form = QFormLayout(body)
        form.setContentsMargins(12, 12, 12, 12)
        form.setVerticalSpacing(8)

        self.title = QLineEdit(); self.title.setPlaceholderText("Romset name ou título do jogo")
        self.rom = QLineEdit(); self.rom.setPlaceholderText("Nome da ROM / arquivo")
        self.parent_query = QLineEdit(); self.parent_query.setPlaceholderText("Nome do parent")
        self.clone_query = QLineEdit(); self.clone_query.setPlaceholderText("Nome do clone")
        self.full_text = QLineEdit(); self.full_text.setPlaceholderText("Pesquisa no metadata do MAME")
        for label, widget in (("Título / ROM:", self.title), ("ROM:", self.rom), ("Parent:", self.parent_query), ("Clone:", self.clone_query), ("Texto completo:", self.full_text)):
            form.addRow(label, widget)

        years = QHBoxLayout()
        self.year_from = QSpinBox(); self.year_from.setRange(0, 2100); self.year_from.setSpecialValueText("—"); self.year_from.setValue(0)
        self.year_to = QSpinBox(); self.year_to.setRange(0, 2100); self.year_to.setSpecialValueText("—"); self.year_to.setValue(0)
        years.addWidget(QLabel("De")); years.addWidget(self.year_from); years.addWidget(QLabel("até")); years.addWidget(self.year_to); years.addStretch()
        form.addRow("Ano:", years)

        self.type_all = QRadioButton("Todos"); self.type_parent = QRadioButton("Parent"); self.type_clone = QRadioButton("Clone"); self.type_all.setChecked(True)
        types = QHBoxLayout(); types.addWidget(self.type_all); types.addWidget(self.type_parent); types.addWidget(self.type_clone); types.addStretch()
        form.addRow("Tipo:", types)

        self.emulation = QComboBox(); self.emulation.addItem("Todos", "")
        for value, label in self._LABELS["playability"].items(): self.emulation.addItem(label, value)
        form.addRow("Emulação:", self.emulation)

        self.manufacturer = QListWidget(); self.manufacturer.setSelectionMode(QListWidget.SelectionMode.MultiSelection); self.manufacturer.setMinimumHeight(130)
        self._lists["manufacturer"] = self.manufacturer
        form.addRow("Fabricante:", self.manufacturer)
        scroll.setWidget(body)
        layout = QVBoxLayout(page); layout.setContentsMargins(0, 0, 0, 0); layout.addWidget(scroll)
        return page

    def _list_tab(self, key: str, title: str, values_hint: str) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(10, 10, 10, 10)
        box = QGroupBox(title); box_layout = QVBoxLayout(box)
        info = QLabel(values_hint); info.setWordWrap(True); box_layout.addWidget(info)
        widget = QListWidget(); widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection); widget.setMinimumHeight(240)
        self._lists[key] = widget; box_layout.addWidget(widget, 1)
        layout.addWidget(box, 1); return page

    def _driver_tab(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(10, 10, 10, 10)
        for key, title, hint in (("content", "Tipo de conteúdo", "Arcade, console, handheld, mecânico, gambling etc."), ("hardware", "Hardware / plataforma", "Famílias de hardware descobertas pelo SERM.")):
            box = QGroupBox(title); box_layout = QVBoxLayout(box); box_layout.addWidget(QLabel(hint)); w = QListWidget(); w.setSelectionMode(QListWidget.SelectionMode.MultiSelection); self._lists[key] = w; box_layout.addWidget(w, 1); layout.addWidget(box, 1)
        return page

    def _input_tab(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(10, 10, 10, 10)
        for key, title in (("input", "Controles"), ("wheel", "Rotação do volante")):
            box = QGroupBox(title); box_layout = QVBoxLayout(box); w = QListWidget(); w.setSelectionMode(QListWidget.SelectionMode.MultiSelection); self._lists[key] = w; box_layout.addWidget(w, 1); layout.addWidget(box, 1)
        return page

    def _video_tab(self) -> QWidget:
        page = QWidget(); form = QFormLayout(page); form.setContentsMargins(14, 14, 14, 14)
        self.video_query = QLineEdit(); self.video_query.setPlaceholderText("driver, vídeo, resolução, chipset…")
        self.screen_query = QLineEdit(); self.screen_query.setPlaceholderText("tipo/tamanho de tela")
        self.orientation = QComboBox(); self.orientation.addItems(["Todos", "Horizontal", "Vertical"])
        self.cabinet = QLineEdit(); self.cabinet.setPlaceholderText("cabinet / gabinete")
        form.addRow("Vídeo:", self.video_query); form.addRow("Tela:", self.screen_query); form.addRow("Orientação:", self.orientation); form.addRow("Cabinet:", self.cabinet)
        note = QLabel("Os campos textuais consultam o metadata efetivamente presente no snapshot; não são preenchidos com dados inventados.")
        note.setWordWrap(True); form.addRow(note); return page

    def _audio_tab(self) -> QWidget:
        page = QWidget(); form = QFormLayout(page); form.setContentsMargins(14, 14, 14, 14)
        self.audio_query = QLineEdit(); self.audio_query.setPlaceholderText("chip / driver de áudio")
        self.channels = QLineEdit(); self.channels.setPlaceholderText("canais")
        form.addRow("Audio chip:", self.audio_query); form.addRow("Canais:", self.channels); return page

    def _categories_tab(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(QLabel("CATLIST do SERM — selecione categorias e subcategorias para INCLUIR somente essas machines."))
        self._category_tree = QTreeWidget(); self._category_tree.setHeaderLabels(["Categoria / subcategoria", "Machines"]); self._category_tree.setColumnWidth(0, 460)
        layout.addWidget(self._category_tree, 1); return page

    def _extra_tab(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(10, 10, 10, 10)
        box = QGroupBox("Classificações adicionais"); grid = QGridLayout(box)
        for key, title in (("genre", "Gênero"), ("series", "Série / família")):
            sub = QGroupBox(title); v = QVBoxLayout(sub); w = QListWidget(); w.setSelectionMode(QListWidget.SelectionMode.MultiSelection); self._lists[key] = w; v.addWidget(w); grid.addWidget(sub, 0, len(self._lists) % 2)
        layout.addWidget(box, 1)
        self.working = QCheckBox("Somente machines working")
        layout.addWidget(self.working); return page

    def _other_tab(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(10, 10, 10, 10)
        structure = QGroupBox("SET / estrutura"); form = QFormLayout(structure)
        self.set_type = QComboBox(); self.set_type.addItem("Split — cada clone separado", "split"); self.set_type.addItem("Non-Merged — componentes incorporados", "non_merged"); self.set_type.addItem("Full-Merged — parent concentra o conjunto", "full_merged")
        self.clone_policy = QComboBox(); self.clone_policy.addItem("Parents + clones", "with_clones"); self.clone_policy.addItem("Somente parents", "parents_only")
        form.addRow("Formato:", self.set_type); form.addRow("Machines:", self.clone_policy)
        layout.addWidget(structure)
        components = QGroupBox("Componentes"); grid = QGridLayout(components)
        self.bios = QCheckBox("Incluir BIOS"); self.devices = QCheckBox("Incluir Devices"); self.chd = QCheckBox("Incluir CHDs"); self.optional = QCheckBox("Incluir opcionais"); self.working_other = QCheckBox("Working only")
        self.chd.setChecked(True)
        for i, w in enumerate((self.bios, self.devices, self.chd, self.optional, self.working_other)): grid.addWidget(w, i // 2, i % 2)
        layout.addWidget(components)
        exclusion = QGroupBox("Exclusões fundamentais"); eg = QGridLayout(exclusion)
        self.fundamental: dict[str, QCheckBox] = {}
        for i, (key, label) in enumerate((("mechanical", "Mecânicas / eletromecânicas"), ("dance", "Dança"), ("console", "Consoles"), ("handheld", "Handhelds"), ("fruit_machines", "Fruit / gambling / redemption"), ("quiz", "Quiz / trivia"), ("tabletop", "Tabletop"))):
            w = QCheckBox(label); self.fundamental[key] = w; eg.addWidget(w, i // 2, i % 2)
        layout.addWidget(exclusion); layout.addStretch(); return page

    def set_facets(self, facets: dict[str, list[dict[str, object]]]) -> None:
        for key, widget in self._lists.items():
            widget.clear()
            for entry in facets.get(key, []):
                value = str(entry.get("value")); count = int(entry.get("count") or 0)
                label = self._LABELS.get(key, {}).get(value, value.replace("_", " ").title())
                item = QListWidgetItem(f"{label}   [{count:,} machines]")
                item.setData(Qt.ItemDataRole.UserRole, value); widget.addItem(item)

    def set_categories(self, rows: list[dict[str, object]]) -> None:
        if self._category_tree is None: return
        self._category_tree.clear(); parents: dict[str, QTreeWidgetItem] = {}
        for row in rows:
            category = str(row.get("category") or "[Sem categoria]"); subcategory = str(row.get("subcategory") or ""); count = int(row.get("machines") or 0)
            parent = parents.get(category)
            if parent is None:
                parent = QTreeWidgetItem([category, ""]); parent.setFlags(parent.flags() | Qt.ItemFlag.ItemIsUserCheckable); parent.setCheckState(0, Qt.CheckState.Unchecked); parents[category] = parent; self._category_tree.addTopLevelItem(parent)
            if subcategory:
                child = QTreeWidgetItem([subcategory, str(count)]); child.setData(0, Qt.ItemDataRole.UserRole, category); child.setData(0, Qt.ItemDataRole.UserRole + 1, subcategory); child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable); child.setCheckState(0, Qt.CheckState.Unchecked); parent.addChild(child)
            else:
                parent.setText(1, str(count))

    @staticmethod
    def _selected(widget: QListWidget) -> list[str]:
        return [str(item.data(Qt.ItemDataRole.UserRole)) for item in widget.selectedItems()]

    def values(self) -> dict[str, object]:
        if self.type_parent.isChecked(): type_filter = "parent"
        elif self.type_clone.isChecked(): type_filter = "clone"
        else: type_filter = "all"
        categories: list[str] = []; subcategories: list[str] = []
        if self._category_tree is not None:
            for i in range(self._category_tree.topLevelItemCount()):
                parent = self._category_tree.topLevelItem(i)
                if parent.checkState(0) == Qt.CheckState.Checked: categories.append(parent.text(0))
                for j in range(parent.childCount()):
                    child = parent.child(j)
                    if child.checkState(0) == Qt.CheckState.Checked: subcategories.append(child.text(0))
        year_from = self.year_from.value() or None; year_to = self.year_to.value() or None
        return {
            "title_query": self.title.text().strip(), "rom_query": self.rom.text().strip(), "parent_query": self.parent_query.text().strip(), "clone_query": self.clone_query.text().strip(), "full_text": self.full_text.text().strip(),
            "year_from": year_from, "year_to": year_to, "type_filter": type_filter, "video_query": self.video_query.text().strip(), "audio_query": self.audio_query.text().strip(), "screen_query": self.screen_query.text().strip(), "orientation": self.orientation.currentText().casefold(), "cabinet_query": self.cabinet.text().strip(), "channels_query": self.channels.text().strip(),
            "content": self._selected(self._lists["content"]), "hardware": self._selected(self._lists["hardware"]), "input": self._selected(self._lists["input"]), "wheel": self._selected(self._lists["wheel"]), "genre": self._selected(self._lists["genre"]), "series": self._selected(self._lists["series"]), "manufacturer": self._selected(self._lists["manufacturer"]),
            "playability": [self.emulation.currentData()] if self.emulation.currentData() else [], "categories": categories, "subcategories": subcategories,
            "mame_set_type": self.set_type.currentData(), "mame_clone_policy": self.clone_policy.currentData(), "mame_include_bios": self.bios.isChecked(), "mame_include_devices": self.devices.isChecked(), "mame_include_chd": self.chd.isChecked(), "mame_include_optional": self.optional.isChecked(), "mame_working_only": self.working.isChecked() or self.working_other.isChecked(),
            "fundamental": {key: widget.isChecked() for key, widget in self.fundamental.items()},
        }

    def apply_state(self, state: MameFilterState) -> None:
        self.title.setText(state.title_query); self.rom.setText(state.rom_query); self.parent_query.setText(state.parent_query); self.clone_query.setText(state.clone_query); self.full_text.setText(state.full_text)
        self.year_from.setValue(state.year_from or 0); self.year_to.setValue(state.year_to or 0)
        {"all": self.type_all, "parent": self.type_parent, "clone": self.type_clone}.get(state.type_filter, self.type_all).setChecked(True)
        self.video_query.setText(state.video_query); self.audio_query.setText(state.audio_query); self.screen_query.setText(state.screen_query); self.cabinet.setText(state.cabinet_query); self.channels.setText(state.channels_query)
        idx = self.orientation.findText(state.orientation.title()) if state.orientation != "all" else 0; self.orientation.setCurrentIndex(max(0, idx))
        for key, widget in self._lists.items():
            selected = set(getattr(state, key, []));
            for i in range(widget.count()): widget.item(i).setSelected(str(widget.item(i).data(Qt.ItemDataRole.UserRole)) in selected)
        self.emulation.setCurrentIndex(max(0, self.emulation.findData(state.playability[0] if state.playability else "")))
        self.set_type.setCurrentIndex(max(0, self.set_type.findData(state.mame_set_type))); self.clone_policy.setCurrentIndex(max(0, self.clone_policy.findData(state.mame_clone_policy)))
        self.bios.setChecked(state.mame_include_bios); self.devices.setChecked(state.mame_include_devices); self.chd.setChecked(state.mame_include_chd); self.optional.setChecked(state.mame_include_optional); self.working.setChecked(state.mame_working_only); self.working_other.setChecked(state.mame_working_only)
        for key, widget in self.fundamental.items(): widget.setChecked(bool(state.fundamental.get(key, False)))
        if self._category_tree is not None:
            cats, subs = set(state.categories), set(state.subcategories)
            for i in range(self._category_tree.topLevelItemCount()):
                parent = self._category_tree.topLevelItem(i); parent.setCheckState(0, Qt.CheckState.Checked if parent.text(0) in cats else Qt.CheckState.Unchecked)
                for j in range(parent.childCount()):
                    child = parent.child(j); child.setCheckState(0, Qt.CheckState.Checked if child.text(0) in subs else Qt.CheckState.Unchecked)


class MameFiltersPanel(QWidget):
    """Pesquisa MAME V2 compacta, responsiva e baseada em filtros adicionais."""

    _FACETS = (("content", "Tipo de conteúdo"), ("playability", "Jogabilidade"), ("genre", "Gênero"), ("hardware", "Hardware / plataforma"), ("manufacturer", "Fabricante"), ("series", "Série / família"), ("input", "Controles"), ("wheel", "Rotação do volante"))
    _RECENT_LIMIT = 10

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scan_path: Path | None = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="serm-mame-filter")
        self._future: Future | None = None; self._future_operation: str | None = None; self._future_generation = 0; self._generation = 0
        self._facets_loaded = False; self._pending_preview = False; self._restoring_state = False
        self._facets: dict[str, list[dict[str, object]]] = {}
        self._dialog: MameAdvancedFiltersDialog | None = None
        self._preview_timer = QTimer(self); self._preview_timer.setSingleShot(True); self._preview_timer.setInterval(180); self._preview_timer.timeout.connect(self._start_preview)
        self._poll_timer = QTimer(self); self._poll_timer.setInterval(60); self._poll_timer.timeout.connect(self._poll_future)
        self._build_ui(); self.refresh()

    @property
    def _last_state_path(self) -> Path: return data_root() / "mame_filter_last_state_v2.json"
    @property
    def _recent_profiles_path(self) -> Path: return data_root() / "mame_filter_recent_profiles_v2.json"

    def _build_ui(self) -> None:
        root = QVBoxLayout(self); root.setContentsMargins(8, 6, 8, 8); root.setSpacing(6)
        title = QLabel("MAME MACHINES  >  ARCADE"); title.setProperty("role", "title"); root.addWidget(title)

        search = QGroupBox("PESQUISA")
        grid = QGridLayout(search); grid.setContentsMargins(10, 8, 10, 8); grid.setHorizontalSpacing(8); grid.setVerticalSpacing(6)
        self.title_query = QLineEdit(); self.title_query.setPlaceholderText("Romset name ou título do jogo")
        self.year_quick = QComboBox(); self.year_quick.addItem("Todos os anos", None)
        self.genre_quick = QComboBox(); self.genre_quick.addItem("Todos os gêneros", "")
        self.mamecab = QCheckBox("MameCab only"); self.mamecab.setChecked(True)
        self.show_clones = QCheckBox("Mostrar clones"); self.show_clones.setChecked(True)
        self.latest = QCheckBox("Última release (0.289)"); self.latest.setChecked(True)
        self.full_text = QLineEdit(); self.full_text.setPlaceholderText("Full text search (mameinfo, history, etc.)")
        self.advanced_button = QPushButton("⚙ FILTROS ADICIONAIS")
        self.advanced_button.clicked.connect(self._open_advanced)
        self.clear_button = QPushButton("LIMPAR")
        self.clear_button.clicked.connect(self._clear_filters)
        self.title_query.returnPressed.connect(self._changed); self.full_text.returnPressed.connect(self._changed); self.genre_quick.currentIndexChanged.connect(self._quick_changed); self.year_quick.currentIndexChanged.connect(self._quick_changed); self.show_clones.stateChanged.connect(self._quick_changed); self.mamecab.stateChanged.connect(self._quick_changed)
        grid.addWidget(QLabel("Nome:"), 0, 0); grid.addWidget(self.title_query, 0, 1, 1, 3); grid.addWidget(QLabel("Ano:"), 0, 4); grid.addWidget(self.year_quick, 0, 5); grid.addWidget(QLabel("Gênero:"), 0, 6); grid.addWidget(self.genre_quick, 0, 7)
        grid.addWidget(self.mamecab, 1, 0); grid.addWidget(self.show_clones, 1, 1); grid.addWidget(self.latest, 1, 2); grid.addWidget(self.advanced_button, 1, 6); grid.addWidget(self.clear_button, 1, 7)
        grid.addWidget(QLabel("Texto completo:"), 2, 0); grid.addWidget(self.full_text, 2, 1, 1, 7)
        root.addWidget(search)

        self.active = QLabel("Filtros adicionais: nenhum"); self.active.setWordWrap(True); root.addWidget(self.active)
        self.summary = self._summary_bar(); root.addWidget(self.summary)

        result = QGroupBox("RESULTADO")
        rv = QVBoxLayout(result); rv.setContentsMargins(10, 7, 10, 7)
        self.result = QLabel("Selecione um snapshot para iniciar."); self.result.setWordWrap(True); rv.addWidget(self.result)
        actions = QHBoxLayout(); self.save = QPushButton("SALVAR PERFIL"); self.save.clicked.connect(self._save_profile); self.apply = QPushButton("APLICAR E GERAR FILTER JSON"); self.apply.clicked.connect(self._apply); self.apply.setEnabled(False); actions.addWidget(self.save); actions.addWidget(self.apply); actions.addStretch(); rv.addLayout(actions)
        root.addWidget(result)

    @staticmethod
    def _summary_bar() -> QWidget:
        widget = QWidget(); layout = QHBoxLayout(widget); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(6); return widget

    def _set_summary(self, total: int, kept: int, excluded: int) -> None:
        layout = self.summary.layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for label, value in (("MACHINES NO SNAPSHOT", total), ("INCLUÍDAS", kept), ("EXCLUÍDAS", excluded)):
            box = QGroupBox(label); box_layout = QVBoxLayout(box); box_layout.setContentsMargins(8, 4, 8, 4); text = QLabel(f"{value:,}"); text.setAlignment(Qt.AlignmentFlag.AlignCenter); text.setProperty("role", "title"); box_layout.addWidget(text); layout.addWidget(box, 1)

    def refresh(self) -> None:
        old = str(self._scan_path) if self._scan_path else ""; root = scans_root() / "mame"
        files = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if root.is_dir() else []
        preferred = root / "MAME - 0.289_mame0289 - Arcade.json"
        if preferred.is_file(): files = [preferred] + [p for p in files if p != preferred]
        if self._scan_path is None and files: self._scan_path = files[0]
        elif old:
            candidate = Path(old)
            if candidate.is_file(): self._scan_path = candidate
        self._scan_changed()

    def _scan_changed(self) -> None:
        self._generation += 1; self._facets_loaded = False; self._pending_preview = False
        if self._scan_path is None or not self._scan_path.is_file(): self.result.setText("Nenhum snapshot JSON válido em data/scans/mame."); self.apply.setEnabled(False); return
        self.result.setText("Carregando catálogo e descobrindo filtros…"); self._start_operation("facets")

    def _start_operation(self, operation: str) -> None:
        if self._scan_path is None or not self._scan_path.is_file() or (self._future is not None and not self._future.done()): return
        self._future_generation = self._generation; self._future_operation = operation; self._future = self._executor.submit(self._execute, operation, self._scan_path, self._state()); self._poll_timer.start()

    @staticmethod
    def _execute(operation: str, path: Path, state: MameFilterState):
        if operation == "facets": return MameFilterV2Service.facets(path)
        if operation == "preview": return MameFilterV2Service.preview(path, state)
        if operation == "apply": return MameFilterV2Service.apply(path, state)
        raise ValueError(f"Operação desconhecida: {operation}")

    def _poll_future(self) -> None:
        future = self._future
        if future is None or not future.done(): return
        self._poll_timer.stop(); operation = self._future_operation or ""; generation = self._future_generation; self._future = None; self._future_operation = None
        try: payload = future.result()
        except Exception as exc:
            if generation == self._generation: self._worker_failed(f"{type(exc).__name__}: {exc}")
        else:
            if generation == self._generation: self._worker_ready(operation, payload)
        if self._pending_preview and self._facets_loaded: self._pending_preview = False; self._start_preview()

    def _worker_ready(self, operation: str, payload) -> None:
        if operation == "facets":
            self._facets = payload; self._facets_loaded = True; self.apply.setEnabled(True)
            total = sum(int(x.get("count") or 0) for x in payload.get("content", [])); self._set_summary(total, total, 0); self._populate_quick_filters(payload); self._ensure_dialog(); self._dialog.set_facets(payload); self._dialog.set_categories(MameCategoryFilterService.tree()); self._restore_last_state(); self.result.setText(f"{total:,} MACHINES carregadas. Pesquisa rápida + filtros adicionais prontos."); self._pending_preview = True
        elif operation in {"preview", "apply"}:
            total = int(payload.get("input_count", 0)); kept = int(payload.get("output_count", 0)); excluded = int(payload.get("filtered_count", 0)); self._set_summary(total, kept, excluded); text = self._format_preview(payload); self.result.setText(text + (f"\nFILTER JSON: {payload.get('filtered_file_path', '—')}" if operation == "apply" else "")); self.apply.setEnabled(True)

    def _populate_quick_filters(self, facets: dict[str, list[dict[str, object]]]) -> None:
        self.genre_quick.blockSignals(True); self.genre_quick.clear(); self.genre_quick.addItem("Todos os gêneros", "")
        for entry in facets.get("genre", []): self.genre_quick.addItem(str(entry.get("value", "")).replace("_", " ").title(), str(entry.get("value", "")))
        self.genre_quick.blockSignals(False)
        self.year_quick.blockSignals(True); self.year_quick.clear(); self.year_quick.addItem("Todos os anos", None)
        years = sorted({str(entry.get("value")) for entry in facets.get("year", []) if str(entry.get("value", "")).isdigit()}, reverse=True)
        for year in years: self.year_quick.addItem(year, int(year))
        self.year_quick.blockSignals(False)

    def _ensure_dialog(self) -> None:
        if self._dialog is None: self._dialog = MameAdvancedFiltersDialog(self)

    def _open_advanced(self) -> None:
        if not self._facets_loaded: return
        self._ensure_dialog(); self._dialog.set_facets(self._facets); self._dialog.set_categories(MameCategoryFilterService.tree()); self._dialog.apply_state(self._state())
        if self._dialog.exec() == QDialog.DialogCode.Accepted:
            values = self._dialog.values(); self._apply_advanced_values(values); self._changed()

    def _apply_advanced_values(self, values: dict[str, object]) -> None:
        current = asdict(self._state()); current.update(values); self._apply_state(MameFilterState(**current))

    def _state(self) -> MameFilterState:
        state = MameFilterState()
        state.title_query = self.title_query.text().strip(); state.full_text = self.full_text.text().strip(); state.mamecab_only = self.mamecab.isChecked()
        if self._dialog is not None:
            values = self._dialog.values()
            for key, value in values.items():
                if key in MameFilterState.__dataclass_fields__: setattr(state, key, value)
        if self.genre_quick.currentData(): state.genre = [str(self.genre_quick.currentData())]
        if self.year_quick.currentData() is not None: state.year_from = int(self.year_quick.currentData()); state.year_to = int(self.year_quick.currentData())
        if not self.show_clones.isChecked(): state.type_filter = "parent"
        state.mamecab_only = self.mamecab.isChecked()
        return state

    def _apply_state(self, state: MameFilterState) -> None:
        self._restoring_state = True
        try:
            self.title_query.setText(state.title_query); self.full_text.setText(state.full_text); self.show_clones.setChecked(state.type_filter != "parent"); self.mamecab.setChecked(state.mamecab_only)
            self.genre_quick.blockSignals(True); self.year_quick.blockSignals(True)
            try:
                genre_value = state.genre[0] if state.genre else ""
                genre_index = self.genre_quick.findData(genre_value)
                self.genre_quick.setCurrentIndex(max(0, genre_index))
                if state.year_from is not None and state.year_to == state.year_from:
                    year_index = self.year_quick.findData(state.year_from)
                    self.year_quick.setCurrentIndex(max(0, year_index))
                else:
                    self.year_quick.setCurrentIndex(0)
            finally:
                self.genre_quick.blockSignals(False); self.year_quick.blockSignals(False)
            if self._dialog is not None: self._dialog.apply_state(state)
            self._update_active_summary(state)
        finally: self._restoring_state = False

    def _restore_last_state(self) -> None:
        try:
            payload = json.loads(self._last_state_path.read_text(encoding="utf-8")); raw_state = payload.get("state") if isinstance(payload, dict) else None
            saved_scan = str(payload.get("scan_path") or "") if isinstance(payload, dict) else ""
            if saved_scan and self._scan_path and Path(saved_scan).resolve() != self._scan_path.resolve(): return
            if isinstance(raw_state, dict):
                allowed = set(MameFilterState.__dataclass_fields__); state = MameFilterState(**{k: v for k, v in raw_state.items() if k in allowed}); self._apply_state(state); self.result.setText("Último filtro restaurado automaticamente.")
        except (OSError, ValueError, TypeError): return

    def _persist_last_state(self) -> None:
        if self._restoring_state or self._scan_path is None: return
        state = asdict(self._state()); payload = {"saved_at": datetime.now(timezone.utc).isoformat(), "scan_path": str(self._scan_path.resolve()), "state": state}
        self._last_state_path.parent.mkdir(parents=True, exist_ok=True); self._last_state_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"); self._persist_recent_profile(payload)

    def _persist_recent_profile(self, payload: dict) -> None:
        try: raw = json.loads(self._recent_profiles_path.read_text(encoding="utf-8")); profiles = raw if isinstance(raw, list) else []
        except (OSError, ValueError, TypeError): profiles = []
        signature = json.dumps(payload.get("state", {}), sort_keys=True, ensure_ascii=False); profiles = [p for p in profiles if isinstance(p, dict) and json.dumps(p.get("state", {}), sort_keys=True, ensure_ascii=False) != signature]; profiles.insert(0, payload); self._recent_profiles_path.parent.mkdir(parents=True, exist_ok=True); self._recent_profiles_path.write_text(json.dumps(profiles[:self._RECENT_LIMIT], indent=2, ensure_ascii=False), encoding="utf-8")

    def _quick_changed(self, *_args) -> None:
        if self._restoring_state or not self._facets_loaded: return
        self._changed()

    def _changed(self, *_args) -> None:
        if self._restoring_state or not self._facets_loaded: return
        self._persist_last_state(); self._update_active_summary(self._state()); self._preview_timer.start()

    def _update_active_summary(self, state: MameFilterState) -> None:
        parts: list[str] = []
        if state.title_query: parts.append(f'Título="{state.title_query}"')
        if state.full_text: parts.append(f'Texto="{state.full_text}"')
        if state.year_from: parts.append(f"Ano={state.year_from}" if state.year_from == state.year_to else f"Ano={state.year_from}-{state.year_to}")
        if state.genre: parts.append("Gênero=" + ", ".join(state.genre))
        if state.content: parts.append("Conteúdo=" + ", ".join(state.content))
        if state.manufacturer: parts.append("Fabricante=" + ", ".join(state.manufacturer[:3]))
        if state.categories or state.subcategories: parts.append(f"CATLIST={len(state.categories) + len(state.subcategories)} selecionada(s)")
        if state.type_filter != "all": parts.append("Parents only" if state.type_filter == "parent" else "Clones only")
        if state.mame_set_type != "split": parts.append(state.mame_set_type)
        if state.mame_working_only: parts.append("Working")
        if not state.mamecab_only: parts.append("MameCab OFF")
        self.active.setText("Filtros ativos: " + (" • ".join(parts) if parts else "nenhum"))

    def _clear_filters(self) -> None:
        state = MameFilterState(); self._apply_state(state); self.genre_quick.setCurrentIndex(0); self.year_quick.setCurrentIndex(0); self._changed()

    def _start_preview(self) -> None:
        if self._future is not None and not self._future.done(): self._pending_preview = True; return
        self._start_operation("preview")

    @staticmethod
    def _format_preview(payload: dict) -> str:
        total = int(payload.get("input_count", 0)); kept = int(payload.get("output_count", 0)); excluded = int(payload.get("filtered_count", 0)); reasons = payload.get("filter_counts") or {}; reason_text = ", ".join(f"{str(k).replace('_', ' ')}: {int(v):,}" for k, v in list(reasons.items())[:6]) or "nenhuma"; return f"MACHINES: {total:,} → {kept:,} incluídas → {excluded:,} excluídas. Motivos: {reason_text}."

    def _save_profile(self) -> None:
        if self._scan_path is None: QMessageBox.warning(self, "Filtros MAME", "Selecione um snapshot primeiro."); return
        self._persist_last_state(); path = data_root() / "mame_filter_profiles_v2.json"; state = asdict(self._state())
        try: raw = json.loads(path.read_text(encoding="utf-8")); profiles = raw if isinstance(raw, list) else []
        except (OSError, ValueError, TypeError): profiles = []
        profiles = [p for p in profiles if not isinstance(p, dict) or p.get("profile_id") != state["profile_id"]]; profiles.append(state); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(profiles, indent=2, ensure_ascii=False), encoding="utf-8"); self.result.setText("Perfil salvo e última configuração registrada automaticamente.")

    def _apply(self) -> None:
        if self._scan_path is None or not self._facets_loaded or (self._future is not None and not self._future.done()): return
        self._persist_last_state(); self.apply.setEnabled(False); self.result.setText("Aplicando filtros às machines e gerando FILTER JSON…"); self._start_operation("apply")

    def _worker_failed(self, message: str) -> None:
        self.result.setText(f"Falha no filtro MAME V2: {message}"); self.apply.setEnabled(self._facets_loaded)

    def closeEvent(self, event) -> None:
        self._preview_timer.stop(); self._poll_timer.stop(); self._persist_last_state()
        if self._future is not None and not self._future.done(): self._future.cancel()
        self._executor.shutdown(wait=True, cancel_futures=True); self._future = None
        if self._dialog is not None: self._dialog.close()
        super().closeEvent(event)


__all__ = ["MameFiltersPanel", "MameFilterState", "MameAdvancedFiltersDialog"]
