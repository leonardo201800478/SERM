"""Filtros e scan do SERM V2.

O perfil salvo e o contrato único entre filtro, scan e reconstrução.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
    QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..runtime.paths import data_root


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


class FilterProfilesPage(QWidget):
    """Cria/seleciona o perfil e inicia o scan usando exatamente esse perfil."""

    scan_requested = Signal(object)
    reconstruction_requested = Signal(object)
    REGION_DEFAULT = ("Brazil", "America", "Europe", "Japan", "World", "Restante")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._profiles_path = data_root() / "filter_profiles.json"
        self._selected_dat: Path | None = None
        self._current_saved_profile: FilterProfileData | None = None
        self._building = False
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("SERM V2 — Filtros e Scan")
        title.setProperty("role", "title")
        root.addWidget(title)
        intro = QLabel(
            "Fluxo: selecione o catálogo → configure o filtro → salve o perfil → "
            "inicie o scan. O perfil salvo permanece como contrato para o scanner e, "
            "depois, para a reconstrução."
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
        layout.addWidget(self.source_tree, 1)

        profiles_box = QGroupBox("Perfis salvos")
        profiles_layout = QVBoxLayout(profiles_box)
        self.profile_list = QListWidget()
        self.profile_list.currentItemChanged.connect(self._saved_profile_selected)
        profiles_layout.addWidget(self.profile_list)
        layout.addWidget(profiles_box, 1)

        refresh = QPushButton("ATUALIZAR")
        refresh.clicked.connect(self.refresh)
        layout.addWidget(refresh)
        return box

    def _editor_panel(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.selected_label = QLabel("Selecione um catálogo")
        self.selected_label.setProperty("role", "subtitle")
        layout.addWidget(self.selected_label)

        source_box = QGroupBox("Fontes temporárias do scan — máximo 3")
        source_layout = QVBoxLayout(source_box)
        self.source_list = QListWidget()
        source_layout.addWidget(self.source_list)
        actions = QHBoxLayout()
        add = QPushButton("+ ADICIONAR")
        add.clicked.connect(self._add_source_directory)
        remove = QPushButton("REMOVER")
        remove.clicked.connect(self._remove_source_directory)
        actions.addWidget(add)
        actions.addWidget(remove)
        actions.addStretch()
        source_layout.addLayout(actions)
        self.recursive = QCheckBox("Incluir subdiretórios")
        self.recursive.setChecked(True)
        source_layout.addWidget(self.recursive)
        layout.addWidget(source_box)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        self.filter_layout = QVBoxLayout(body)
        self._build_generic_controls()
        self._build_mame_controls()
        self.filter_layout.addStretch()
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

        scan_box = QGroupBox("Scan do perfil")
        scan_layout = QVBoxLayout(scan_box)
        self.scan_context = QLabel("Nenhum perfil salvo selecionado.")
        self.scan_context.setWordWrap(True)
        scan_layout.addWidget(self.scan_context)
        buttons = QHBoxLayout()
        self.save_button = QPushButton("SALVAR PERFIL")
        self.save_button.setProperty("role", "primary")
        self.save_button.clicked.connect(self._save_profile)
        self.scan_button = QPushButton("SALVAR E INICIAR SCAN")
        self.scan_button.setProperty("role", "primary")
        self.scan_button.clicked.connect(self._save_and_scan)
        self.reconstruction_button = QPushButton("ABRIR RECONSTRUÇÃO")
        self.reconstruction_button.setEnabled(False)
        self.reconstruction_button.clicked.connect(self._open_reconstruction)
        reset = QPushButton("RESTAURAR PADRÃO")
        reset.clicked.connect(self._reset_defaults)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.scan_button)
        buttons.addWidget(self.reconstruction_button)
        buttons.addWidget(reset)
        scan_layout.addLayout(buttons)
        self.scan_status = QLabel("Nenhum scan iniciado.")
        self.scan_status.setWordWrap(True)
        scan_layout.addWidget(self.scan_status)
        layout.addWidget(scan_box)
        return page

    def _build_generic_controls(self) -> None:
        self.content_box = QGroupBox("Conteúdo")
        content = QFormLayout(self.content_box)
        self.games_only = QCheckBox("Somente Games")
        self.games_only.setChecked(True)
        content.addRow(self.games_only)
        self.content_checks: dict[str, QCheckBox] = {}
        for key, text in (
            ("bios", "BIOS"), ("educational", "Educational"), ("manuals", "Manuais"),
            ("magazines", "Revistas"), ("software", "Software / Applications"),
            ("demos", "Demos"), ("prototypes", "Prototypes / Betas"), ("unlicensed", "Unlicensed"),
        ):
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
        self.include_chd = QCheckBox("Aceitar CHD"); self.include_chd.setChecked(True)
        self.prefer_chd = QCheckBox("Priorizar CHD"); self.prefer_chd.setChecked(True)
        self.allow_cue_bin = QCheckBox("CUE/BIN como fallback"); self.allow_cue_bin.setChecked(True)
        self.convert_cue_bin = QCheckBox("Converter CUE/BIN para CHD via chdman.exe"); self.convert_cue_bin.setChecked(True)
        self.keep_cue_bin = QCheckBox("Manter CUE/BIN original"); self.keep_cue_bin.setChecked(True)
        for widget in (self.include_chd, self.prefer_chd, self.allow_cue_bin, self.convert_cue_bin, self.keep_cue_bin):
            redump.addRow(widget)
        self.filter_layout.addWidget(self.redump_box)

        self.wh_box = QGroupBox("WHLoader")
        wh = QFormLayout(self.wh_box)
        self.wh_games_only = QCheckBox("Somente Games (.lha)"); self.wh_games_only.setChecked(True)
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
        self.mame_chd = QCheckBox("Incluir CHDs / disks"); self.mame_chd.setChecked(True)
        self.mame_optional = QCheckBox("Incluir ROMs opcionais"); self.mame_optional.setChecked(True)
        self.mame_working = QCheckBox("Somente máquinas marcadas como working")
        for widget in (self.mame_bios, self.mame_devices, self.mame_chd, self.mame_optional, self.mame_working):
            layout.addRow(widget)
        self.mame_classification = QComboBox()
        self.mame_classification.addItem("catlist.ini — prioridade", "catlist")
        self.mame_classification.addItem("ListXML — fallback", "listxml")
        layout.addRow("Classificação:", self.mame_classification)
        self.filter_layout.addWidget(self.mame_box)

    def _selected_item_data(self) -> tuple[str, str, str | None] | None:
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
        self.selected_label.setText(f"{source}  ›  {system}")
        self._selected_dat = Path(dat_path) if dat_path else None
        saved = self._load_saved_profile(source, system, dat_path)
        self._current_saved_profile = saved
        self._load_profile(saved or self._new_default_profile(source, system, dat_path))
        self._configure_source_controls(source)
        self._refresh_profile_list(source, system, dat_path)

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
        if is_mame:
            self.content_box.setTitle("MAME — categorias do catálogo")

    def _new_default_profile(self, source: str, system: str, dat_path: str | None) -> FilterProfileData:
        now = datetime.now(timezone.utc).isoformat()
        profile = FilterProfileData(
            source=source, system=system, dat_path=dat_path,
            profile_id=str(uuid4()), name=f"{source} — {system}", created_at=now, updated_at=now,
        )
        if source == "MAME":
            profile.one_game_one_region = False
        if source == "WHLoader":
            profile.one_game_one_region = False
            profile.remove_previous_versions = False
        return profile

    def _load_profile(self, profile: FilterProfileData) -> None:
        self._building = True
        try:
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
            self.scan_context.setText(f"Perfil: {profile.name}\nID: {profile.profile_id}\nFonte: {profile.source} › {profile.system}")
        finally:
            self._building = False

    def _current_profile(self) -> FilterProfileData | None:
        selected = self._selected_item_data()
        if selected is None:
            return None
        source, system, dat_path = selected
        previous = self._current_saved_profile
        now = datetime.now(timezone.utc).isoformat()
        return FilterProfileData(
            source=source, system=system, dat_path=dat_path,
            profile_id=previous.profile_id if previous else str(uuid4()),
            name=previous.name if previous else f"{source} — {system}",
            schema_version=2,
            created_at=previous.created_at if previous else now,
            updated_at=now,
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

    @staticmethod
    def _from_dict(raw: dict) -> FilterProfileData | None:
        try:
            fields = set(FilterProfileData.__dataclass_fields__)
            clean = {key: value for key, value in raw.items() if key in fields}
            profile = FilterProfileData(**clean)
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

    def _read_profiles(self) -> list[FilterProfileData]:
        try:
            raw = json.loads(self._profiles_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return []
        if not isinstance(raw, list):
            return []
        result: list[FilterProfileData] = []
        for item in raw:
            if isinstance(item, dict):
                profile = self._from_dict(item)
                if profile is not None:
                    result.append(profile)
        return result

    def _write_profiles(self, profiles: list[FilterProfileData]) -> None:
        self._profiles_path.parent.mkdir(parents=True, exist_ok=True)
        self._profiles_path.write_text(json.dumps([asdict(p) for p in profiles], indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_saved_profile(self, source: str, system: str, dat_path: str | None) -> FilterProfileData | None:
        return next((p for p in self._read_profiles() if p.source == source and p.system == system and p.dat_path == dat_path), None)

    def _refresh_profile_list(self, source: str | None = None, system: str | None = None, dat_path: str | None = None) -> None:
        profiles = self._read_profiles()
        self.profile_list.blockSignals(True)
        self.profile_list.clear()
        selected_row = -1
        for index, profile in enumerate(profiles):
            item = QListWidgetItem(f"{profile.name}\n{profile.source} › {profile.system}")
            item.setData(Qt.ItemDataRole.UserRole, profile.profile_id)
            item.setToolTip(f"Perfil {profile.profile_id}\nAtualizado: {profile.updated_at}")
            self.profile_list.addItem(item)
            if self._current_saved_profile and profile.profile_id == self._current_saved_profile.profile_id:
                selected_row = index
        self.profile_list.blockSignals(False)
        if selected_row >= 0:
            self.profile_list.setCurrentRow(selected_row)

    def _saved_profile_selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        profile_id = current.data(Qt.ItemDataRole.UserRole)
        profile = next((p for p in self._read_profiles() if p.profile_id == profile_id), None)
        if profile is None:
            return
        for i in range(self.source_tree.topLevelItemCount()):
            root = self.source_tree.topLevelItem(i)
            for item in [root, *[root.child(n) for n in range(root.childCount())]]:
                data = item.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(data, (tuple, list)) and tuple(data) == (profile.source, profile.system, profile.dat_path):
                    self.source_tree.setCurrentItem(item)
                    self._current_saved_profile = profile
                    self._load_profile(profile)
                    self._configure_source_controls(profile.source)
                    return

    def _save_profile(self) -> FilterProfileData | None:
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
        self._refresh_profile_list(profile.source, profile.system, profile.dat_path)
        self.scan_context.setText(f"Perfil salvo: {profile.name}\nID: {profile.profile_id}\n{profile.source} › {profile.system}")
        self.scan_status.setText("Perfil salvo. Ele é a entrada oficial do próximo scan.")
        self.reconstruction_button.setEnabled(True)
        return profile

    def _save_and_scan(self) -> None:
        profile = self._save_profile()
        if profile is None:
            return
        self.scan_status.setText("Perfil salvo e enviado ao motor de scan. O resultado deverá registrar o mesmo profile_id.")
        self.scan_requested.emit(profile)

    def _open_reconstruction(self) -> None:
        profile = self._current_saved_profile or self._save_profile()
        if profile is not None:
            self.reconstruction_requested.emit(profile)
            window = self.window()
            navigation = getattr(window, "navigation", None)
            if navigation is not None:
                navigation.setCurrentRow(5)

    def _reset_defaults(self) -> None:
        selected = self._selected_item_data()
        if selected:
            self._load_profile(self._new_default_profile(*selected))
            self._current_saved_profile = None
            self.scan_status.setText("Padrões restaurados; salve novamente para persistir.")

    def _add_source_directory(self) -> None:
        if self.source_list.count() >= 3:
            QMessageBox.information(self, "Fontes", "Máximo de 3 diretórios por perfil.")
            return
        directory = QFileDialog.getExistingDirectory(self, "Diretório de origem", str(Path.home()))
        if directory:
            path = str(Path(directory).resolve())
            if not any(self.source_list.item(i).text() == path for i in range(self.source_list.count())):
                self.source_list.addItem(path)

    def _remove_source_directory(self) -> None:
        row = self.source_list.currentRow()
        if row >= 0:
            self.source_list.takeItem(row)

    def refresh(self) -> None:
        self.source_tree.clear()
        self._add_source_item("MAME", "MAME", None)
        self._add_dat_entries("No-Intro", data_root() / "sources" / "no_intro" / "dats")
        self._add_dat_entries("Redump", data_root() / "sources" / "redump" / "dats")
        self._add_source_item("WHLoader", "WHLoader", None)
        self._add_source_item("C64", "Commodore C64 - Games", None)
        self._refresh_profile_list()
        if self.source_tree.topLevelItemCount():
            self.source_tree.setCurrentItem(self.source_tree.topLevelItem(0))

    def _add_source_item(self, source: str, system: str, dat_path: str | None) -> None:
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

    def _add_dat_entries(self, source: str, directory: Path) -> None:
        parent = QTreeWidgetItem([source])
        parent.setData(0, Qt.ItemDataRole.UserRole, (source, source, None))
        self.source_tree.addTopLevelItem(parent)
        if not directory.is_dir():
            child = QTreeWidgetItem(["Nenhum DAT baixado"])
            child.setData(0, Qt.ItemDataRole.UserRole, (source, "Nenhum DAT baixado", None))
            parent.addChild(child)
        else:
            paths = sorted(directory.glob("*.dat"), key=lambda p: p.name.casefold())
            if not paths:
                child = QTreeWidgetItem(["Nenhum DAT baixado"])
                child.setData(0, Qt.ItemDataRole.UserRole, (source, "Nenhum DAT baixado", None))
                parent.addChild(child)
            for path in paths:
                child = QTreeWidgetItem([path.stem])
                child.setData(0, Qt.ItemDataRole.UserRole, (source, path.stem, str(path)))
                parent.addChild(child)
        parent.setExpanded(True)

    def selected_profile(self) -> FilterProfileData | None:
        return self._current_saved_profile or self._current_profile()


__all__ = ["FilterProfileData", "FilterProfilesPage"]
