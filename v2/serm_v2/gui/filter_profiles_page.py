"""Filtros e scan do SERM V2."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QScrollArea, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..runtime.paths import data_root
from ..services.rom_scan_service import RomScanService, ScanResult
from ..services.scan_repository import ScanRepository


@dataclass(slots=True)
class FilterProfileData:
    source: str
    system: str
    dat_path: str | None = None
    profile_id: str = ""
    name: str = ""
    schema_version: int = 2
    created_at: str = ""
    updated_at: str = ""
    source_directories: list[str] = field(default_factory=list)
    recursive: bool = True
    games_only: bool = True
    include_bios: bool = False
    include_educational: bool = False
    include_manuals: bool = False
    include_magazines: bool = False
    include_software: bool = False
    include_demos: bool = False
    include_prototypes: bool = False
    include_unlicensed: bool = False
    one_game_one_region: bool = True
    region_priority: list[str] = field(default_factory=lambda: ["Brazil", "America", "Europe", "Japan", "World", "Restante"])
    remove_previous_versions: bool = True
    include_translations: bool = False
    translation_policy: str = "original_then_translation"
    include_chd: bool = True
    prefer_chd: bool = True
    allow_cue_bin: bool = True
    convert_cue_bin_to_chd: bool = True
    keep_cue_bin: bool = True
    whloader_games_only: bool = True
    mame_set_type: str = "split"
    mame_clone_policy: str = "with_clones"
    mame_include_bios: bool = False
    mame_include_devices: bool = False
    mame_include_chd: bool = True
    mame_include_optional: bool = True
    mame_working_only: bool = False
    mame_classification_source: str = "catlist"


class _ScanWorker(QThread):
    progress = Signal(int, int)
    log = Signal(str, str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, profile: FilterProfileData, database_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.profile = profile
        self.database_path = database_path
        self.service: RomScanService | None = None

    def run(self) -> None:
        try:
            self.service = RomScanService(log_callback=self.log.emit, progress_callback=self.progress.emit)
            result = self.service.scan(self.profile, database=self.database_path)
            ScanRepository(self.database_path).save(result)
            self.completed.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def cancel(self) -> None:
        if self.service is not None:
            self.service.cancel()


class FilterProfilesPage(QWidget):
    """Perfil de filtro/scan; o resultado segue para a reconstrução."""
    scan_requested = Signal(object)
    reconstruction_requested = Signal(object)
    REGION_DEFAULT = ("Brazil", "America", "Europe", "Japan", "World", "Restante")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._profiles_path = data_root() / "filter_profiles.json"
        self._selected_dat: Path | None = None
        self._current_saved_profile: FilterProfileData | None = None
        self._scan_worker: _ScanWorker | None = None
        self._last_scan_result: ScanResult | None = None
        self._building = False
        self._editor_splitter: QSplitter | None = None
        self._estimate_timer = QTimer(self)
        self._estimate_timer.setSingleShot(True)
        self._estimate_timer.setInterval(80)
        self._estimate_timer.timeout.connect(self._update_catalog_estimate)
        self._build_ui()
        self._connect_filter_estimate_signals()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("SERM V2 — Filtros e Scan")
        title.setProperty("role", "title")
        root.addWidget(title)
        intro = QLabel(
            "Selecione o catálogo, configure o perfil, salve e execute o scan. "
            "O mesmo profile_id acompanha o resultado até a reconstrução."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._catalog_panel())
        splitter.addWidget(self._editor_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

    def _catalog_panel(self) -> QWidget:
        box = QGroupBox("Catálogos")
        layout = QVBoxLayout(box)
        self.source_tree = QTreeWidget()
        self.source_tree.setHeaderLabels(["Fonte / sistema"])
        self.source_tree.setMinimumWidth(270)
        self.source_tree.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self.source_tree, 3)

        profiles_box = QGroupBox("Perfis salvos")
        profiles_layout = QVBoxLayout(profiles_box)
        self.profile_list = QListWidget()
        self.profile_list.currentItemChanged.connect(self._saved_profile_selected)
        profiles_layout.addWidget(self.profile_list, 1)
        profile_actions = QHBoxLayout()
        new_profile = QPushButton("NOVO PERFIL")
        delete_profile = QPushButton("EXCLUIR")
        new_profile.clicked.connect(self._new_profile)
        delete_profile.clicked.connect(self._delete_selected_profile)
        profile_actions.addWidget(new_profile)
        profile_actions.addWidget(delete_profile)
        profiles_layout.addLayout(profile_actions)
        layout.addWidget(profiles_box, 1)

        refresh = QPushButton("ATUALIZAR")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        return box

    def _editor_panel(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.selected_label = QLabel("Selecione um catálogo")
        layout.addWidget(self.selected_label)

        self._editor_splitter = QSplitter(Qt.Orientation.Vertical)
        source_box = self._source_box()
        lower = QWidget()
        lower_layout = QVBoxLayout(lower)
        lower_layout.setContentsMargins(0, 0, 0, 0)

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Nome do perfil:"))
        self.profile_name = QLineEdit()
        self.profile_name.setPlaceholderText("Ex.: MAME Arcade 1G1R")
        self.profile_name.editingFinished.connect(self._profile_name_changed)
        name_layout.addWidget(self.profile_name, 1)
        lower_layout.addLayout(name_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        self.filter_layout = QVBoxLayout(body)
        self._build_generic_controls()
        self._build_mame_controls()
        self.filter_layout.addStretch()
        scroll.setWidget(body)
        lower_layout.addWidget(scroll, 1)

        estimate_box = QGroupBox("Estimativa do catálogo — filtros em tempo real")
        estimate_layout = QVBoxLayout(estimate_box)
        self.catalog_estimate = QLabel("Selecione um catálogo para calcular.")
        self.catalog_estimate.setWordWrap(True)
        self.catalog_estimate.setProperty("role", "subtitle")
        estimate_layout.addWidget(self.catalog_estimate)
        self.catalog_estimate_detail = QLabel("Nenhuma consulta executada.")
        self.catalog_estimate_detail.setWordWrap(True)
        estimate_layout.addWidget(self.catalog_estimate_detail)
        lower_layout.addWidget(estimate_box)

        scan_box = QGroupBox("Execução do Scan")
        scan_layout = QVBoxLayout(scan_box)
        self.scan_progress = QLabel("Nenhum scan executado.")
        self.scan_progress.setWordWrap(True)
        scan_layout.addWidget(self.scan_progress)
        buttons = QHBoxLayout()
        self.save_button = QPushButton("SALVAR PERFIL")
        self.save_button.clicked.connect(self._save_profile)
        self.scan_button = QPushButton("SALVAR E INICIAR SCAN")
        self.scan_button.clicked.connect(self._save_and_scan)
        self.cancel_button = QPushButton("CANCELAR")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_scan)
        self.reconstruction_button = QPushButton("ABRIR RECONSTRUÇÃO")
        self.reconstruction_button.setEnabled(False)
        self.reconstruction_button.clicked.connect(self._open_reconstruction)
        for button in (self.save_button, self.scan_button, self.cancel_button, self.reconstruction_button):
            buttons.addWidget(button)
        buttons.addStretch()
        scan_layout.addLayout(buttons)
        self.log_view = QListWidget()
        self.log_view.setMinimumHeight(100)
        self.log_view.setMaximumHeight(180)
        scan_layout.addWidget(self.log_view)
        lower_layout.addWidget(scan_box)

        self._editor_splitter.addWidget(source_box)
        self._editor_splitter.addWidget(lower)
        self._editor_splitter.setStretchFactor(0, 0)
        self._editor_splitter.setStretchFactor(1, 1)
        self._editor_splitter.setSizes([145, 650])
        layout.addWidget(self._editor_splitter, 1)
        return page

    def _source_box(self) -> QGroupBox:
        source_box = QGroupBox("Fontes temporárias do scan — máximo 3")
        source_layout = QVBoxLayout(source_box)
        self.source_list = QListWidget()
        self.source_list.setMinimumHeight(55)
        self.source_list.setMaximumHeight(95)
        source_layout.addWidget(self.source_list)
        actions = QHBoxLayout()
        add = QPushButton("+ ADICIONAR")
        remove = QPushButton("REMOVER")
        add.clicked.connect(self._add_source_directory)
        remove.clicked.connect(self._remove_source_directory)
        actions.addWidget(add)
        actions.addWidget(remove)
        actions.addStretch()
        source_layout.addLayout(actions)
        self.recursive = QCheckBox("Incluir subdiretórios")
        self.recursive.setChecked(True)
        source_layout.addWidget(self.recursive)
        return source_box

    def _build_generic_controls(self) -> None:
        self.content_box = QGroupBox("Conteúdo")
        content = QFormLayout(self.content_box)
        self.games_only = QCheckBox("Somente Games")
        self.games_only.setChecked(True)
        content.addRow(self.games_only)
        self.content_checks: dict[str, QCheckBox] = {}
        for key, text in (("bios", "BIOS"), ("educational", "Educational"), ("manuals", "Manuais"),
                          ("magazines", "Revistas"), ("software", "Software / Applications"),
                          ("demos", "Demos"), ("prototypes", "Prototypes / Betas"), ("unlicensed", "Unlicensed")):
            check = QCheckBox(text)
            self.content_checks[key] = check
            content.addRow(check)
        self.filter_layout.addWidget(self.content_box)
        self.region_box = QGroupBox("Clones / 1G1R")
        region = QFormLayout(self.region_box)
        self.one_game_one_region = QCheckBox("Aplicar 1G1R — uma ROM por jogo/região")
        self.one_game_one_region.setChecked(True)
        region.addRow(self.one_game_one_region)
        self.region_list = QListWidget()
        self.region_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.region_list.setMaximumHeight(120)
        region.addRow("Prioridade regional:", self.region_list)
        self.filter_layout.addWidget(self.region_box)
        self.version_box = QGroupBox("Versões / revisões")
        version = QFormLayout(self.version_box)
        self.remove_previous = QCheckBox("Remover versões/revisões anteriores")
        self.remove_previous.setChecked(True)
        version.addRow(self.remove_previous)
        self.filter_layout.addWidget(self.version_box)
        self.translation_box = QGroupBox("Traduções / DE-PARA")
        trans = QFormLayout(self.translation_box)
        self.include_translations = QCheckBox("Permitir traduções catalogadas / DE-PARA")
        trans.addRow(self.include_translations)
        self.translation_policy = QComboBox()
        self.translation_policy.addItem("Original primeiro; tradução somente se necessário", "original_then_translation")
        self.translation_policy.addItem("Priorizar tradução", "translation_first")
        self.translation_policy.addItem("Somente tradução", "translation_only")
        trans.addRow("Política:", self.translation_policy)
        self.filter_layout.addWidget(self.translation_box)
        self.redump_box = QGroupBox("Redump — mídia óptica")
        redump = QFormLayout(self.redump_box)
        self.include_chd = QCheckBox("Aceitar CHD")
        self.include_chd.setChecked(True)
        self.prefer_chd = QCheckBox("Priorizar CHD")
        self.prefer_chd.setChecked(True)
        self.allow_cue_bin = QCheckBox("CUE/BIN como fallback")
        self.allow_cue_bin.setChecked(True)
        self.convert_cue_bin = QCheckBox("Converter CUE/BIN para CHD via chdman.exe")
        self.convert_cue_bin.setChecked(True)
        self.keep_cue_bin = QCheckBox("Manter CUE/BIN original")
        self.keep_cue_bin.setChecked(True)
        for widget in (self.include_chd, self.prefer_chd, self.allow_cue_bin, self.convert_cue_bin, self.keep_cue_bin):
            redump.addRow(widget)
        self.filter_layout.addWidget(self.redump_box)
        self.wh_box = QGroupBox("WHLoader")
        wh = QFormLayout(self.wh_box)
        self.wh_games_only = QCheckBox("Somente Games (.lha)")
        self.wh_games_only.setChecked(True)
        wh.addRow(self.wh_games_only)
        self.filter_layout.addWidget(self.wh_box)

    def _build_mame_controls(self) -> None:
        self.mame_box = QGroupBox("MAME — filtro específico baseado na V1")
        layout = QFormLayout(self.mame_box)
        self.mame_set_type = QComboBox()
        self.mame_set_type.addItem("Split — padrão", "split")
        self.mame_set_type.addItem("Non-Merged", "non_merged")
        self.mame_set_type.addItem("Full-Merged", "full_merged")
        layout.addRow("Tipo de SET:", self.mame_set_type)
        self.mame_clone_policy = QComboBox()
        self.mame_clone_policy.addItem("Com clones", "with_clones")
        self.mame_clone_policy.addItem("Somente parents", "parents_only")
        layout.addRow("Clones:", self.mame_clone_policy)
        self.mame_bios = QCheckBox("Incluir BIOS / sets de BIOS")
        self.mame_devices = QCheckBox("Incluir Devices")
        self.mame_chd = QCheckBox("Incluir CHDs / disks")
        self.mame_chd.setChecked(True)
        self.mame_optional = QCheckBox("Incluir ROMs opcionais")
        self.mame_optional.setChecked(True)
        self.mame_working = QCheckBox("Somente máquinas marcadas como working")
        for widget in (self.mame_bios, self.mame_devices, self.mame_chd, self.mame_optional, self.mame_working):
            layout.addRow(widget)
        self.mame_classification = QComboBox()
        self.mame_classification.addItem("catlist.ini — prioridade", "catlist")
        self.mame_classification.addItem("ListXML — fallback", "listxml")
        layout.addRow("Classificação:", self.mame_classification)
        self.filter_layout.addWidget(self.mame_box)

    def _connect_filter_estimate_signals(self) -> None:
        widgets = [self.games_only, self.recursive, self.one_game_one_region, self.remove_previous,
                    self.include_translations, self.include_chd, self.prefer_chd, self.allow_cue_bin,
                    self.convert_cue_bin, self.keep_cue_bin, self.wh_games_only, self.mame_bios,
                    self.mame_devices, self.mame_chd, self.mame_optional, self.mame_working]
        widgets.extend(self.content_checks.values())
        for widget in widgets:
            widget.toggled.connect(self._schedule_catalog_estimate)
        for combo in (self.translation_policy, self.mame_set_type, self.mame_clone_policy, self.mame_classification):
            combo.currentIndexChanged.connect(self._schedule_catalog_estimate)
        self.region_list.model().rowsMoved.connect(self._schedule_catalog_estimate)
        self.region_list.model().rowsInserted.connect(self._schedule_catalog_estimate)
        self.region_list.model().rowsRemoved.connect(self._schedule_catalog_estimate)

    def _schedule_catalog_estimate(self, *_args) -> None:
        if self._building:
            return
        self._estimate_timer.start()

    def _update_catalog_estimate(self) -> None:
        selected = self._selected_item_data()
        if selected is None:
            self.catalog_estimate.setText("Selecione um catálogo para calcular.")
            self.catalog_estimate_detail.setText("Nenhuma consulta executada.")
            return
        source, system, dat_path = selected
        if source != "MAME":
            if dat_path and Path(dat_path).is_file():
                try:
                    raw = Path(dat_path).read_text(encoding="utf-8", errors="ignore")
                    games = raw.lower().count("<game ")
                    self.catalog_estimate.setText(f"CATÁLOGO: {games:,} entradas")
                    self.catalog_estimate_detail.setText("Estimativa instantânea do DAT. Filtros específicos serão aplicados pelo scanner do sistema.")
                except OSError as exc:
                    self.catalog_estimate.setText("CATÁLOGO: indisponível")
                    self.catalog_estimate_detail.setText(f"Não foi possível ler o DAT: {exc}")
            else:
                self.catalog_estimate.setText("CATÁLOGO: aguardando DAT")
                self.catalog_estimate_detail.setText("Baixe/importе o catálogo para habilitar a estimativa.")
            return
        profile = self._current_profile()
        if profile is None:
            return
        estimate = RomScanService().estimate_mame(profile, database=self._database_path())
        error = estimate.get("error")
        if error:
            self.catalog_estimate.setText("CATÁLOGO MAME: indisponível")
            self.catalog_estimate_detail.setText(f"Erro ao calcular: {error}")
            return
        self.catalog_estimate.setText(f"ROMs selecionadas: {int(estimate['roms']):,}  •  máquinas: {int(estimate['machines']):,}")
        details = (
            f"Opcionais: {int(estimate['optional_roms']):,}  •  CHDs/disks: {int(estimate['disks']):,}  •  "
            f"SET: {estimate.get('set_type', 'split')}  •  catálogo total: {int(estimate['catalog_roms']):,} ROMs"
        )
        self.catalog_estimate_detail.setText(details)

    def _selected_item_data(self):
        item = self.source_tree.currentItem()
        if item is None:
            return None
        data = item.data(0, Qt.ItemDataRole.UserRole)
        return tuple(data) if isinstance(data, (tuple, list)) and len(data) == 3 else None

    def _selection_changed(self) -> None:
        selected = self._selected_item_data()
        if selected is None:
            return
        source, system, dat_path = selected
        self.selected_label.setText(f"{source} › {system}")
        self._selected_dat = Path(dat_path) if dat_path else None
        profile = self._load_saved_profile(source, system, dat_path)
        self._current_saved_profile = profile
        self._load_profile(profile or self._new_default_profile(source, system, dat_path))
        self._configure_source_controls(source)
        self._refresh_profile_list()
        if self._current_saved_profile:
            latest = ScanRepository(self._database_path()).latest_for_profile(self._current_saved_profile.profile_id)
            if latest:
                self.scan_progress.setText(
                    f"Último scan: {latest['scan_id']} | status={latest['status']} | "
                    f"arquivos={latest['files_examined']} | itens={latest['items_examined']}"
                )
        self._schedule_catalog_estimate()

    def _configure_source_controls(self, source: str) -> None:
        is_mame = source == "MAME"
        is_wh = source == "WHLoader"
        is_redump = source == "Redump"
        self.mame_box.setVisible(is_mame)
        self.region_box.setVisible(not is_mame and not is_wh)
        self.translation_box.setVisible(not is_mame and not is_wh)
        self.version_box.setVisible(not is_mame)
        self.redump_box.setVisible(is_redump)
        self.wh_box.setVisible(is_wh)
        self.content_box.setVisible(not is_mame)

    def _new_default_profile(self, source, system, dat_path):
        now = datetime.now(timezone.utc).isoformat()
        profile = FilterProfileData(source=source, system=system, dat_path=dat_path, profile_id=str(uuid4()), name=f"{source} — {system}", created_at=now, updated_at=now)
        if source == "MAME":
            profile.one_game_one_region = False
        if source == "WHLoader":
            profile.one_game_one_region = False
            profile.remove_previous_versions = False
        return profile

    def _load_profile(self, profile: FilterProfileData) -> None:
        self._building = True
        try:
            self.profile_name.setText(profile.name)
            self.source_list.clear()
            self.source_list.addItems(profile.source_directories[:3])
            self.recursive.setChecked(profile.recursive)
            self.games_only.setChecked(profile.games_only)
            for key, check in self.content_checks.items():
                check.setChecked(bool(getattr(profile, f"include_{key}")))
            self.one_game_one_region.setChecked(profile.one_game_one_region)
            self.region_list.clear()
            self.region_list.addItems(profile.region_priority or list(self.REGION_DEFAULT))
            self.remove_previous.setChecked(profile.remove_previous_versions)
            self.include_translations.setChecked(profile.include_translations)
            self.translation_policy.setCurrentIndex(max(0, self.translation_policy.findData(profile.translation_policy)))
            self.include_chd.setChecked(profile.include_chd)
            self.prefer_chd.setChecked(profile.prefer_chd)
            self.allow_cue_bin.setChecked(profile.allow_cue_bin)
            self.convert_cue_bin.setChecked(profile.convert_cue_bin_to_chd)
            self.keep_cue_bin.setChecked(profile.keep_cue_bin)
            self.wh_games_only.setChecked(profile.whloader_games_only)
            self.mame_set_type.setCurrentIndex(max(0, self.mame_set_type.findData(profile.mame_set_type)))
            self.mame_clone_policy.setCurrentIndex(max(0, self.mame_clone_policy.findData(profile.mame_clone_policy)))
            self.mame_bios.setChecked(profile.mame_include_bios)
            self.mame_devices.setChecked(profile.mame_include_devices)
            self.mame_chd.setChecked(profile.mame_include_chd)
            self.mame_optional.setChecked(profile.mame_include_optional)
            self.mame_working.setChecked(profile.mame_working_only)
            self.mame_classification.setCurrentIndex(max(0, self.mame_classification.findData(profile.mame_classification_source)))
            self.scan_progress.setText(f"Perfil: {profile.name} | ID={profile.profile_id}")
        finally:
            self._building = False

    @staticmethod
    def _from_dict(raw):
        try:
            profile = FilterProfileData(**{key: value for key, value in raw.items() if key in FilterProfileData.__dataclass_fields__})
        except (TypeError, ValueError):
            return None
        if not profile.profile_id:
            profile.profile_id = str(uuid4())
        if not profile.name:
            profile.name = f"{profile.source} — {profile.system}"
        if not profile.created_at:
            profile.created_at = profile.updated_at or datetime.now(timezone.utc).isoformat()
        if not profile.updated_at:
            profile.updated_at = profile.created_at
        return profile

    def _read_profiles(self):
        try:
            raw = json.loads(self._profiles_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return []
        return [profile for item in raw if isinstance(item, dict) and (profile := self._from_dict(item)) is not None] if isinstance(raw, list) else []

    def _write_profiles(self, profiles):
        self._profiles_path.parent.mkdir(parents=True, exist_ok=True)
        self._profiles_path.write_text(json.dumps([asdict(p) for p in profiles], indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_saved_profile(self, source, system, dat_path):
        return next((p for p in self._read_profiles() if p.source == source and p.system == system and p.dat_path == dat_path), None)

    def _refresh_profile_list(self, *_):
        profiles = self._read_profiles()
        self.profile_list.blockSignals(True)
        self.profile_list.clear()
        for profile in profiles:
            item = QListWidgetItem(f"{profile.name}\n{profile.source} › {profile.system}")
            item.setData(Qt.ItemDataRole.UserRole, profile.profile_id)
            item.setToolTip(f"ID={profile.profile_id}\nCriado={profile.created_at}\nAtualizado={profile.updated_at}")
            self.profile_list.addItem(item)
        self.profile_list.blockSignals(False)

    def _saved_profile_selected(self, current, _previous):
        if current is None:
            return
        profile_id = current.data(Qt.ItemDataRole.UserRole)
        profile = next((p for p in self._read_profiles() if p.profile_id == profile_id), None)
        if profile is None:
            return
        for i in range(self.source_tree.topLevelItemCount()):
            root = self.source_tree.topLevelItem(i)
            candidates = [root] + [root.child(n) for n in range(root.childCount())]
            for item in candidates:
                data = item.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(data, (tuple, list)) and tuple(data) == (profile.source, profile.system, profile.dat_path):
                    self.source_tree.setCurrentItem(item)
                    self._current_saved_profile = profile
                    self._load_profile(profile)
                    self._configure_source_controls(profile.source)
                    self._schedule_catalog_estimate()
                    return

    def _profile_name_changed(self) -> None:
        name = self.profile_name.text().strip()
        if name:
            self.scan_progress.setText(f"Nome do perfil: {name}")

    def _new_profile(self) -> None:
        selected = self._selected_item_data()
        if selected is None:
            QMessageBox.information(self, "Perfil", "Selecione um catálogo antes de criar um novo perfil.")
            return
        source, system, dat_path = selected
        self._current_saved_profile = None
        self._last_scan_result = None
        profile = self._new_default_profile(source, system, dat_path)
        profile.name = self._next_profile_name(source, system)
        self._load_profile(profile)
        self._configure_source_controls(source)
        self._schedule_catalog_estimate()

    def _next_profile_name(self, source: str, system: str) -> str:
        base = f"{source} — {system}"
        names = {profile.name.casefold() for profile in self._read_profiles()}
        if base.casefold() not in names:
            return base
        index = 2
        while f"{base} #{index}".casefold() in names:
            index += 1
        return f"{base} #{index}"

    def _delete_selected_profile(self) -> None:
        item = self.profile_list.currentItem()
        if item is None:
            QMessageBox.information(self, "Perfis", "Selecione um perfil para excluir.")
            return
        profile_id = item.data(Qt.ItemDataRole.UserRole)
        profiles = self._read_profiles()
        profile = next((p for p in profiles if p.profile_id == profile_id), None)
        if profile is None:
            self._refresh_profile_list()
            return
        answer = QMessageBox.question(
            self,
            "Excluir perfil",
            f"Excluir o perfil '{profile.name}'?\n\nO histórico de scans já gravados não será apagado.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        profiles = [p for p in profiles if p.profile_id != profile_id]
        self._write_profiles(profiles)
        if self._current_saved_profile and self._current_saved_profile.profile_id == profile_id:
            self._current_saved_profile = None
        self._refresh_profile_list()
        self.scan_progress.setText("Perfil excluído. O histórico de scans foi preservado.")

    def _current_profile(self):
        selected = self._selected_item_data()
        if selected is None:
            return None
        source, system, dat_path = selected
        previous = self._current_saved_profile
        now = datetime.now(timezone.utc).isoformat()
        name = self.profile_name.text().strip() or (previous.name if previous else self._next_profile_name(source, system))
        return FilterProfileData(
            source=source, system=system, dat_path=dat_path,
            profile_id=previous.profile_id if previous else str(uuid4()),
            name=name,
            created_at=previous.created_at if previous else now, updated_at=now,
            source_directories=[self.source_list.item(i).text() for i in range(self.source_list.count())],
            recursive=self.recursive.isChecked(), games_only=self.games_only.isChecked(),
            include_bios=self.content_checks["bios"].isChecked(), include_educational=self.content_checks["educational"].isChecked(),
            include_manuals=self.content_checks["manuals"].isChecked(), include_magazines=self.content_checks["magazines"].isChecked(),
            include_software=self.content_checks["software"].isChecked(), include_demos=self.content_checks["demos"].isChecked(),
            include_prototypes=self.content_checks["prototypes"].isChecked(), include_unlicensed=self.content_checks["unlicensed"].isChecked(),
            one_game_one_region=self.one_game_one_region.isChecked(),
            region_priority=[self.region_list.item(i).text() for i in range(self.region_list.count())],
            remove_previous_versions=self.remove_previous.isChecked(), include_translations=self.include_translations.isChecked(),
            translation_policy=str(self.translation_policy.currentData()), include_chd=self.include_chd.isChecked(),
            prefer_chd=self.prefer_chd.isChecked(), allow_cue_bin=self.allow_cue_bin.isChecked(),
            convert_cue_bin_to_chd=self.convert_cue_bin.isChecked(), keep_cue_bin=self.keep_cue_bin.isChecked(),
            whloader_games_only=self.wh_games_only.isChecked(), mame_set_type=str(self.mame_set_type.currentData()),
            mame_clone_policy=str(self.mame_clone_policy.currentData()), mame_include_bios=self.mame_bios.isChecked(),
            mame_include_devices=self.mame_devices.isChecked(), mame_include_chd=self.mame_chd.isChecked(),
            mame_include_optional=self.mame_optional.isChecked(), mame_working_only=self.mame_working.isChecked(),
            mame_classification_source=str(self.mame_classification.currentData()),
        )

    def _save_profile(self):
        profile = self._current_profile()
        if profile is None:
            QMessageBox.information(self, "Filtros", "Selecione um catálogo antes de salvar.")
            return None
        profiles = self._read_profiles()
        replaced = False
        for index, existing in enumerate(profiles):
            if existing.profile_id == profile.profile_id:
                profiles[index] = profile
                replaced = True
                break
        if not replaced:
            profiles.append(profile)
        self._write_profiles(profiles)
        self._current_saved_profile = profile
        self._refresh_profile_list()
        self.scan_progress.setText(f"Perfil salvo: {profile.name} | ID={profile.profile_id}")
        self.reconstruction_button.setEnabled(self._last_scan_result is not None)
        return profile

    def _save_and_scan(self):
        profile = self._save_profile()
        if profile is None:
            return
        self.scan_requested.emit(profile)
        self._start_scan(profile)

    def _start_scan(self, profile):
        if self._scan_worker is not None and self._scan_worker.isRunning():
            self._append_log("WARNING", "SCAN | já existe um scan em execução")
            return
        if not profile.source_directories:
            QMessageBox.information(self, "Scan", "Adicione ao menos um diretório de origem.")
            return
        self.log_view.clear()
        self.scan_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.reconstruction_button.setEnabled(False)
        self.scan_progress.setText(f"SCAN | iniciando | profile_id={profile.profile_id}")
        self._scan_worker = _ScanWorker(profile, self._database_path(), self)
        self._scan_worker.progress.connect(self._scan_progress)
        self._scan_worker.log.connect(self._append_log)
        self._scan_worker.completed.connect(self._scan_completed)
        self._scan_worker.failed.connect(self._scan_failed)
        self._scan_worker.finished.connect(self._scan_finished)
        self._scan_worker.start()

    def _scan_progress(self, current, total):
        self.scan_progress.setText(f"SCAN | progresso={current}/{total} | {current / total * 100:.1f}%" if total else f"SCAN | arquivos={current}")

    def _append_log(self, level, message):
        self.log_view.addItem(f"{level} | {message}")
        self.log_view.scrollToBottom()

    def _scan_completed(self, result):
        self._last_scan_result = result
        self.reconstruction_button.setEnabled(True)
        self.scan_progress.setText(f"SCAN | concluído | scan_id={result.scan_id} | duração={result.elapsed_seconds:.2f}s | arquivos={result.files_examined} | itens={result.items_examined}")
        self.reconstruction_requested.emit({"profile": self._current_saved_profile, "scan_result": result})

    def _scan_failed(self, message):
        self._append_log("ERROR", f"SCAN | falha final | {message}")
        self.scan_progress.setText("SCAN | falhou; consulte o log")

    def _scan_finished(self):
        self.scan_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self._scan_worker = None

    def _cancel_scan(self):
        if self._scan_worker is not None:
            self._scan_worker.cancel()
            self._append_log("WARNING", "SCAN | cancelamento solicitado")

    def _open_reconstruction(self):
        if self._current_saved_profile is not None:
            self.reconstruction_requested.emit({"profile": self._current_saved_profile, "scan_result": self._last_scan_result})

    def _database_path(self):
        return data_root() / "database" / "serm.db"

    def _reset_defaults(self):
        self._new_profile()

    def _add_source_directory(self):
        if self.source_list.count() >= 3:
            QMessageBox.information(self, "Fontes", "Máximo de 3 diretórios por perfil.")
            return
        directory = QFileDialog.getExistingDirectory(self, "Diretório de origem", str(Path.home()))
        if directory:
            self.source_list.addItem(str(Path(directory).resolve()))

    def _remove_source_directory(self):
        row = self.source_list.currentRow()
        if row >= 0:
            self.source_list.takeItem(row)

    def refresh(self):
        self.source_tree.clear()
        self._add_source_item("MAME", "MAME", None)
        self._add_dat_entries("No-Intro", data_root() / "sources" / "no_intro" / "dats")
        self._add_dat_entries("Redump", data_root() / "sources" / "redump" / "dats")
        self._add_source_item("WHLoader", "WHLoader", None)
        self._add_source_item("C64", "Commodore C64 - Games", None)
        self._refresh_profile_list()
        if self.source_tree.topLevelItemCount():
            self.source_tree.setCurrentItem(self.source_tree.topLevelItem(0))
        self._schedule_catalog_estimate()

    def _add_source_item(self, source, system, dat_path):
        parent = next((self.source_tree.topLevelItem(i) for i in range(self.source_tree.topLevelItemCount()) if self.source_tree.topLevelItem(i).text(0) == source), None)
        if parent is None:
            parent = QTreeWidgetItem([source])
            parent.setData(0, Qt.ItemDataRole.UserRole, (source, system, dat_path))
            self.source_tree.addTopLevelItem(parent)
        else:
            child = QTreeWidgetItem([system])
            child.setData(0, Qt.ItemDataRole.UserRole, (source, system, dat_path))
            parent.addChild(child)
            parent.setExpanded(True)

    def _add_dat_entries(self, source, directory):
        parent = QTreeWidgetItem([source])
        parent.setData(0, Qt.ItemDataRole.UserRole, (source, source, None))
        self.source_tree.addTopLevelItem(parent)
        paths = sorted(directory.glob("*.dat"), key=lambda p: p.name.casefold()) if directory.is_dir() else []
        if not paths:
            child = QTreeWidgetItem(["Nenhum DAT baixado"])
            child.setData(0, Qt.ItemDataRole.UserRole, (source, "Nenhum DAT baixado", None))
            parent.addChild(child)
        else:
            for path in paths:
                child = QTreeWidgetItem([path.stem])
                child.setData(0, Qt.ItemDataRole.UserRole, (source, path.stem, str(path)))
                parent.addChild(child)
        parent.setExpanded(True)

    def selected_profile(self):
        return self._current_saved_profile or self._current_profile()


__all__ = ["FilterProfileData", "FilterProfilesPage"]