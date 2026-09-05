"""GUI de filtros e scan do SERM V2.

O perfil define o SET desejado. Depois de salvo, o mesmo perfil é a entrada
para o motor de scan. MAME possui critérios próprios baseados na V1; as
fontes DAT seguem políticas específicas de No-Intro, Redump, WHLoader e C64.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QListWidget, QMessageBox, QPushButton, QScrollArea, QSplitter,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..runtime.paths import data_root


@dataclass(slots=True)
class FilterProfileData:
    source: str
    system: str
    dat_path: str | None = None
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
    # Critérios específicos do MAME, derivados da organização da V1.
    mame_set_type: str = "split"
    mame_clones: str = "with_clones"
    mame_bios: str = "exclude_bios"
    mame_devices: str = "exclude_devices"
    mame_chds: str = "include_chds"
    mame_optional_roms: bool = True
    mame_working_only: bool = False
    mame_category_filters: list[str] = field(default_factory=list)


class FilterProfilesPage(QWidget):
    """Editor do perfil e fluxo imediato de scan."""

    SOURCES = ("MAME", "No-Intro", "Redump", "WHLoader", "C64")
    REGION_DEFAULT = ("Brazil", "America", "Europe", "Japan", "World", "Restante")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._profiles_path = data_root() / "filter_profiles.json"
        self._selected_dat: Path | None = None
        self._last_saved_profile: FilterProfileData | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("SERM V2 — Filtros e Scan")
        title.setProperty("role", "title")
        root.addWidget(title)
        intro = QLabel(
            "Defina o SET final, salve o perfil e execute o SCAN com exatamente o mesmo perfil. "
            "Os diretórios informados são fontes temporárias do scan; não são diretórios finais dos emuladores."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._source_tree())
        splitter.addWidget(self._editor())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        actions = QHBoxLayout()
        self.save_button = QPushButton("SALVAR PERFIL")
        self.save_button.setProperty("role", "primary")
        self.save_button.clicked.connect(self._save_profile)
        self.scan_button = QPushButton("SALVAR E INICIAR SCAN")
        self.scan_button.setProperty("role", "primary")
        self.scan_button.setEnabled(False)
        self.scan_button.clicked.connect(self._save_and_scan)
        self.reset_button = QPushButton("RESTAURAR PADRÃO")
        self.reset_button.clicked.connect(self._reset_defaults)
        self.scan_hint = QLabel("Nenhum perfil salvo nesta sessão.")
        actions.addWidget(self.save_button)
        actions.addWidget(self.scan_button)
        actions.addWidget(self.reset_button)
        actions.addWidget(self.scan_hint, 1)
        root.addLayout(actions)

        scan_box = QGroupBox("SCAN")
        scan_layout = QVBoxLayout(scan_box)
        self.scan_status = QLabel("O scan será iniciado pelo perfil salvo. O motor físico será conectado a esta etapa.")
        self.scan_status.setWordWrap(True)
        scan_layout.addWidget(self.scan_status)
        root.addWidget(scan_box)

    def _source_tree(self) -> QWidget:
        box = QGroupBox("Sets disponíveis")
        layout = QVBoxLayout(box)
        self.source_tree = QTreeWidget()
        self.source_tree.setHeaderLabels(["Fonte / sistema"])
        self.source_tree.setMinimumWidth(280)
        self.source_tree.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self.source_tree, 1)
        self.refresh_button = QPushButton("ATUALIZAR CATÁLOGOS LOCAIS")
        self.refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_button)
        return box

    def _editor(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        self.selected_label = QLabel("Selecione um sistema")
        self.selected_label.setProperty("role", "subtitle")
        outer.addWidget(self.selected_label)

        source_box = QGroupBox("Fontes temporárias do SCAN — máximo 3")
        source_layout = QVBoxLayout(source_box)
        self.source_list = QListWidget()
        source_layout.addWidget(self.source_list)
        source_actions = QHBoxLayout()
        add = QPushButton("+ ADICIONAR DIRETÓRIO")
        add.clicked.connect(self._add_source_directory)
        remove = QPushButton("REMOVER")
        remove.clicked.connect(self._remove_source_directory)
        source_actions.addWidget(add)
        source_actions.addWidget(remove)
        source_actions.addStretch()
        source_layout.addLayout(source_actions)
        self.recursive = QCheckBox("Incluir subdiretórios")
        self.recursive.setChecked(True)
        source_layout.addWidget(self.recursive)
        outer.addWidget(source_box)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        self.filter_layout = QVBoxLayout(content)
        self.filter_layout.setSpacing(10)
        self._build_mame_controls()
        self._build_generic_controls()
        self.filter_layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        return page

    def _build_mame_controls(self) -> None:
        self.mame_box = QGroupBox("MAME — filtros do SET")
        layout = QVBoxLayout(self.mame_box)
        form = QFormLayout()

        self.mame_set_type = QComboBox()
        self.mame_set_type.addItem("Split — padrão", "split")
        self.mame_set_type.addItem("Non-Merged", "non_merged")
        self.mame_set_type.addItem("Full-Merged", "full_merged")
        form.addRow("Tipo de SET:", self.mame_set_type)

        self.mame_clones = QComboBox()
        self.mame_clones.addItem("Com clones", "with_clones")
        self.mame_clones.addItem("Somente parents / sem clones", "parents_only")
        form.addRow("Clones:", self.mame_clones)

        self.mame_bios = QComboBox()
        self.mame_bios.addItem("Sem BIOS", "exclude_bios")
        self.mame_bios.addItem("Com BIOS", "include_bios")
        self.mame_bios.addItem("Somente BIOS", "bios_only")
        form.addRow("BIOS:", self.mame_bios)

        self.mame_devices = QComboBox()
        self.mame_devices.addItem("Sem devices", "exclude_devices")
        self.mame_devices.addItem("Com devices", "include_devices")
        self.mame_devices.addItem("Somente devices", "devices_only")
        form.addRow("Devices:", self.mame_devices)

        self.mame_chds = QComboBox()
        self.mame_chds.addItem("Com CHDs / disks", "include_chds")
        self.mame_chds.addItem("Sem CHDs / disks", "exclude_chds")
        self.mame_chds.addItem("Somente sets com CHD", "chds_only")
        form.addRow("CHDs / disks:", self.mame_chds)
        layout.addLayout(form)

        checks = QHBoxLayout()
        self.mame_optional_roms = QCheckBox("Incluir ROMs opcionais")
        self.mame_optional_roms.setChecked(True)
        self.mame_working_only = QCheckBox("Somente máquinas Working")
        for widget in (self.mame_optional_roms, self.mame_working_only):
            checks.addWidget(widget)
        checks.addStretch()
        layout.addLayout(checks)

        note = QLabel(
            "Classificação não é filtro: CATLIST/INI e ListXML continuam sendo preservados. "
            "A resolução segue a fonte canônica do catálogo e não mistura catlist.ini entre diretórios."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.filter_layout.addWidget(self.mame_box)

    def _build_generic_controls(self) -> None:
        # Cada grupo tem responsabilidade única; isso evita o antigo bloco embolado.
        self.content_box = QGroupBox("Conteúdo")
        content = QVBoxLayout(self.content_box)
        self.games_only = QCheckBox("Somente Games")
        self.games_only.setChecked(True)
        content.addWidget(self.games_only)
        self.content_checks: dict[str, QCheckBox] = {}
        for key, text in (
            ("bios", "BIOS"), ("educational", "Educational"), ("manuals", "Manuais"),
            ("magazines", "Revistas"), ("software", "Software / Applications"),
            ("demos", "Demos"), ("prototypes", "Prototypes / Betas"), ("unlicensed", "Unlicensed"),
        ):
            check = QCheckBox(text)
            self.content_checks[key] = check
            content.addWidget(check)
        self.filter_layout.addWidget(self.content_box)

        self.region_box = QGroupBox("Clones / 1G1R")
        region_layout = QVBoxLayout(self.region_box)
        self.one_game_one_region = QCheckBox("Aplicar 1G1R — uma ROM por jogo/região")
        self.one_game_one_region.setChecked(True)
        region_layout.addWidget(self.one_game_one_region)
        region_layout.addWidget(QLabel("Prioridade regional:"))
        self.region_list = QListWidget()
        self.region_list.setMaximumHeight(145)
        self.region_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        region_layout.addWidget(self.region_list)
        move = QHBoxLayout()
        self.region_up = QPushButton("↑ Subir")
        self.region_down = QPushButton("↓ Descer")
        self.region_up.clicked.connect(lambda: self._move_region(-1))
        self.region_down.clicked.connect(lambda: self._move_region(1))
        move.addWidget(self.region_up)
        move.addWidget(self.region_down)
        move.addStretch()
        region_layout.addLayout(move)
        self.filter_layout.addWidget(self.region_box)

        self.version_box = QGroupBox("Versões / revisões")
        version_layout = QVBoxLayout(self.version_box)
        self.remove_previous = QCheckBox("Remover versões/revisões anteriores")
        self.remove_previous.setChecked(True)
        version_layout.addWidget(self.remove_previous)
        version_layout.addWidget(QLabel("A seleção considera a regra de versão do DAT antes do scan físico."))
        self.filter_layout.addWidget(self.version_box)

        self.translation_box = QGroupBox("Traduções / DE-PARA")
        translation_layout = QFormLayout(self.translation_box)
        self.include_translations = QCheckBox("Permitir traduções catalogadas / DE-PARA")
        self.translation_policy = QComboBox()
        self.translation_policy.addItem("Original primeiro; tradução somente se necessário", "original_then_translation")
        self.translation_policy.addItem("Priorizar tradução quando disponível", "translation_first")
        self.translation_policy.addItem("Somente tradução catalogada", "translation_only")
        translation_layout.addRow(self.include_translations)
        translation_layout.addRow("Política:", self.translation_policy)
        self.filter_layout.addWidget(self.translation_box)

        self.redump_box = QGroupBox("Redump — mídia óptica")
        redump_layout = QVBoxLayout(self.redump_box)
        self.include_chd = QCheckBox("Aceitar CHD")
        self.include_chd.setChecked(True)
        self.prefer_chd = QCheckBox("Priorizar CHD")
        self.prefer_chd.setChecked(True)
        self.allow_cue_bin = QCheckBox("Aceitar CUE/BIN como fallback")
        self.allow_cue_bin.setChecked(True)
        self.convert_cue_bin = QCheckBox("Converter CUE/BIN para CHD via chdman.exe")
        self.convert_cue_bin.setChecked(True)
        self.keep_cue_bin = QCheckBox("Manter CUE/BIN original")
        self.keep_cue_bin.setChecked(True)
        for check in (self.include_chd, self.prefer_chd, self.allow_cue_bin, self.convert_cue_bin, self.keep_cue_bin):
            redump_layout.addWidget(check)
        self.filter_layout.addWidget(self.redump_box)

        self.wh_box = QGroupBox("WHLoader")
        wh_layout = QVBoxLayout(self.wh_box)
        self.wh_games_only = QCheckBox("Somente Games (.lha)")
        self.wh_games_only.setChecked(True)
        wh_layout.addWidget(self.wh_games_only)
        wh_layout.addWidget(QLabel("Pacotes WHDLoad são tratados como mídia LHA, sem extração pelo filtro."))
        self.filter_layout.addWidget(self.wh_box)

    def _selected_item_data(self) -> tuple[str, str, str | None] | None:
        item = self.source_tree.currentItem()
        if item is None:
            return None
        data = item.data(0, Qt.ItemDataRole.UserRole)
        return tuple(data) if isinstance(data, (list, tuple)) and len(data) == 3 else None

    def _selection_changed(self) -> None:
        selected = self._selected_item_data()
        if selected is None:
            return
        source, system, dat_path = selected
        self.selected_label.setText(f"{source}  ›  {system}")
        self._selected_dat = Path(dat_path) if dat_path else None
        saved = self._load_saved_profile(source, system, dat_path)
        self._load_profile(saved or self._new_default_profile(source, system, dat_path))
        self._configure_source_controls(source)

    def _configure_source_controls(self, source: str) -> None:
        is_mame = source == "MAME"
        is_wh = source == "WHLoader"
        is_redump = source == "Redump"
        self.mame_box.setVisible(is_mame)
        self.content_box.setVisible(not is_mame)
        self.region_box.setVisible(not is_mame and not is_wh)
        self.version_box.setVisible(not is_mame and not is_wh)
        self.translation_box.setVisible(not is_mame and not is_wh)
        self.redump_box.setVisible(is_redump)
        self.wh_box.setVisible(is_wh)

    def _new_default_profile(self, source: str, system: str, dat_path: str | None = None) -> FilterProfileData:
        profile = FilterProfileData(source=source, system=system, dat_path=dat_path)
        if source == "MAME":
            profile.one_game_one_region = False
        elif source == "WHLoader":
            profile.one_game_one_region = False
            profile.remove_previous_versions = False
        return profile

    def _load_profile(self, profile: FilterProfileData) -> None:
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
        idx = self.translation_policy.findData(profile.translation_policy)
        self.translation_policy.setCurrentIndex(idx if idx >= 0 else 0)
        self.include_chd.setChecked(profile.include_chd)
        self.prefer_chd.setChecked(profile.prefer_chd)
        self.allow_cue_bin.setChecked(profile.allow_cue_bin)
        self.convert_cue_bin.setChecked(profile.convert_cue_bin_to_chd)
        self.keep_cue_bin.setChecked(profile.keep_cue_bin)
        self.wh_games_only.setChecked(profile.whloader_games_only)
        idx = self.mame_set_type.findData(profile.mame_set_type)
        self.mame_set_type.setCurrentIndex(idx if idx >= 0 else 0)
        idx = self.mame_clones.findData(profile.mame_clones)
        self.mame_clones.setCurrentIndex(idx if idx >= 0 else 0)
        idx = self.mame_bios.findData(profile.mame_bios)
        self.mame_bios.setCurrentIndex(idx if idx >= 0 else 0)
        idx = self.mame_devices.findData(profile.mame_devices)
        self.mame_devices.setCurrentIndex(idx if idx >= 0 else 0)
        idx = self.mame_chds.findData(profile.mame_chds)
        self.mame_chds.setCurrentIndex(idx if idx >= 0 else 0)
        self.mame_optional_roms.setChecked(profile.mame_optional_roms)
        self.mame_working_only.setChecked(profile.mame_working_only)

    def _current_profile(self) -> FilterProfileData | None:
        selected = self._selected_item_data()
        if selected is None:
            return None
        source, system, dat_path = selected
        return FilterProfileData(
            source=source, system=system, dat_path=dat_path,
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
            mame_clones=str(self.mame_clones.currentData()), mame_bios=str(self.mame_bios.currentData()),
            mame_devices=str(self.mame_devices.currentData()), mame_chds=str(self.mame_chds.currentData()),
            mame_optional_roms=self.mame_optional_roms.isChecked(), mame_working_only=self.mame_working_only.isChecked(),
        )

    def _load_saved_profile(self, source: str, system: str, dat_path: str | None) -> FilterProfileData | None:
        try:
            data = json.loads(self._profiles_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        if not isinstance(data, list):
            return None
        for raw in data:
            if isinstance(raw, dict) and (raw.get("source"), raw.get("system"), raw.get("dat_path")) == (source, system, dat_path):
                try:
                    return FilterProfileData(**raw)
                except TypeError:
                    return None
        return None

    def _save_profile(self) -> FilterProfileData | None:
        profile = self._current_profile()
        if profile is None:
            QMessageBox.information(self, "Filtros", "Selecione um sistema antes de salvar.")
            return None
        try:
            existing = json.loads(self._profiles_path.read_text(encoding="utf-8")) if self._profiles_path.is_file() else []
            if not isinstance(existing, list):
                existing = []
        except (OSError, ValueError, TypeError):
            existing = []
        existing = [item for item in existing if not isinstance(item, dict) or (item.get("source"), item.get("system"), item.get("dat_path")) != (profile.source, profile.system, profile.dat_path)]
        existing.append(asdict(profile))
        self._profiles_path.parent.mkdir(parents=True, exist_ok=True)
        self._profiles_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
        self._last_saved_profile = profile
        self.scan_button.setEnabled(True)
        self.scan_hint.setText(f"Perfil salvo: {profile.source} › {profile.system}")
        return profile

    def _save_and_scan(self) -> None:
        profile = self._save_profile()
        if profile is None:
            return
        self.scan_status.setText(
            f"SCAN preparado: {profile.source} › {profile.system}. "
            "O perfil salvo foi validado e será a entrada do motor de scan V2."
        )

    def _add_source_directory(self) -> None:
        if self.source_list.count() >= 3:
            QMessageBox.information(self, "Fontes do scan", "Cada perfil pode ter no máximo 3 diretórios de origem.")
            return
        directory = QFileDialog.getExistingDirectory(self, "Selecionar diretório de origem do scan", str(Path.home()))
        if directory:
            path = str(Path(directory).resolve())
            if not any(self.source_list.item(i).text() == path for i in range(self.source_list.count())):
                self.source_list.addItem(path)

    def _remove_source_directory(self) -> None:
        row = self.source_list.currentRow()
        if row >= 0:
            self.source_list.takeItem(row)

    def _move_region(self, delta: int) -> None:
        row = self.region_list.currentRow()
        target = row + delta
        if row < 0 or target < 0 or target >= self.region_list.count():
            return
        item = self.region_list.takeItem(row)
        self.region_list.insertItem(target, item)
        self.region_list.setCurrentRow(target)

    def _reset_defaults(self) -> None:
        selected = self._selected_item_data()
        if selected is None:
            return
        self._load_profile(self._new_default_profile(*selected))
        self.scan_button.setEnabled(False)
        self.scan_hint.setText("Padrões restaurados; salve o perfil antes do scan.")

    def refresh(self) -> None:
        self.source_tree.clear()
        self._add_source_item("MAME", "MAME", None)
        self._add_dat_entries("No-Intro", data_root() / "sources" / "no_intro" / "dats")
        self._add_dat_entries("Redump", data_root() / "sources" / "redump" / "dats")
        self._add_source_item("WHLoader", "WHLoader", None)
        self._add_source_item("C64", "Commodore C64 - Games", None)
        if self.source_tree.topLevelItemCount() and self.source_tree.currentItem() is None:
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

    def _add_dat_entries(self, source: str, directory: Path) -> None:
        parent = QTreeWidgetItem([source])
        parent.setData(0, Qt.ItemDataRole.UserRole, (source, source, None))
        self.source_tree.addTopLevelItem(parent)
        if not directory.is_dir():
            child = QTreeWidgetItem(["Nenhum DAT baixado"])
            child.setData(0, Qt.ItemDataRole.UserRole, (source, "Nenhum DAT baixado", None))
            parent.addChild(child)
        else:
            paths = sorted(directory.glob("*.dat"), key=lambda path: path.name.casefold())
            if not paths:
                child = QTreeWidgetItem(["Nenhum DAT baixado"])
                child.setData(0, Qt.ItemDataRole.UserRole, (source, "Nenhum DAT baixado", None))
                parent.addChild(child)
            for path in paths:
                name = re.sub(r"\s+", " ", path.stem).strip()
                child = QTreeWidgetItem([name])
                child.setData(0, Qt.ItemDataRole.UserRole, (source, name, str(path)))
                parent.addChild(child)
        parent.setExpanded(True)

    def selected_profile(self) -> FilterProfileData | None:
        return self._current_profile()


__all__ = ["FilterProfileData", "FilterProfilesPage"]
