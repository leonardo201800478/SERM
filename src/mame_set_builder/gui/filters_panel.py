"""
Painel de controles de filtro – com prevenção de recursão.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QCheckBox, QComboBox,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QHBoxLayout, QSpinBox, QLineEdit
)
from PyQt6.QtCore import pyqtSignal, Qt

from ..domain.set_profile import SetProfile, EmulationStatus, SetType
from ..filtering.profiles import arcade_only, all_systems, consoles_only, computers_only, mechanical_only

class FiltersPanel(QWidget):
    # Sinal emitido quando o perfil muda (para ser capturado pela main window)
    profile_changed = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self._updating = False  # flag para evitar recursão
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # --- Seleção de Perfil Rápido ---
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
        
        # --- Categorias ---
        group_cat = QGroupBox("Categorias")
        vbox_cat = QVBoxLayout(group_cat)
        self.category_list = QListWidget()
        self.category_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        categories = [
            "Arcade", "Console", "Computer", "Portable",
            "Pinball", "Fruit Machine", "Casino", "Gambling",
            "Quiz", "Mahjong", "Tabletop", "Electromechanical",
            "Mechanical", "Device", "BIOS"
        ]
        for cat in categories:
            item = QListWidgetItem(cat)
            self.category_list.addItem(item)
        vbox_cat.addWidget(self.category_list)
        layout.addWidget(group_cat)
        
        # --- Status de Emulação ---
        group_emu = QGroupBox("Emulação")
        vbox_emu = QVBoxLayout(group_emu)
        self.emu_combo = QComboBox()
        self.emu_combo.addItems(["GOOD", "IMPERFECT", "PRELIMINARY", "ALL"])
        vbox_emu.addWidget(self.emu_combo)
        layout.addWidget(group_emu)
        
        # --- Tipo de Set ---
        group_set = QGroupBox("Tipo de Set")
        vbox_set = QVBoxLayout(group_set)
        self.set_combo = QComboBox()
        self.set_combo.addItems(["Non-Merged", "Split", "Merged"])
        vbox_set.addWidget(self.set_combo)
        layout.addWidget(group_set)
        
        # --- Opções ---
        group_opts = QGroupBox("Opções")
        vbox_opts = QVBoxLayout(group_opts)
        self.clone_check = QCheckBox("Incluir Clones")
        self.clone_check.setChecked(True)
        vbox_opts.addWidget(self.clone_check)
        self.bios_check = QCheckBox("Manter BIOS")
        self.bios_check.setChecked(True)
        vbox_opts.addWidget(self.bios_check)
        self.device_check = QCheckBox("Manter Devices")
        self.device_check.setChecked(True)
        vbox_opts.addWidget(self.device_check)
        self.sample_check = QCheckBox("Manter Samples")
        self.sample_check.setChecked(False)
        vbox_opts.addWidget(self.sample_check)
        self.chd_check = QCheckBox("Manter CHDs")
        self.chd_check.setChecked(True)
        vbox_opts.addWidget(self.chd_check)
        layout.addWidget(group_opts)
        
        # --- Contador ---
        self.count_label = QLabel("Máquinas: 0")
        layout.addWidget(self.count_label)
        
        # --- Botão Aplicar ---
        self.apply_btn = QPushButton("Aplicar Filtros")
        layout.addWidget(self.apply_btn)
        
        layout.addStretch()
    
    def _connect_signals(self):
        """Conecta todos os sinais aos slots, usando bloqueio para evitar recursão."""
        self.profile_combo.currentTextChanged.connect(self._on_profile_combo)
        self.category_list.itemSelectionChanged.connect(self._on_any_change)
        self.emu_combo.currentTextChanged.connect(self._on_any_change)
        self.set_combo.currentTextChanged.connect(self._on_set_change)
        self.clone_check.stateChanged.connect(self._on_any_change)
        self.bios_check.stateChanged.connect(self._on_any_change)
        self.device_check.stateChanged.connect(self._on_any_change)
        self.sample_check.stateChanged.connect(self._on_any_change)
        self.chd_check.stateChanged.connect(self._on_any_change)
        self.apply_btn.clicked.connect(self._apply)
    
    def _on_profile_combo(self, text: str):
        """Carrega perfil rápido e aplica."""
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
    
    def _on_set_change(self):
        """Atualiza estado do checkbox de clones para Merged."""
        if self.set_combo.currentText() == "Merged":
            self.clone_check.setChecked(True)
            self.clone_check.setEnabled(False)
        else:
            self.clone_check.setEnabled(True)
        self._on_any_change()
    
    def _on_any_change(self):
        """Slot genérico para qualquer mudança que exija reaplicação."""
        if not self._updating:
            self._apply()
    
    def _apply(self):
        """Dispara a aplicação dos filtros (emite sinal)."""
        if self._updating:
            return
        profile = self.get_profile()
        self.profile_changed.emit(profile)
    
    def get_profile(self) -> SetProfile:
        """Constrói o perfil a partir dos controles."""
        # Categorias selecionadas
        categories = [item.text() for item in self.category_list.selectedItems()]
        
        # Status de emulação
        emu_text = self.emu_combo.currentText().upper()
        emu_map = {
            "GOOD": EmulationStatus.GOOD,
            "IMPERFECT": EmulationStatus.IMPERFECT,
            "PRELIMINARY": EmulationStatus.PRELIMINARY,
            "ALL": EmulationStatus.ALL,
        }
        emu_status = emu_map.get(emu_text, EmulationStatus.PRELIMINARY)
        
        # Tipo de Set
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
            emulation_status=emu_status,
            set_type=set_type,
            include_clones=self.clone_check.isChecked(),
            keep_bios=self.bios_check.isChecked(),
            keep_devices=self.device_check.isChecked(),
            keep_samples=self.sample_check.isChecked(),
            keep_chds=self.chd_check.isChecked(),
        )
    
    def set_profile(self, profile: SetProfile):
        """Atualiza os controles a partir de um perfil, sem disparar eventos."""
        self._updating = True
        try:
            # Selecionar categorias
            self.category_list.clearSelection()
            categories = set(profile.categories)
            for i in range(self.category_list.count()):
                item = self.category_list.item(i)
                if item.text() in categories:
                    item.setSelected(True)
            
            # Status de emulação
            emu_map = {
                EmulationStatus.GOOD: "GOOD",
                EmulationStatus.IMPERFECT: "IMPERFECT",
                EmulationStatus.PRELIMINARY: "PRELIMINARY",
                EmulationStatus.ALL: "ALL",
            }
            idx = self.emu_combo.findText(emu_map.get(profile.emulation_status, "PRELIMINARY"))
            if idx >= 0:
                self.emu_combo.setCurrentIndex(idx)
            
            # Tipo de Set
            set_map = {
                SetType.NON_MERGED: "Non-Merged",
                SetType.SPLIT: "Split",
                SetType.MERGED: "Merged",
            }
            idx = self.set_combo.findText(set_map.get(profile.set_type, "Split"))
            if idx >= 0:
                self.set_combo.setCurrentIndex(idx)
            
            # Opções
            self.clone_check.setChecked(profile.include_clones)
            self.bios_check.setChecked(profile.keep_bios)
            self.device_check.setChecked(profile.keep_devices)
            self.sample_check.setChecked(profile.keep_samples)
            self.chd_check.setChecked(profile.keep_chds)
        finally:
            self._updating = False
    
    def update_count(self, count: int):
        """Atualiza o rótulo de contagem."""
        self.count_label.setText(f"Máquinas: {count}")