import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QComboBox, QCheckBox, QSlider, QPushButton, QMessageBox,
    QScrollArea, QLineEdit
)
from PyQt6.QtCore import Qt

from .settings import Settings
from .mame_ini_parser import MameIniParser

logger = logging.getLogger(__name__)

class ShaderTab(QWidget):
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

        # --- HLSL (Windows) ---
        group_hlsl = QGroupBox("HLSL (Direct3D)")
        hlsl_layout = QVBoxLayout(group_hlsl)

        self.hlsl_enable_check = QCheckBox("Ativar HLSL")
        self.hlsl_enable_check.setToolTip("Ativa efeitos HLSL (requer video=d3d).")
        hlsl_layout.addWidget(self.hlsl_enable_check)

        # Path HLSL
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("HLSL Path:"))
        self.hlsl_path_edit = QLineEdit()
        self.hlsl_path_edit.setPlaceholderText("hlsl")
        path_layout.addWidget(self.hlsl_path_edit)
        hlsl_layout.addLayout(path_layout)

        # Shadow Mask Texture
        shadow_layout = QHBoxLayout()
        shadow_layout.addWidget(QLabel("Shadow Mask Texture:"))
        self.hlsl_shadow_combo = QComboBox()
        self.hlsl_shadow_combo.setEditable(True)
        self.hlsl_shadow_combo.addItems(["shadow-mask.png", "aperture.png", "slot-mask.png"])
        shadow_layout.addWidget(self.hlsl_shadow_combo)
        hlsl_layout.addLayout(shadow_layout)

        # Sliders
        self._add_slider(hlsl_layout, "Scanline Alpha", "scanline_alpha", 0, 100, 25)
        self._add_slider(hlsl_layout, "Bloom Scale", "bloom_scale", 0, 100, 0)
        self._add_slider(hlsl_layout, "Shadow Mask Alpha", "shadow_mask_alpha", 0, 100, 15)
        self._add_slider(hlsl_layout, "Defocus X", "defocus_x", 0, 100, 0)
        self._add_slider(hlsl_layout, "Defocus Y", "defocus_y", 0, 100, 0)

        # YIQ
        self.hlsl_yiq_check = QCheckBox("Ativar YIQ (NTSC)")
        hlsl_layout.addWidget(self.hlsl_yiq_check)

        # Vector settings
        hlsl_layout.addWidget(QLabel("Configurações Vetoriais:"))
        self._add_slider(hlsl_layout, "Beam Width Min", "beam_width_min", 0, 200, 100, divisor=100)
        self._add_slider(hlsl_layout, "Beam Width Max", "beam_width_max", 0, 200, 100, divisor=100)
        self._add_slider(hlsl_layout, "Flicker", "flicker", 0, 100, 0)

        vbox.addWidget(group_hlsl)

        # --- GLSL (OpenGL) ---
        group_glsl = QGroupBox("GLSL (OpenGL)")
        glsl_layout = QVBoxLayout(group_glsl)

        self.glsl_enable_check = QCheckBox("Ativar GLSL")
        self.glsl_enable_check.setToolTip("Ativa efeitos GLSL (requer video=opengl).")
        glsl_layout.addWidget(self.glsl_enable_check)

        self.glsl_filter_check = QCheckBox("Filtro GLSL")
        glsl_layout.addWidget(self.glsl_filter_check)

        # Shader selection (simplificado, permitir texto livre)
        shader_layout = QHBoxLayout()
        shader_layout.addWidget(QLabel("Shader MAME0:"))
        self.glsl_shader_edit = QLineEdit()
        self.glsl_shader_edit.setPlaceholderText("none")
        shader_layout.addWidget(self.glsl_shader_edit)
        glsl_layout.addLayout(shader_layout)

        # Mais shaders podem ser adicionados conforme necessidade

        vbox.addWidget(group_glsl)

        # --- Botão Salvar ---
        save_btn = QPushButton("Salvar Configurações de Efeitos")
        save_btn.clicked.connect(self._save_shader_config)
        vbox.addWidget(save_btn)

        vbox.addStretch()

    def _add_slider(self, parent_layout, label_text, config_key, min_val, max_val, default_val, divisor=1):
        """Adiciona um slider com label e valor."""
        layout = QHBoxLayout()
        layout.addWidget(QLabel(f"{label_text}:"))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default_val)
        slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        slider.setTickInterval((max_val - min_val) // 10)
        value_label = QLabel(str(default_val / divisor))
        slider.valueChanged.connect(lambda v, lbl=value_label, d=divisor: lbl.setText(f"{v / d:.2f}"))
        layout.addWidget(slider)
        layout.addWidget(value_label)
        parent_layout.addLayout(layout)
        # Armazenar referências para acesso posterior (inclui limites)
        setattr(self, f"_slider_{config_key}", (slider, value_label, divisor, min_val, max_val))

    def _load_config(self):
        """Carrega configurações atuais e preenche campos."""
        config = self.config
        # HLSL
        self.hlsl_enable_check.setChecked(config.get("hlsl_enable", "0") == "1")
        self.hlsl_path_edit.setText(config.get("hlslpath", "hlsl"))
        self.hlsl_shadow_combo.setEditText(config.get("shadow_mask_texture", "shadow-mask.png"))
        self.hlsl_yiq_check.setChecked(config.get("yiq_enable", "0") == "1")

        # Carregar sliders
        slider_mappings = {
            "scanline_alpha": ("scanline_alpha", 0.25),
            "bloom_scale": ("bloom_scale", 0.0),
            "shadow_mask_alpha": ("shadow_mask_alpha", 0.15),
            "defocus_x": ("defocus", 0.0),  # defocus é "x,y" - vamos tratar como x
            "defocus_y": ("defocus", 0.0),
            "beam_width_min": ("beam_width_min", 1.0),
            "beam_width_max": ("beam_width_max", 1.0),
            "flicker": ("flicker", 0.0),
        }
        for key, (ini_key, default) in slider_mappings.items():
            val_str = config.get(ini_key, str(default))
            if ',' in val_str and key.startswith("defocus"):
                # pega o primeiro valor
                val = float(val_str.split(',')[0])
            else:
                try:
                    val = float(val_str)
                except:
                    val = default
            slider_info = getattr(self, f"_slider_{key}", None)
            if slider_info:
                slider, label, divisor, min_val, max_val = slider_info
                int_val = int(val * divisor)
                if min_val <= int_val <= max_val:
                    slider.setValue(int_val)
                    label.setText(f"{val:.2f}")

        # GLSL
        self.glsl_enable_check.setChecked(config.get("gl_glsl", "0") == "1")
        self.glsl_filter_check.setChecked(config.get("gl_glsl_filter", "1") == "1")
        self.glsl_shader_edit.setText(config.get("glsl_shader_mame0", "none"))

    def _save_shader_config(self):
        """Salva configurações de efeitos no mame.ini."""
        if not self.ini_path or not self.ini_path.exists():
            exe_path = self.config.get("mame_executable", "")
            if exe_path:
                self.ini_path = MameIniParser.find_ini(Path(exe_path))
            if not self.ini_path or not self.ini_path.exists():
                QMessageBox.warning(self, "Erro", "Arquivo mame.ini não encontrado.")
                return

        # Coletar valores dos sliders
        slider_values = {}
        slider_mappings = {
            "scanline_alpha": "scanline_alpha",
            "bloom_scale": "bloom_scale",
            "shadow_mask_alpha": "shadow_mask_alpha",
            "beam_width_min": "beam_width_min",
            "beam_width_max": "beam_width_max",
            "flicker": "flicker",
        }
        for key, ini_key in slider_mappings.items():
            slider_info = getattr(self, f"_slider_{key}", None)
            if slider_info:
                slider, _, divisor = slider_info
                val = slider.value() / divisor
                slider_values[ini_key] = f"{val:.2f}"

        # Defocus (x,y) - usar o mesmo valor para ambos por simplicidade, ou permitir separado? Vamos usar X e Y iguais.
        defocus_slider = getattr(self, "_slider_defocus_x", None)
        if defocus_slider:
            val_x = defocus_slider[0].value() / defocus_slider[2]
            val_y = val_x  # ou ler de defocus_y se existir
            slider_values["defocus"] = f"{val_x:.2f},{val_y:.2f}"

        config = {
            "hlsl_enable": "1" if self.hlsl_enable_check.isChecked() else "0",
            "hlslpath": self.hlsl_path_edit.text().strip(),
            "shadow_mask_texture": self.hlsl_shadow_combo.currentText().strip(),
            "yiq_enable": "1" if self.hlsl_yiq_check.isChecked() else "0",
            "gl_glsl": "1" if self.glsl_enable_check.isChecked() else "0",
            "gl_glsl_filter": "1" if self.glsl_filter_check.isChecked() else "0",
            "glsl_shader_mame0": self.glsl_shader_edit.text().strip(),
            **slider_values
        }

        try:
            with open(self.ini_path, 'r', encoding='utf-8-sig') as f:
                original_lines = f.readlines()
        except:
            original_lines = None

        MameIniParser.save(self.ini_path, config, original_lines)
        QMessageBox.information(self, "Sucesso", f"Configurações de efeitos salvas em {self.ini_path}")