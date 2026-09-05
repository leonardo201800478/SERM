"""Filtros e scan do SERM V2."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QListWidget, QMessageBox, QPushButton, QScrollArea, QSplitter, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
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
    mame_set_type: str = "split"
    mame_clone_policy: str = "with_clones"
    mame_include_bios: bool = False
    mame_include_devices: bool = False
    mame_include_chd: bool = True
    mame_include_optional: bool = True
    mame_working_only: bool = False
    mame_classification_source: str = "catlist"


class FilterProfilesPage(QWidget):
    """Seleciona perfis, executa o scan e entrega o mesmo contrato à reconstrução."""

    scan_requested = Signal(object)
    REGION_DEFAULT = ("Brazil", "America", "Europe", "Japan", "World", "Restante")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._profiles_path = data_root() / "filter_profiles.json"
        self._selected_dat: Path | None = None
        self._current_saved_profile: FilterProfileData | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel("SERM V2 — Filtros e Scan")
        title.setProperty("role", "title")
        root.addWidget(title)
        intro = QLabel("O perfil define o SET desejado. Salve o perfil antes do scan; o mesmo perfil será reutilizado pelo scanner e pela reconstrução.")
        intro.setWordWrap(True)
        root.addWidget(intro)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._source_tree())
        splitter.addWidget(self._editor())
        splitter.setStretchFactor(0, 0); splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

    def _source_tree(self) -> QWidget:
        box = QGroupBox("Catálogos e perfis")
        layout = QVBoxLayout(box)
        self.source_tree = QTreeWidget(); self.source_tree.setHeaderLabels(["Fonte / sistema"]); self.source_tree.setMinimumWidth(280)
        self.source_tree.itemSelectionChanged.connect(self._selection_changed); layout.addWidget(self.source_tree, 1)
        self.refresh_button = QPushButton("ATUALIZAR CATÁLOGOS"); self.refresh_button.clicked.connect(self.refresh); layout.addWidget(self.refresh_button)
        return box

    def _editor(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page)
        self.selected_label = QLabel("Selecione um sistema"); self.selected_label.setProperty("role", "subtitle"); layout.addWidget(self.selected_label)
        source_box = QGroupBox("Fontes temporárias do scan — máximo 3"); source_layout = QVBoxLayout(source_box)
        self.source_list = QListWidget(); source_layout.addWidget(self.source_list)
        source_actions = QHBoxLayout(); add = QPushButton("+ ADICIONAR"); add.clicked.connect(self._add_source_directory); remove = QPushButton("REMOVER"); remove.clicked.connect(self._remove_source_directory); source_actions.addWidget(add); source_actions.addWidget(remove); source_actions.addStretch(); source_layout.addLayout(source_actions)
        self.recursive = QCheckBox("Incluir subdiretórios"); self.recursive.setChecked(True); source_layout.addWidget(self.recursive); layout.addWidget(source_box)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget(); self.filter_layout = QVBoxLayout(body); self._build_generic_controls(); self._build_mame_controls(); self.filter_layout.addStretch(); scroll.setWidget(body); layout.addWidget(scroll, 1)
        actions = QHBoxLayout(); self.save_button = QPushButton("SALVAR PERFIL"); self.save_button.setProperty("role", "primary"); self.save_button.clicked.connect(self._save_profile); self.scan_button = QPushButton("SALVAR E INICIAR SCAN"); self.scan_button.setProperty("role", "primary"); self.scan_button.clicked.connect(self._save_and_scan); self.reset_button = QPushButton("RESTAURAR PADRÃO"); self.reset_button.clicked.connect(self._reset_defaults); actions.addWidget(self.save_button); actions.addWidget(self.scan_button); actions.addWidget(self.reset_button); layout.addLayout(actions)
        self.scan_status = QLabel("Nenhum scan iniciado."); self.scan_status.setWordWrap(True); layout.addWidget(self.scan_status)
        return page

    def _build_generic_controls(self) -> None:
        self.content_box = QGroupBox("Conteúdo"); content = QVBoxLayout(self.content_box); self.games_only = QCheckBox("Somente Games"); self.games_only.setChecked(True); content.addWidget(self.games_only); self.content_checks: dict[str, QCheckBox] = {}
        for key, text in (("bios", "BIOS"), ("educational", "Educational"), ("manuals", "Manuais"), ("magazines", "Revistas"), ("software", "Software / Applications"), ("demos", "Demos"), ("prototypes", "Prototypes / Betas"), ("unlicensed", "Unlicensed")):
            check = QCheckBox(text); self.content_checks[key] = check; content.addWidget(check)
        self.filter_layout.addWidget(self.content_box)
        self.region_box = QGroupBox("Clones / 1G1R"); region = QVBoxLayout(self.region_box); self.one_game_one_region = QCheckBox("Aplicar 1G1R — uma ROM por jogo/região"); self.one_game_one_region.setChecked(True); region.addWidget(self.one_game_one_region); region.addWidget(QLabel("Prioridade regional (ordem do perfil):")); self.region_list = QListWidget(); self.region_list.setDragDropMode(QListWidget.DragDropMode.InternalMove); region.addWidget(self.region_list); self.filter_layout.addWidget(self.region_box)
        self.version_box = QGroupBox("Versões / revisões"); v = QVBoxLayout(self.version_box); self.remove_previous = QCheckBox("Remover versões/revisões anteriores"); self.remove_previous.setChecked(True); v.addWidget(self.remove_previous); v.addWidget(QLabel("A regra mantém a revisão adequada conforme o DAT e as regras do perfil.")); self.filter_layout.addWidget(self.version_box)
        self.translation_box = QGroupBox("Traduções / DE-PARA"); t = QVBoxLayout(self.translation_box); self.include_translations = QCheckBox("Permitir traduções catalogadas / DE-PARA"); t.addWidget(self.include_translations); self.translation_policy = QComboBox(); self.translation_policy.addItem("Original primeiro; tradução somente se necessário", "original_then_translation"); self.translation_policy.addItem("Priorizar tradução", "translation_first"); self.translation_policy.addItem("Somente tradução", "translation_only"); t.addWidget(self.translation_policy); self.filter_layout.addWidget(self.translation_box)
        self.redump_box = QGroupBox("Redump — mídia óptica"); r = QVBoxLayout(self.redump_box); self.include_chd = QCheckBox("Aceitar CHD"); self.include_chd.setChecked(True); self.prefer_chd = QCheckBox("Priorizar CHD"); self.prefer_chd.setChecked(True); self.allow_cue_bin = QCheckBox("CUE/BIN como fallback"); self.allow_cue_bin.setChecked(True); self.convert_cue_bin = QCheckBox("Converter CUE/BIN para CHD via chdman.exe"); self.convert_cue_bin.setChecked(True); self.keep_cue_bin = QCheckBox("Manter CUE/BIN original"); self.keep_cue_bin.setChecked(True)
        for w in (self.include_chd, self.prefer_chd, self.allow_cue_bin, self.convert_cue_bin, self.keep_cue_bin): r.addWidget(w)
        self.filter_layout.addWidget(self.redump_box)
        self.wh_box = QGroupBox("WHLoader"); w = QVBoxLayout(self.wh_box); self.wh_games_only = QCheckBox("Somente Games (.lha)"); self.wh_games_only.setChecked(True); w.addWidget(self.wh_games_only); self.filter_layout.addWidget(self.wh_box)

    def _build_mame_controls(self) -> None:
        self.mame_box = QGroupBox("MAME — filtro baseado na V1"); layout = QVBoxLayout(self.mame_box)
        layout.addWidget(QLabel("Tipo de SET:")); self.mame_set_type = QComboBox(); self.mame_set_type.addItem("Split — padrão", "split"); self.mame_set_type.addItem("Non-Merged", "non_merged"); self.mame_set_type.addItem("Full-Merged", "full_merged"); layout.addWidget(self.mame_set_type)
        layout.addWidget(QLabel("Clones:")); self.mame_clone_policy = QComboBox(); self.mame_clone_policy.addItem("Com clones", "with_clones"); self.mame_clone_policy.addItem("Somente parents", "parents_only"); layout.addWidget(self.mame_clone_policy)
        self.mame_bios = QCheckBox("Incluir BIOS / sets de BIOS"); self.mame_devices = QCheckBox("Incluir Devices"); self.mame_chd = QCheckBox("Incluir CHDs / disks"); self.mame_chd.setChecked(True); self.mame_optional = QCheckBox("Incluir ROMs opcionais"); self.mame_optional.setChecked(True); self.mame_working = QCheckBox("Somente máquinas marcadas como working")
        for w in (self.mame_bios, self.mame_devices, self.mame_chd, self.mame_optional, self.mame_working): layout.addWidget(w)
        layout.addWidget(QLabel("Classificação: catlist.ini tem precedência conforme as regras V2; ListXML permanece preservado.")); self.mame_classification = QComboBox(); self.mame_classification.addItem("catlist.ini", "catlist"); self.mame_classification.addItem("ListXML", "listxml"); layout.addWidget(self.mame_classification)
        self.filter_layout.addWidget(self.mame_box)

    def _selected_item_data(self) -> tuple[str, str, str | None] | None:
        item = self.source_tree.currentItem()
        if item is None: return None
        data = item.data(0, Qt.ItemDataRole.UserRole)
        return tuple(data) if isinstance(data, (list, tuple)) and len(data) == 3 else None

    def _selection_changed(self) -> None:
        selected = self._selected_item_data()
        if selected is None: return
        source, system, dat_path = selected; self.selected_label.setText(f"{source}  ›  {system}"); self._selected_dat = Path(dat_path) if dat_path else None
        saved = self._load_saved_profile(source, system, dat_path); self._current_saved_profile = saved; self._load_profile(saved or self._new_default_profile(source, system, dat_path)); self._configure_source_controls(source)

    def _configure_source_controls(self, source: str) -> None:
        is_mame = source == "MAME"; is_wh = source == "WHLoader"; is_redump = source == "Redump"
        self.mame_box.setVisible(is_mame); self.region_box.setVisible(not is_mame and not is_wh); self.translation_box.setVisible(not is_mame and not is_wh); self.redump_box.setVisible(is_redump); self.wh_box.setVisible(is_wh); self.content_box.setTitle("MAME — categorias do catálogo" if is_mame else "Conteúdo")

    def _new_default_profile(self, source: str, system: str, dat_path: str | None) -> FilterProfileData:
        p = FilterProfileData(source=source, system=system, dat_path=dat_path)
        if source == "MAME": p.one_game_one_region = False
        if source == "WHLoader": p.one_game_one_region = False; p.remove_previous_versions = False
        return p

    def _load_profile(self, p: FilterProfileData) -> None:
        self.source_list.clear(); self.source_list.addItems(p.source_directories[:3]); self.recursive.setChecked(p.recursive); self.games_only.setChecked(p.games_only)
        for key, check in self.content_checks.items(): check.setChecked(bool(getattr(p, f"include_{key}")))
        self.one_game_one_region.setChecked(p.one_game_one_region); self.region_list.clear(); self.region_list.addItems(p.region_priority or list(self.REGION_DEFAULT)); self.remove_previous.setChecked(p.remove_previous_versions); self.include_translations.setChecked(p.include_translations); idx = self.translation_policy.findData(p.translation_policy); self.translation_policy.setCurrentIndex(max(0, idx)); self.include_chd.setChecked(p.include_chd); self.prefer_chd.setChecked(p.prefer_chd); self.allow_cue_bin.setChecked(p.allow_cue_bin); self.convert_cue_bin.setChecked(p.convert_cue_bin_to_chd); self.keep_cue_bin.setChecked(p.keep_cue_bin); self.wh_games_only.setChecked(p.whloader_games_only)
        self.mame_set_type.setCurrentIndex(max(0, self.mame_set_type.findData(p.mame_set_type))); self.mame_clone_policy.setCurrentIndex(max(0, self.mame_clone_policy.findData(p.mame_clone_policy))); self.mame_bios.setChecked(p.mame_include_bios); self.mame_devices.setChecked(p.mame_include_devices); self.mame_chd.setChecked(p.mame_include_chd); self.mame_optional.setChecked(p.mame_include_optional); self.mame_working.setChecked(p.mame_working_only); self.mame_classification.setCurrentIndex(max(0, self.mame_classification.findData(p.mame_classification_source)))

    def _current_profile(self) -> FilterProfileData | None:
        selected = self._selected_item_data()
        if selected is None: return None
        source, system, dat_path = selected
        return FilterProfileData(source=source, system=system, dat_path=dat_path, source_directories=[self.source_list.item(i).text() for i in range(self.source_list.count())], recursive=self.recursive.isChecked(), games_only=self.games_only.isChecked(), include_bios=self.content_checks["bios"].isChecked(), include_educational=self.content_checks["educational"].isChecked(), include_manuals=self.content_checks["manuals"].isChecked(), include_magazines=self.content_checks["magazines"].isChecked(), include_software=self.content_checks["software"].isChecked(), include_demos=self.content_checks["demos"].isChecked(), include_prototypes=self.content_checks["prototypes"].isChecked(), include_unlicensed=self.content_checks["unlicensed"].isChecked(), one_game_one_region=self.one_game_one_region.isChecked(), region_priority=[self.region_list.item(i).text() for i in range(self.region_list.count())], remove_previous_versions=self.remove_previous.isChecked(), include_translations=self.include_translations.isChecked(), translation_policy=str(self.translation_policy.currentData()), include_chd=self.include_chd.isChecked(), prefer_chd=self.prefer_chd.isChecked(), allow_cue_bin=self.allow_cue_bin.isChecked(), convert_cue_bin_to_chd=self.convert_cue_bin.isChecked(), keep_cue_bin=self.keep_cue_bin.isChecked(), whloader_games_only=self.wh_games_only.isChecked(), mame_set_type=str(self.mame_set_type.currentData()), mame_clone_policy=str(self.mame_clone_policy.currentData()), mame_include_bios=self.mame_bios.isChecked(), mame_include_devices=self.mame_devices.isChecked(), mame_include_chd=self.mame_chd.isChecked(), mame_include_optional=self.mame_optional.isChecked(), mame_working_only=self.mame_working.isChecked(), mame_classification_source=str(self.mame_classification.currentData()))

    def _load_saved_profile(self, source: str, system: str, dat_path: str | None) -> FilterProfileData | None:
        try: data = json.loads(self._profiles_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError): return None
        if not isinstance(data, list): return None
        for raw in data:
            if isinstance(raw, dict) and raw.get("source") == source and raw.get("system") == system and raw.get("dat_path") == dat_path:
                try: return FilterProfileData(**raw)
                except TypeError: return None
        return None

    def _save_profile(self) -> FilterProfileData | None:
        p = self._current_profile()
        if p is None: QMessageBox.information(self, "Filtros", "Selecione um sistema antes de salvar."); return None
        try: existing = json.loads(self._profiles_path.read_text(encoding="utf-8")) if self._profiles_path.is_file() else []
        except (OSError, ValueError, TypeError): existing = []
        if not isinstance(existing, list): existing = []
        existing = [x for x in existing if not isinstance(x, dict) or (x.get("source"), x.get("system"), x.get("dat_path")) != (p.source, p.system, p.dat_path)]
        existing.append(asdict(p)); self._profiles_path.parent.mkdir(parents=True, exist_ok=True); self._profiles_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8"); self._current_saved_profile = p; self.scan_status.setText(f"Perfil salvo: {p.source} › {p.system}"); return p

    def _save_and_scan(self) -> None:
        p = self._save_profile()
        if p is None: return
        self.scan_status.setText(f"Perfil salvo. Scan preparado para {p.source} › {p.system}."); self.scan_requested.emit(p)

    def _reset_defaults(self) -> None:
        selected = self._selected_item_data()
        if selected: self._load_profile(self._new_default_profile(*selected)); self.scan_status.setText("Padrões restaurados; salve novamente para persistir.")

    def _add_source_directory(self) -> None:
        if self.source_list.count() >= 3: QMessageBox.information(self, "Fontes", "Máximo de 3 diretórios por perfil."); return
        directory = QFileDialog.getExistingDirectory(self, "Diretório de origem", str(Path.home()))
        if directory:
            path = str(Path(directory).resolve())
            if not any(self.source_list.item(i).text() == path for i in range(self.source_list.count())): self.source_list.addItem(path)

    def _remove_source_directory(self) -> None:
        row = self.source_list.currentRow()
        if row >= 0: self.source_list.takeItem(row)

    def refresh(self) -> None:
        self.source_tree.clear(); self._add_source_item("MAME", "MAME", None); self._add_dat_entries("No-Intro", data_root() / "sources" / "no_intro" / "dats"); self._add_dat_entries("Redump", data_root() / "sources" / "redump" / "dats"); self._add_source_item("WHLoader", "WHLoader", None); self._add_source_item("C64", "Commodore C64 - Games", None)
        if self.source_tree.topLevelItemCount(): self.source_tree.setCurrentItem(self.source_tree.topLevelItem(0))

    def _add_source_item(self, source: str, system: str, dat_path: str | None) -> None:
        parent = next((self.source_tree.topLevelItem(i) for i in range(self.source_tree.topLevelItemCount()) if self.source_tree.topLevelItem(i).text(0) == source), None)
        if parent is None: parent = QTreeWidgetItem([source]); parent.setData(0, Qt.ItemDataRole.UserRole, (source, system, dat_path)); self.source_tree.addTopLevelItem(parent)
        else: child = QTreeWidgetItem([system]); child.setData(0, Qt.ItemDataRole.UserRole, (source, system, dat_path)); parent.addChild(child); parent.setExpanded(True)

    def _add_dat_entries(self, source: str, directory: Path) -> None:
        if not directory.is_dir(): self._add_source_item(source, "Nenhum DAT baixado", None); return
        paths = sorted(directory.glob("*.dat"), key=lambda p: p.name.casefold())
        if not paths: self._add_source_item(source, "Nenhum DAT baixado", None); return
        parent = QTreeWidgetItem([source]); parent.setData(0, Qt.ItemDataRole.UserRole, (source, source, None)); self.source_tree.addTopLevelItem(parent)
        for path in paths:
            name = re.sub(r"\s+", " ", path.stem).strip(); child = QTreeWidgetItem([name]); child.setData(0, Qt.ItemDataRole.UserRole, (source, name, str(path))); parent.addChild(child)
        parent.setExpanded(True)

    def selected_profile(self) -> FilterProfileData | None:
        return self._current_profile()


__all__ = ["FilterProfileData", "FilterProfilesPage"]
