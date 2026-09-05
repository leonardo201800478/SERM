"""GUI de definição dos filtros que antecedem o scan do SERM V2.

A página define o *set desejado* e as fontes temporárias de entrada do scan.
Ela não representa os diretórios finais de ROMs dos emuladores.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root


@dataclass(slots=True)
class FilterProfileData:
    """Representa um filtro serializável e independente da interface."""

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
    region_priority: list[str] = field(
        default_factory=lambda: ["Brazil", "America", "Europe", "Japan", "World", "Restante"]
    )
    remove_previous_versions: bool = True
    include_translations: bool = False
    translation_policy: str = "original_then_translation"
    include_chd: bool = True
    prefer_chd: bool = True
    allow_cue_bin: bool = True
    convert_cue_bin_to_chd: bool = True
    keep_cue_bin: bool = True
    whloader_games_only: bool = True


class FilterProfilesPage(QWidget):
    """Editor de filtros MAME, No-Intro, Redump, WHLoader e C64."""

    SOURCES = ("MAME", "No-Intro", "Redump", "WHLoader", "C64")
    REGION_DEFAULT = ("Brazil", "America", "Europe", "Japan", "World", "Restante")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._profiles_path = data_root() / "filter_profiles.json"
        self._selected_dat: Path | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("SERM V2 — Filtros de Sets")
        title.setProperty("role", "title")
        root.addWidget(title)
        intro = QLabel(
            "O filtro define o SET FINAL desejado. Os diretórios abaixo são somente "
            "fontes temporárias para o SCAN e não são os diretórios finais dos emuladores."
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
        self.reset_button = QPushButton("RESTAURAR PADRÃO")
        self.reset_button.clicked.connect(self._reset_defaults)
        self.scan_hint = QLabel("Filtro pronto para ser consumido pelo futuro motor de scan.")
        actions.addWidget(self.save_button)
        actions.addWidget(self.reset_button)
        actions.addWidget(self.scan_hint, 1)
        root.addLayout(actions)

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
        layout = QVBoxLayout(page)

        self.selected_label = QLabel("Selecione um sistema")
        self.selected_label.setProperty("role", "subtitle")
        layout.addWidget(self.selected_label)

        source_box = QGroupBox("Fontes temporárias do SCAN — máximo 3")
        source_layout = QVBoxLayout(source_box)
        self.source_list = QListWidget()
        self.source_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
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
        layout.addWidget(source_box)

        self.filter_stack = QVBoxLayout()
        layout.addLayout(self.filter_stack)
        self._build_filter_controls()
        layout.addStretch()
        return page

    def _build_filter_controls(self) -> None:
        self.content_box = QGroupBox("Conteúdo")
        content = QVBoxLayout(self.content_box)
        self.games_only = QCheckBox("Somente Games")
        self.games_only.setChecked(True)
        content.addWidget(self.games_only)
        self.content_checks: dict[str, QCheckBox] = {}
        for key, text in (
            ("bios", "BIOS"),
            ("educational", "Educational"),
            ("manuals", "Manuais"),
            ("magazines", "Revistas"),
            ("software", "Software / Applications"),
            ("demos", "Demos"),
            ("prototypes", "Prototypes / Betas"),
            ("unlicensed", "Unlicensed"),
        ):
            check = QCheckBox(text)
            self.content_checks[key] = check
            content.addWidget(check)
        self.filter_stack.addWidget(self.content_box)

        self.region_box = QGroupBox("Clones / 1G1R")
        region_layout = QVBoxLayout(self.region_box)
        self.one_game_one_region = QCheckBox("Aplicar 1G1R — uma ROM por jogo/região")
        self.one_game_one_region.setChecked(True)
        region_layout.addWidget(self.one_game_one_region)
        region_layout.addWidget(QLabel("Prioridade de regiões — arraste ou use ↑ / ↓:"))
        self.region_list = QListWidget()
        self.region_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        region_layout.addWidget(self.region_list)
        move = QHBoxLayout()
        self.region_up = QPushButton("↑")
        self.region_down = QPushButton("↓")
        self.region_up.clicked.connect(lambda: self._move_region(-1))
        self.region_down.clicked.connect(lambda: self._move_region(1))
        move.addWidget(self.region_up)
        move.addWidget(self.region_down)
        move.addStretch()
        region_layout.addLayout(move)
        self.filter_stack.addWidget(self.region_box)

        self.version_box = QGroupBox("Versões / revisões")
        version_layout = QVBoxLayout(self.version_box)
        self.remove_previous = QCheckBox("Remover versões/revisões anteriores")
        self.remove_previous.setChecked(True)
        version_layout.addWidget(self.remove_previous)
        version_layout.addWidget(QLabel("Ex.: REV01 + REV02 + REV03 → manter REV03."))
        self.filter_stack.addWidget(self.version_box)

        self.translation_box = QGroupBox("Traduções e variantes não presentes no DAT padrão")
        translation_layout = QFormLayout(self.translation_box)
        self.include_translations = QCheckBox("Permitir traduções catalogadas / DE-PARA")
        self.translation_policy = QComboBox()
        self.translation_policy.addItem("Original primeiro; tradução somente se necessário", "original_then_translation")
        self.translation_policy.addItem("Priorizar tradução quando disponível", "translation_first")
        self.translation_policy.addItem("Somente tradução catalogada", "translation_only")
        translation_layout.addRow(self.include_translations)
        translation_layout.addRow("Política:", self.translation_policy)
        self.filter_stack.addWidget(self.translation_box)

        self.redump_box = QGroupBox("Redump — mídia")
        redump_layout = QVBoxLayout(self.redump_box)
        self.include_chd = QCheckBox("Aceitar CHD")
        self.include_chd.setChecked(True)
        self.prefer_chd = QCheckBox("Priorizar CHD")
        self.prefer_chd.setChecked(True)
        self.allow_cue_bin = QCheckBox("Aceitar CUE/BIN como fallback")
        self.allow_cue_bin.setChecked(True)
        self.convert_cue_bin = QCheckBox("Converter CUE/BIN para CHD via chdman.exe do MAME")
        self.convert_cue_bin.setChecked(True)
        self.keep_cue_bin = QCheckBox("Manter CUE/BIN original após conversão")
        self.keep_cue_bin.setChecked(True)
        for check in (self.include_chd, self.prefer_chd, self.allow_cue_bin, self.convert_cue_bin, self.keep_cue_bin):
            redump_layout.addWidget(check)
        redump_layout.addWidget(QLabel("A conversão usa exclusivamente o chdman.exe da instalação MAME configurada."))
        self.filter_stack.addWidget(self.redump_box)

        self.wh_box = QGroupBox("WHLoader")
        wh_layout = QVBoxLayout(self.wh_box)
        self.wh_games_only = QCheckBox("Somente Games (.lha)")
        self.wh_games_only.setChecked(True)
        wh_layout.addWidget(self.wh_games_only)
        wh_layout.addWidget(QLabel("Software, educacionais e demais categorias ficam fora do set por padrão."))
        self.filter_stack.addWidget(self.wh_box)

        self._source_widgets = (
            self.content_box, self.region_box, self.version_box,
            self.translation_box, self.redump_box, self.wh_box,
        )

    def _new_default_profile(self, source: str, system: str, dat_path: str | None = None) -> FilterProfileData:
        profile = FilterProfileData(source=source, system=system, dat_path=dat_path)
        if source == "WHLoader":
            profile.one_game_one_region = False
            profile.remove_previous_versions = False
        if source == "MAME":
            profile.one_game_one_region = False
            profile.include_chd = True
        return profile

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
        self._load_profile(self._load_saved_profile(source, system, dat_path) or self._new_default_profile(source, system, dat_path))
        self._configure_source_controls(source)

    def _configure_source_controls(self, source: str) -> None:
        is_mame = source == "MAME"
        is_wh = source == "WHLoader"
        is_redump = source == "Redump"
        for widget in self._source_widgets:
            widget.setVisible(True)
        self.region_box.setVisible(not is_mame and not is_wh)
        self.translation_box.setVisible(not is_mame and not is_wh)
        self.redump_box.setVisible(is_redump)
        self.wh_box.setVisible(is_wh)
        if is_mame:
            self.content_box.setTitle("MAME — categorias e classificação dos INIs")
        else:
            self.content_box.setTitle("Conteúdo")

    def _add_source_directory(self) -> None:
        if self.source_list.count() >= 3:
            QMessageBox.information(self, "Fontes do scan", "Cada filtro pode ter no máximo 3 diretórios de origem.")
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
        index = self.translation_policy.findData(profile.translation_policy)
        self.translation_policy.setCurrentIndex(index if index >= 0 else 0)
        self.include_chd.setChecked(profile.include_chd)
        self.prefer_chd.setChecked(profile.prefer_chd)
        self.allow_cue_bin.setChecked(profile.allow_cue_bin)
        self.convert_cue_bin.setChecked(profile.convert_cue_bin_to_chd)
        self.keep_cue_bin.setChecked(profile.keep_cue_bin)
        self.wh_games_only.setChecked(profile.whloader_games_only)

    def _current_profile(self) -> FilterProfileData | None:
        selected = self._selected_item_data()
        if selected is None:
            return None
        source, system, dat_path = selected
        return FilterProfileData(
            source=source,
            system=system,
            dat_path=dat_path,
            source_directories=[self.source_list.item(i).text() for i in range(self.source_list.count())],
            recursive=self.recursive.isChecked(),
            games_only=self.games_only.isChecked(),
            include_bios=self.content_checks["bios"].isChecked(),
            include_educational=self.content_checks["educational"].isChecked(),
            include_manuals=self.content_checks["manuals"].isChecked(),
            include_magazines=self.content_checks["magazines"].isChecked(),
            include_software=self.content_checks["software"].isChecked(),
            include_demos=self.content_checks["demos"].isChecked(),
            include_prototypes=self.content_checks["prototypes"].isChecked(),
            include_unlicensed=self.content_checks["unlicensed"].isChecked(),
            one_game_one_region=self.one_game_one_region.isChecked(),
            region_priority=[self.region_list.item(i).text() for i in range(self.region_list.count())],
            remove_previous_versions=self.remove_previous.isChecked(),
            include_translations=self.include_translations.isChecked(),
            translation_policy=str(self.translation_policy.currentData()),
            include_chd=self.include_chd.isChecked(),
            prefer_chd=self.prefer_chd.isChecked(),
            allow_cue_bin=self.allow_cue_bin.isChecked(),
            convert_cue_bin_to_chd=self.convert_cue_bin.isChecked(),
            keep_cue_bin=self.keep_cue_bin.isChecked(),
            whloader_games_only=self.wh_games_only.isChecked(),
        )

    def _load_saved_profile(self, source: str, system: str, dat_path: str | None) -> FilterProfileData | None:
        try:
            data = json.loads(self._profiles_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        if not isinstance(data, list):
            return None
        for raw in data:
            if not isinstance(raw, dict):
                continue
            if raw.get("source") == source and raw.get("system") == system and raw.get("dat_path") == dat_path:
                try:
                    return FilterProfileData(**raw)
                except TypeError:
                    return None
        return None

    def _save_profile(self) -> None:
        profile = self._current_profile()
        if profile is None:
            QMessageBox.information(self, "Filtros", "Selecione um sistema antes de salvar.")
            return
        try:
            existing = json.loads(self._profiles_path.read_text(encoding="utf-8")) if self._profiles_path.is_file() else []
            if not isinstance(existing, list):
                existing = []
        except (OSError, ValueError, TypeError):
            existing = []
        payload = asdict(profile)
        existing = [
            item for item in existing
            if not isinstance(item, dict)
            or (item.get("source"), item.get("system"), item.get("dat_path"))
            != (profile.source, profile.system, profile.dat_path)
        ]
        existing.append(payload)
        self._profiles_path.parent.mkdir(parents=True, exist_ok=True)
        self._profiles_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
        self.scan_hint.setText(f"Perfil salvo: {profile.source} › {profile.system}")

    def _reset_defaults(self) -> None:
        selected = self._selected_item_data()
        if selected is None:
            return
        self._load_profile(self._new_default_profile(*selected))
        self.scan_hint.setText("Padrões restaurados; clique em SALVAR PERFIL para persistir.")

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
        if not directory.is_dir():
            self._add_source_item(source, "Nenhum DAT baixado", None)
            return
        paths = sorted(directory.glob("*.dat"), key=lambda path: path.name.casefold())
        if not paths:
            self._add_source_item(source, "Nenhum DAT baixado", None)
            return
        parent = QTreeWidgetItem([source])
        parent.setData(0, Qt.ItemDataRole.UserRole, (source, source, None))
        self.source_tree.addTopLevelItem(parent)
        for path in paths:
            name = re.sub(r"\s+", " ", path.stem).strip()
            child = QTreeWidgetItem([name])
            child.setData(0, Qt.ItemDataRole.UserRole, (source, name, str(path)))
            parent.addChild(child)
        parent.setExpanded(True)

    def selected_profile(self) -> FilterProfileData | None:
        """Retorna o filtro atual para integração com o motor de scan."""
        return self._current_profile()


__all__ = ["FilterProfileData", "FilterProfilesPage"]
