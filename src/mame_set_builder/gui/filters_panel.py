"""
Painel de controles de filtro – com prevenção de recursão e novos filtros.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QCheckBox, QComboBox,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QHBoxLayout
)
from PyQt6.QtCore import pyqtSignal, Qt

from ..domain.set_profile import SetProfile, EmulationStatus, SetType, RomSetType
from ..filtering.profiles import arcade_only, all_systems, consoles_only, computers_only, mechanical_only

class FiltersPanel(QWidget):
    profile_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self._updating = False
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Perfis Rápidos
        group = QGroupBox("Perfis Rápidos")
        vbox = QVBoxLayout(group)
        self.profile_combo = QComboBox()
        self.profile_combo.addItems([
            "Arcade Only",
            "All Systems",
            "Consoles & Portables",
            "Computers Only",
            "Mechanical"
        ])
        vbox.addWidget(self.profile_combo)
        layout.addWidget(group)

        # --- Tipo de ROM set ---
        group_rom_type = QGroupBox("Tipo de ROM set")
        vbox_rom_type = QVBoxLayout(group_rom_type)
        self.rom_type_combo = QComboBox()
        self.rom_type_combo.addItems(["All", "Parent", "Clone"])
        vbox_rom_type.addWidget(self.rom_type_combo)
        layout.addWidget(group_rom_type)

        # --- Filtros de categoria (checkboxes) ---
        group_cat = QGroupBox("Filtros de Categoria")
        vbox_cat = QVBoxLayout(group_cat)
        self.cat_checkboxes = {}
        cat_names = ["Arcade", "System", "Bios", "Device", "Mechanical",
                     "Casino", "Mahjong", "Mature", "Screenless", "Free to play"]
        for cat in cat_names:
            cb = QCheckBox(cat)
            cb.setChecked(False)
            vbox_cat.addWidget(cb)
            self.cat_checkboxes[cat] = cb
        layout.addWidget(group_cat)

        # --- Filtros de recursos ---
        group_res = QGroupBox("Recursos")
        vbox_res = QVBoxLayout(group_res)
        self.chd_check = QCheckBox("Use CHD")
        self.sample_check = QCheckBox("Use sample")
        self.bios_check = QCheckBox("Use bios")
        vbox_res.addWidget(self.chd_check)
        vbox_res.addWidget(self.sample_check)
        vbox_res.addWidget(self.bios_check)
        layout.addWidget(group_res)

        # --- MameCab only ---
        self.mamecab_only_check = QCheckBox("MameCab only")
        self.mamecab_only_check.setToolTip("Se ativado, restringe o uso de alguns filtros.")
        layout.addWidget(self.mamecab_only_check)

        # Aviso
        self.warning_label = QLabel("Aviso: Você precisa desmarcar 'MameCab only' para usar todos os filtros.")
        self.warning_label.setStyleSheet("color: orange;")
        self.warning_label.setVisible(False)
        layout.addWidget(self.warning_label)

        # --- Status de Emulação (já existente) ---
        group_emu = QGroupBox("Emulação")
        vbox_emu = QVBoxLayout(group_emu)
        self.emu_combo = QComboBox()
        self.emu_combo.addItems(["GOOD", "IMPERFECT", "PRELIMINARY", "ALL"])
        vbox_emu.addWidget(self.emu_combo)
        layout.addWidget(group_emu)

        # --- Tipo de Set (já existente) ---
        group_set = QGroupBox("Tipo de Set")
        vbox_set = QVBoxLayout(group_set)
        self.set_combo = QComboBox()
        self.set_combo.addItems(["Non-Merged", "Split", "Merged"])
        vbox_set.addWidget(self.set_combo)
        layout.addWidget(group_set)

        # --- Opções (já existente) ---
        group_opts = QGroupBox("Opções")
        vbox_opts = QVBoxLayout(group_opts)
        self.clone_check = QCheckBox("Incluir Clones")
        self.clone_check.setChecked(True)
        vbox_opts.addWidget(self.clone_check)
        self.bios_keep_check = QCheckBox("Manter BIOS")
        self.bios_keep_check.setChecked(True)
        vbox_opts.addWidget(self.bios_keep_check)
        self.device_keep_check = QCheckBox("Manter Devices")
        self.device_keep_check.setChecked(True)
        vbox_opts.addWidget(self.device_keep_check)
        self.sample_keep_check = QCheckBox("Manter Samples")
        self.sample_keep_check.setChecked(False)
        vbox_opts.addWidget(self.sample_keep_check)
        self.chd_keep_check = QCheckBox("Manter CHDs")
        self.chd_keep_check.setChecked(True)
        vbox_opts.addWidget(self.chd_keep_check)
        layout.addWidget(group_opts)

        # Contador e botão Aplicar
        self.count_label = QLabel("Máquinas: 0")
        layout.addWidget(self.count_label)
        self.apply_btn = QPushButton("Aplicar Filtros")
        layout.addWidget(self.apply_btn)

        layout.addStretch()

    def _connect_signals(self):
        self.profile_combo.currentTextChanged.connect(self._on_profile_combo)
        self.rom_type_combo.currentTextChanged.connect(self._on_any_change)
        self.mamecab_only_check.stateChanged.connect(self._on_mamecab_changed)
        for cb in self.cat_checkboxes.values():
            cb.stateChanged.connect(self._on_any_change)
        self.chd_check.stateChanged.connect(self._on_any_change)
        self.sample_check.stateChanged.connect(self._on_any_change)
        self.bios_check.stateChanged.connect(self._on_any_change)
        self.emu_combo.currentTextChanged.connect(self._on_any_change)
        self.set_combo.currentTextChanged.connect(self._on_set_change)
        self.clone_check.stateChanged.connect(self._on_any_change)
        self.bios_keep_check.stateChanged.connect(self._on_any_change)
        self.device_keep_check.stateChanged.connect(self._on_any_change)
        self.sample_keep_check.stateChanged.connect(self._on_any_change)
        self.chd_keep_check.stateChanged.connect(self._on_any_change)
        self.apply_btn.clicked.connect(self._apply)

    def _on_mamecab_changed(self):
        self.warning_label.setVisible(self.mamecab_only_check.isChecked())
        self._on_any_change()

    def _on_set_change(self):
        if self.set_combo.currentText() == "Merged":
            self.clone_check.setChecked(True)
            self.clone_check.setEnabled(False)
        else:
            self.clone_check.setEnabled(True)
        self._on_any_change()

    def _on_any_change(self):
        if not self._updating:
            self._apply()

    def _on_profile_combo(self, text: str):
        profiles = {
            "Arcade Only": arcade_only,
            "All Systems": all_systems,
            "Consoles & Portables": consoles_only,
            "Computers Only": computers_only,
            "Mechanical": mechanical_only,
        }
        if text in profiles:
            profile = profiles[text]()
            self.set_profile(profile)
            self._apply()

    def _apply(self):
        if self._updating:
            return
        profile = self.get_profile()
        self.profile_changed.emit(profile)

    def get_profile(self) -> SetProfile:
        categories = []
        for cat, cb in self.cat_checkboxes.items():
            if cb.isChecked():
                categories.append(cat)

        rom_type_map = {"All": RomSetType.ALL, "Parent": RomSetType.PARENT, "Clone": RomSetType.CLONE}
        rom_type = rom_type_map.get(self.rom_type_combo.currentText(), RomSetType.ALL)

        emu_text = self.emu_combo.currentText().upper()
        emu_map = {
            "GOOD": EmulationStatus.GOOD,
            "IMPERFECT": EmulationStatus.IMPERFECT,
            "PRELIMINARY": EmulationStatus.PRELIMINARY,
            "ALL": EmulationStatus.ALL,
        }
        emu_status = emu_map.get(emu_text, EmulationStatus.PRELIMINARY)

        set_text = self.set_combo.currentText().lower().replace("-", "_")
        set_map = {
            "non_merged": SetType.NON_MERGED,
            "split": SetType.SPLIT,
            "merged": SetType.MERGED,
        }
        set_type = set_map.get(set_text, SetType.SPLIT)

        return SetProfile(
            name="Custom",
            categories=categories,
            rom_set_type=rom_type,
            use_chd=self.chd_check.isChecked(),
            use_sample=self.sample_check.isChecked(),
            use_bios=self.bios_check.isChecked(),
            mamecab_only=self.mamecab_only_check.isChecked(),
            emulation_status=emu_status,
            set_type=set_type,
            include_clones=self.clone_check.isChecked(),
            keep_bios=self.bios_keep_check.isChecked(),
            keep_devices=self.device_keep_check.isChecked(),
            keep_samples=self.sample_keep_check.isChecked(),
            keep_chds=self.chd_keep_check.isChecked(),
        )

    def set_profile(self, profile: SetProfile):
        self._updating = True
        try:
            # Categorias
            for cat, cb in self.cat_checkboxes.items():
                cb.setChecked(cat in profile.categories)

            # Tipo de ROM set
            rom_type_map_inv = {RomSetType.ALL: "All", RomSetType.PARENT: "Parent", RomSetType.CLONE: "Clone"}
            idx = self.rom_type_combo.findText(rom_type_map_inv.get(profile.rom_set_type, "All"))
            if idx >= 0:
                self.rom_type_combo.setCurrentIndex(idx)

            # Recursos
            self.chd_check.setChecked(profile.use_chd)
            self.sample_check.setChecked(profile.use_sample)
            self.bios_check.setChecked(profile.use_bios)
            self.mamecab_only_check.setChecked(profile.mamecab_only)

            # Emulação
            emu_map_inv = {
                EmulationStatus.GOOD: "GOOD",
                EmulationStatus.IMPERFECT: "IMPERFECT",
                EmulationStatus.PRELIMINARY: "PRELIMINARY",
                EmulationStatus.ALL: "ALL",
            }
            idx = self.emu_combo.findText(emu_map_inv.get(profile.emulation_status, "PRELIMINARY"))
            if idx >= 0:
                self.emu_combo.setCurrentIndex(idx)

            # Tipo de Set
            set_map_inv = {
                SetType.NON_MERGED: "Non-Merged",
                SetType.SPLIT: "Split",
                SetType.MERGED: "Merged",
            }
            idx = self.set_combo.findText(set_map_inv.get(profile.set_type, "Split"))
            if idx >= 0:
                self.set_combo.setCurrentIndex(idx)

            # Opções
            self.clone_check.setChecked(profile.include_clones)
            self.bios_keep_check.setChecked(profile.keep_bios)
            self.device_keep_check.setChecked(profile.keep_devices)
            self.sample_keep_check.setChecked(profile.keep_samples)
            self.chd_keep_check.setChecked(profile.keep_chds)

            self.warning_label.setVisible(profile.mamecab_only)
        finally:
            self._updating = False

    def update_count(self, count: int):
        self.count_label.setText(f"Máquinas: {count}")