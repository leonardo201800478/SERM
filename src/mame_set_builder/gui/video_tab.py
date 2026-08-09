import os
import glob
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QCheckBox, QSlider, QPushButton, QMessageBox,
    QScrollArea
)
from PyQt6.QtCore import Qt

from .settings import Settings
from .mame_ini_parser import MameIniParser

logger = logging.getLogger(__name__)

class VideoTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.config = Settings.load()
        self.ini_path = None
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        vbox = QVBoxLayout(content)

        # --- Driver de Vídeo ---
        group_driver = QGroupBox("Driver de Vídeo")
        driver_layout = QVBoxLayout(group_driver)

        self.video_combo = QComboBox()
        # Opções de driver (comuns)
        drivers = ["bgfx", "d3d", "opengl", "gdi", "soft", "accel", "none"]
        self.video_combo.addItems(drivers)
        self.video_combo.setToolTip("Seleciona o subsistema de vídeo. bgfx é o mais moderno e recomendado.")
        driver_layout.addWidget(self.video_combo)

        vbox.addWidget(group_driver)

        # --- Filtro BGFX ---
        group_bgfx = QGroupBox("BGFX Screen Chains")
        bgfx_layout = QVBoxLayout(group_bgfx)

        # Lista de chains carregadas dinamicamente
        chain_layout = QHBoxLayout()
        chain_layout.addWidget(QLabel("Cadeia(s):"))
        self.chain_combo = QComboBox()
        self.chain_combo.setEditable(True)
        self.chain_combo.setToolTip("Selecione uma ou mais chains BGFX (separadas por vírgula).")
        chain_layout.addWidget(self.chain_combo, 1)
        self.refresh_chains_btn = QPushButton("Atualizar")
        self.refresh_chains_btn.clicked.connect(self._refresh_chains)
        chain_layout.addWidget(self.refresh_chains_btn)
        bgfx_layout.addLayout(chain_layout)

        # Shadow Mask e LUT
        shadow_layout = QHBoxLayout()
        shadow_layout.addWidget(QLabel("Shadow Mask:"))
        self.shadow_combo = QComboBox()
        self.shadow_combo.setEditable(True)
        self.shadow_combo.addItems(["slot-mask.png", "aperture.png", "shadow-mask.png"])
        shadow_layout.addWidget(self.shadow_combo, 1)
        bgfx_layout.addLayout(shadow_layout)

        lut_layout = QHBoxLayout()
        lut_layout.addWidget(QLabel("LUT Texture:"))
        self.lut_combo = QComboBox()
        self.lut_combo.setEditable(True)
        self.lut_combo.addItems(["lut-default.png"])
        lut_layout.addWidget(self.lut_combo, 1)
        bgfx_layout.addLayout(lut_layout)

        vbox.addWidget(group_bgfx)

        # --- Effect (PNG overlay) ---
        group_effect = QGroupBox("Effect (PNG Overlay)")
        effect_layout = QHBoxLayout(group_effect)
        effect_layout.addWidget(QLabel("Arquivo PNG:"))
        self.effect_combo = QComboBox()
        self.effect_combo.setEditable(True)
        self.effect_combo.setToolTip("Selecione um arquivo PNG para overlay (ex.: scanlines.png).")
        effect_layout.addWidget(self.effect_combo, 1)
        self.refresh_effect_btn = QPushButton("Atualizar")
        self.refresh_effect_btn.clicked.connect(self._refresh_effects)
        effect_layout.addWidget(self.refresh_effect_btn)
        vbox.addWidget(group_effect)

        # --- Opções de filtro ---
        group_filter = QGroupBox("Opções de Filtro")
        filter_layout = QVBoxLayout(group_filter)

        self.filter_check = QCheckBox("Filtro Bilinear")
        self.filter_check.setChecked(True)
        self.filter_check.setToolTip("Aplica filtro bilinear (suavização) à imagem.")
        filter_layout.addWidget(self.filter_check)

        self.keepaspect_check = QCheckBox("Manter Proporção (aspect)")
        self.keepaspect_check.setChecked(True)
        self.keepaspect_check.setToolTip("Mantém a proporção original da tela.")
        filter_layout.addWidget(self.keepaspect_check)

        self.unevenstretch_check = QCheckBox("Permitir Esticamento Não-Inteiro")
        self.unevenstretch_check.setChecked(True)
        self.unevenstretch_check.setToolTip("Permite escalonamento não-inteiro para preencher a tela.")
        filter_layout.addWidget(self.unevenstretch_check)

        # Prescale
        prescale_layout = QHBoxLayout()
        prescale_layout.addWidget(QLabel("Prescale:"))
        self.prescale_slider = QSlider(Qt.Orientation.Horizontal)
        self.prescale_slider.setMinimum(1)
        self.prescale_slider.setMaximum(8)
        self.prescale_slider.setValue(1)
        self.prescale_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.prescale_slider.setTickInterval(1)
        self.prescale_label = QLabel("1")
        self.prescale_slider.valueChanged.connect(lambda v: self.prescale_label.setText(str(v)))
        prescale_layout.addWidget(self.prescale_slider)
        prescale_layout.addWidget(self.prescale_label)
        filter_layout.addLayout(prescale_layout)

        vbox.addWidget(group_filter)

        # --- Botão Salvar ---
        save_btn = QPushButton("Salvar Configurações de Vídeo")
        save_btn.clicked.connect(self._save_video_config)
        vbox.addWidget(save_btn)

        vbox.addStretch()

    def _load_config(self):
        """Carrega configurações atuais e preenche campos."""
        config = self.config
        # Preencher combos
        self.video_combo.setCurrentText(config.get("video", "bgfx"))
        self.chain_combo.setEditText(config.get("bgfx_screen_chains", "default"))
        self.shadow_combo.setEditText(config.get("bgfx_shadow_mask", "slot-mask.png"))
        self.lut_combo.setEditText(config.get("bgfx_lut", "lut-default.png"))
        self.effect_combo.setEditText(config.get("effect", "none"))
        self.filter_check.setChecked(config.get("filter", "1") == "1")
        self.keepaspect_check.setChecked(config.get("keepaspect", "1") == "1")
        self.unevenstretch_check.setChecked(config.get("unevenstretch", "1") == "1")
        prescale_val = int(config.get("prescale", "1"))
        self.prescale_slider.setValue(prescale_val)
        self.prescale_label.setText(str(prescale_val))

    def _refresh_chains(self):
        """Lista arquivos .json em bgfx/chains/ e preenche o combo."""
        exe_path = self.config.get("mame_executable", "")
        if not exe_path:
            QMessageBox.warning(self, "Aviso", "Configure o executável do MAME primeiro.")
            return
        mame_dir = Path(exe_path).parent
        chains_dir = mame_dir / "bgfx" / "chains"
        if not chains_dir.exists():
            QMessageBox.warning(self, "Aviso", f"Diretório de chains não encontrado: {chains_dir}")
            return

        # Lista arquivos .json (incluindo subpastas)
        json_files = []
        for root, _, files in os.walk(chains_dir):
            for f in files:
                if f.endswith(".json"):
                    rel_path = Path(root).relative_to(chains_dir)
                    if str(rel_path) == ".":
                        json_files.append(f)
                    else:
                        json_files.append(str(rel_path / f))

        # Preencher combo
        self.chain_combo.clear()
        self.chain_combo.addItems(sorted(json_files))
        # Tentar restaurar o valor anterior
        current = self.chain_combo.currentText()
        if current in json_files:
            self.chain_combo.setCurrentText(current)

    def _refresh_effects(self):
        """Lista arquivos .png em artwork/ e preenche o combo."""
        exe_path = self.config.get("mame_executable", "")
        if not exe_path:
            QMessageBox.warning(self, "Aviso", "Configure o executável do MAME primeiro.")
            return
        mame_dir = Path(exe_path).parent
        artwork_dir = mame_dir / "artwork"
        if not artwork_dir.exists():
            QMessageBox.warning(self, "Aviso", f"Diretório de artwork não encontrado: {artwork_dir}")
            return

        # Lista arquivos .png
        png_files = []
        for root, _, files in os.walk(artwork_dir):
            for f in files:
                if f.lower().endswith(".png"):
                    rel_path = Path(root).relative_to(artwork_dir)
                    if str(rel_path) == ".":
                        png_files.append(f)
                    else:
                        png_files.append(str(rel_path / f))

        self.effect_combo.clear()
        self.effect_combo.addItem("none")
        self.effect_combo.addItems(sorted(png_files))
        # Tentar restaurar valor anterior
        current = self.effect_combo.currentText()
        if current in png_files or current == "none":
            self.effect_combo.setCurrentText(current)

    def _save_video_config(self):
        """Salva configurações de vídeo no mame.ini."""
        if not self.ini_path or not self.ini_path.exists():
            # Tenta localizar o mame.ini
            exe_path = self.config.get("mame_executable", "")
            if exe_path:
                self.ini_path = MameIniParser.find_ini(Path(exe_path))
            if not self.ini_path or not self.ini_path.exists():
                QMessageBox.warning(self, "Erro", "Arquivo mame.ini não encontrado.")
                return

        config = {
            "video": self.video_combo.currentText(),
            "bgfx_screen_chains": self.chain_combo.currentText().strip(),
            "bgfx_shadow_mask": self.shadow_combo.currentText().strip(),
            "bgfx_lut": self.lut_combo.currentText().strip(),
            "effect": self.effect_combo.currentText().strip(),
            "filter": "1" if self.filter_check.isChecked() else "0",
            "keepaspect": "1" if self.keepaspect_check.isChecked() else "0",
            "unevenstretch": "1" if self.unevenstretch_check.isChecked() else "0",
            "prescale": str(self.prescale_slider.value()),
        }

        # Ler o conteúdo original do mame.ini para preservar comentários
        try:
            with open(self.ini_path, 'r', encoding='utf-8-sig') as f:
                original_lines = f.readlines()
        except:
            original_lines = None

        # Salvar usando o parser que preserva estrutura
        MameIniParser.save(self.ini_path, config, original_lines)
        QMessageBox.information(self, "Sucesso", f"Configurações de vídeo salvas em {self.ini_path}")