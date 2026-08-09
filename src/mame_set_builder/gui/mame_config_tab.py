"""
Aba de Configurações do MAME – edita mame.ini via interface gráfica.
Integra OSD Video, BGFX, HLSL e GLSL.
"""

import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QLineEdit, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QPushButton, QScrollArea, QCheckBox, QMessageBox, QTabWidget
)
from PyQt6.QtCore import Qt

from .settings import Settings
from .mame_ini_parser import MameIniParser
from .widgets import ComboSelector, SliderWithValue


logger = logging.getLogger(__name__)

class MameConfigTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.config = Settings.load()
        self.ini_path = None
        self.original_content = None
        self._setup_ui()
        self._load_ini()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Scroll principal
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        main_layout = QVBoxLayout(content)

        # --- Informações do arquivo ---
        info_layout = QHBoxLayout()
        self.ini_label = QLabel("Arquivo mame.ini: não carregado")
        info_layout.addWidget(self.ini_label)
        reload_btn = QPushButton("Recarregar")
        reload_btn.clicked.connect(self._load_ini)
        info_layout.addWidget(reload_btn)
        save_btn = QPushButton("Salvar no mame.ini")
        save_btn.clicked.connect(self._save_ini)
        info_layout.addWidget(save_btn)
        info_layout.addStretch()
        main_layout.addLayout(info_layout)

        # --- Abas internas (OSD Video, BGFX, HLSL, GLSL) ---
        self.tab_widget = QTabWidget()

        # OSD Video
        self.osd_tab = self._create_osd_tab()
        self.tab_widget.addTab(self.osd_tab, "OSD Video")

        # BGFX
        self.bgfx_tab = self._create_bgfx_tab()
        self.tab_widget.addTab(self.bgfx_tab, "BGFX")

        # HLSL (Windows)
        self.hlsl_tab = self._create_hlsl_tab()
        self.tab_widget.addTab(self.hlsl_tab, "HLSL")

        # GLSL
        self.glsl_tab = self._create_glsl_tab()
        self.tab_widget.addTab(self.glsl_tab, "GLSL")

        main_layout.addWidget(self.tab_widget)
        main_layout.addStretch()

    # ============================================================
    # OSD VIDEO TAB
    # ============================================================
    def _create_osd_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # video
        self.video_combo = ComboSelector(
            "Video Driver",
            ["bgfx", "d3d", "opengl", "gdi", "soft", "accel", "none"],
            description="Seleciona o subsistema de vídeo para renderização. bgfx é o mais moderno e recomendado[reference:0]."
        )
        layout.addWidget(self.video_combo)

        # numscreens
        self.numscreens_slider = SliderWithValue(
            "Número de Telas",
            min_val=1, max_val=4, default=1,
            description="Número de janelas/telas de saída. Útil para jogos com múltiplas telas (ex: Darius)[reference:1]."
        )
        layout.addWidget(self.numscreens_slider)

        # window
        self.window_check = QCheckBox("Modo Janela (window)")
        self.window_check.setToolTip("Executa o MAME em janela em vez de tela cheia[reference:2].")
        layout.addWidget(self.window_check)

        # maximize
        self.maximize_check = QCheckBox("Maximizar Janela")
        self.maximize_check.setToolTip("Maximiza a janela ao iniciar (se window=1).")
        layout.addWidget(self.maximize_check)

        # waitvsync
        self.waitvsync_check = QCheckBox("Aguardar VSync (waitvsync)")
        self.waitvsync_check.setToolTip("Sincroniza a renderização com o refresh vertical do monitor.")
        layout.addWidget(self.waitvsync_check)

        # syncrefresh
        self.syncrefresh_check = QCheckBox("Sincronizar Refresh (syncrefresh)")
        self.syncrefresh_check.setToolTip("Ajusta a velocidade da emulação para sincronizar com o refresh do monitor.")
        layout.addWidget(self.syncrefresh_check)

        # monitorprovider
        self.monitor_combo = ComboSelector(
            "Provedor de Monitores",
            ["auto", "windows", "sdl"],
            description="Define como o MAME detecta e gerencia os monitores disponíveis."
        )
        layout.addWidget(self.monitor_combo)

        layout.addStretch()
        return tab

    # ============================================================
    # BGFX TAB
    # ============================================================
    def _create_bgfx_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # bgfx_backend
        self.bgfx_backend_combo = ComboSelector(
            "BGFX Backend",
            ["auto", "d3d9", "d3d11", "d3d12", "opengl", "gles", "metal", "vulkan"],
            description="Backend de renderização do BGFX. vulkan e d3d12 são os mais modernos[reference:3][reference:4]."
        )
        layout.addWidget(self.bgfx_backend_combo)

        # bgfx_debug
        self.bgfx_debug_check = QCheckBox("Modo Debug BGFX")
        self.bgfx_debug_check.setToolTip("Ativa logs de debug do BGFX.")
        layout.addWidget(self.bgfx_debug_check)

        # bgfx_screen_chains
        # Usando QLineEdit para permitir chains customizadas
        from PyQt6.QtWidgets import QLineEdit
        chain_layout = QHBoxLayout()
        chain_layout.addWidget(QLabel("Screen Chains:"))
        self.bgfx_chains_edit = QLineEdit()
        self.bgfx_chains_edit.setPlaceholderText("ex: crt-geom,default")
        self.bgfx_chains_edit.setToolTip("Cadeias de efeitos BGFX. Exemplos: crt-geom, lcd-grid, default, hlsl[reference:5].")
        chain_layout.addWidget(self.bgfx_chains_edit)
        layout.addLayout(chain_layout)

        # bgfx_shadow_mask
        self.bgfx_shadow_combo = ComboSelector(
            "Shadow Mask",
            ["slot-mask.png", "aperture.png", "shadow-mask.png", ""],
            description="Arquivo PNG para o efeito de shadow mask[reference:6]."
        )
        layout.addWidget(self.bgfx_shadow_combo)

        # bgfx_lut
        self.bgfx_lut_combo = ComboSelector(
            "LUT Texture",
            ["lut-default.png", ""],
            description="Arquivo PNG para o efeito de LUT (Look-Up Table)."
        )
        layout.addWidget(self.bgfx_lut_combo)

        # bgfx_path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("BGFX Path:"))
        self.bgfx_path_edit = QLineEdit()
        self.bgfx_path_edit.setPlaceholderText("bgfx")
        self.bgfx_path_edit.setToolTip("Caminho para a pasta de arquivos BGFX.")
        path_layout.addWidget(self.bgfx_path_edit)
        layout.addLayout(path_layout)

        layout.addStretch()
        return tab

    # ============================================================
    # HLSL TAB (Windows)
    # ============================================================
    def _create_hlsl_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Info
        info = QLabel("HLSL (High-Level Shader Language) é um sistema de pós-processamento para Windows que simula efeitos de monitor CRT.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #555; padding: 5px; background: #f0f0f0; border-radius: 4px;")
        layout.addWidget(info)

        # hlsl_enable
        self.hlsl_enable_check = QCheckBox("Ativar HLSL")
        self.hlsl_enable_check.setToolTip("Ativa o pós-processamento HLSL. Requer video=d3d[reference:7][reference:8].")
        layout.addWidget(self.hlsl_enable_check)

        # hlslpath
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("HLSL Path:"))
        self.hlsl_path_edit = QLineEdit()
        self.hlsl_path_edit.setPlaceholderText("hlsl")
        path_layout.addWidget(self.hlsl_path_edit)
        layout.addLayout(path_layout)

        # shadow_mask
        self.hlsl_shadow_combo = ComboSelector(
            "Shadow Mask",
            ["shadow-mask.png", "aperture.png", "slot-mask.png", ""],
            description="Arquivo PNG para o efeito de shadow mask no HLSL."
        )
        layout.addWidget(self.hlsl_shadow_combo)

        # scanline_alpha
        self.hlsl_scanline_slider = SliderWithValue(
            "Intensidade Scanline (scanline_alpha)",
            min_val=0, max_val=100, default=25,
            description="Controla a opacidade das linhas de scanline (0-100%)."
        )
        layout.addWidget(self.hlsl_scanline_slider)

        # bloom_scale
        self.hlsl_bloom_slider = SliderWithValue(
            "Intensidade Bloom (bloom_scale)",
            min_val=0, max_val=100, default=0,
            description="Controla a intensidade do efeito bloom (0-100%)."
        )
        layout.addWidget(self.hlsl_bloom_slider)

        # shadow_mask_alpha
        self.hlsl_shadow_alpha_slider = SliderWithValue(
            "Shadow Mask Alpha",
            min_val=0, max_val=100, default=15,
            description="Controla a opacidade da shadow mask (0-100%)."
        )
        layout.addWidget(self.hlsl_shadow_alpha_slider)

        # yiq_enable
        self.hlsl_yiq_check = QCheckBox("Ativar YIQ (NTSC)")
        self.hlsl_yiq_check.setToolTip("Ativa o pós-processamento de cores YIQ (efeito NTSC)[reference:9].")
        layout.addWidget(self.hlsl_yiq_check)

        layout.addStretch()
        return tab

    # ============================================================
    # GLSL TAB
    # ============================================================
    def _create_glsl_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Info
        info = QLabel("GLSL (OpenGL Shading Language) é o equivalente ao HLSL para plataformas que usam OpenGL. Requer video=opengl[reference:10].")
        info.setWordWrap(True)
        info.setStyleSheet("color: #555; padding: 5px; background: #f0f0f0; border-radius: 4px;")
        layout.addWidget(info)

        # gl_glsl
        self.glsl_enable_check = QCheckBox("Ativar GLSL")
        self.glsl_enable_check.setToolTip("Ativa o pós-processamento GLSL. Requer video=opengl[reference:11][reference:12].")
        layout.addWidget(self.glsl_enable_check)

        # gl_glsl_filter
        self.glsl_filter_check = QCheckBox("Filtro GLSL")
        self.glsl_filter_check.setToolTip("Ativa o filtro suavizante na saída GLSL[reference:13].")
        layout.addWidget(self.glsl_filter_check)

        # glsl_shader_mame0..9 (usando QLineEdit para simplicidade)
        shader_layout = QHBoxLayout()
        shader_layout.addWidget(QLabel("Shader MAME 0:"))
        self.glsl_shader_edit = QLineEdit()
        self.glsl_shader_edit.setPlaceholderText("none")
        self.glsl_shader_edit.setToolTip("Shader a ser aplicado (0-9). Consulte a documentação do seu pacote de shaders[reference:14].")
        shader_layout.addWidget(self.glsl_shader_edit)
        layout.addLayout(shader_layout)

        layout.addStretch()
        return tab

    # ============================================================
    # CARREGAR E SALVAR
    # ============================================================
    def _load_ini(self):
        """Carrega o mame.ini e preenche os campos."""
        # Tenta obter o caminho do mame.ini a partir da configuração
        ini_path = self.config.get("mame_ini_path", "")

        if not ini_path or not Path(ini_path).exists():
            # Tenta localizar a partir do executável
            exe_path = self.config.get("mame_executable", "")
            if exe_path:
                found = MameIniParser.find_ini(Path(exe_path))
                if found.exists():
                    ini_path = str(found)
                else:
                    QMessageBox.warning(self, "Aviso", "Arquivo mame.ini não encontrado.")
                    return
            else:
                QMessageBox.warning(self, "Aviso", "Configure o executável do MAME primeiro.")
                return

        self.ini_path = Path(ini_path)
        self.ini_label.setText(f"Arquivo mame.ini: {self.ini_path}")

        config = MameIniParser.parse(self.ini_path)
        if not config:
            QMessageBox.warning(self, "Erro", "Não foi possível ler o mame.ini.")
            return

        # Preenche os campos da OSD
        self.video_combo.set_value(config.get("video", "bgfx"))
        self.numscreens_slider.set_value(int(config.get("numscreens", "1")))
        self.window_check.setChecked(config.get("window", "0") == "1")
        self.maximize_check.setChecked(config.get("maximize", "1") == "1")
        self.waitvsync_check.setChecked(config.get("waitvsync", "0") == "1")
        self.syncrefresh_check.setChecked(config.get("syncrefresh", "1") == "1")
        self.monitor_combo.set_value(config.get("monitorprovider", "auto"))

        # BGFX
        self.bgfx_backend_combo.set_value(config.get("bgfx_backend", "auto"))
        self.bgfx_debug_check.setChecked(config.get("bgfx_debug", "0") == "1")
        self.bgfx_chains_edit.setText(config.get("bgfx_screen_chains", ""))
        self.bgfx_shadow_combo.set_value(config.get("bgfx_shadow_mask", "slot-mask.png"))
        self.bgfx_lut_combo.set_value(config.get("bgfx_lut", "lut-default.png"))
        self.bgfx_path_edit.setText(config.get("bgfx_path", "bgfx"))

        # HLSL
        self.hlsl_enable_check.setChecked(config.get("hlsl_enable", "0") == "1")
        self.hlsl_path_edit.setText(config.get("hlslpath", "hlsl"))
        self.hlsl_shadow_combo.set_value(config.get("shadow_mask_texture", "shadow-mask.png"))
        self.hlsl_scanline_slider.set_value(int(float(config.get("scanline_alpha", "0.25")) * 100))
        self.hlsl_bloom_slider.set_value(int(float(config.get("bloom_scale", "0.0")) * 100))
        self.hlsl_shadow_alpha_slider.set_value(int(float(config.get("shadow_mask_alpha", "0.15")) * 100))
        self.hlsl_yiq_check.setChecked(config.get("yiq_enable", "0") == "1")

        # GLSL
        self.glsl_enable_check.setChecked(config.get("gl_glsl", "0") == "1")
        self.glsl_filter_check.setChecked(config.get("gl_glsl_filter", "1") == "1")
        self.glsl_shader_edit.setText(config.get("glsl_shader_mame0", "none"))

        logger.info(f"✅ Configurações carregadas de {self.ini_path}")

    def _save_ini(self):
        """Salva as configurações no mame.ini."""
        if not self.ini_path or not self.ini_path.exists():
            QMessageBox.warning(self, "Erro", "Arquivo mame.ini não encontrado.")
            return

        # Coleta os valores
        config = {
            # OSD
            "video": self.video_combo.get_value(),
            "numscreens": str(self.numscreens_slider.get_value()),
            "window": "1" if self.window_check.isChecked() else "0",
            "maximize": "1" if self.maximize_check.isChecked() else "0",
            "waitvsync": "1" if self.waitvsync_check.isChecked() else "0",
            "syncrefresh": "1" if self.syncrefresh_check.isChecked() else "0",
            "monitorprovider": self.monitor_combo.get_value(),

            # BGFX
            "bgfx_backend": self.bgfx_backend_combo.get_value(),
            "bgfx_debug": "1" if self.bgfx_debug_check.isChecked() else "0",
            "bgfx_screen_chains": self.bgfx_chains_edit.text().strip(),
            "bgfx_shadow_mask": self.bgfx_shadow_combo.get_value(),
            "bgfx_lut": self.bgfx_lut_combo.get_value(),
            "bgfx_path": self.bgfx_path_edit.text().strip(),

            # HLSL
            "hlsl_enable": "1" if self.hlsl_enable_check.isChecked() else "0",
            "hlslpath": self.hlsl_path_edit.text().strip(),
            "shadow_mask_texture": self.hlsl_shadow_combo.get_value(),
            "scanline_alpha": f"{self.hlsl_scanline_slider.get_value() / 100:.2f}",
            "bloom_scale": f"{self.hlsl_bloom_slider.get_value() / 100:.2f}",
            "shadow_mask_alpha": f"{self.hlsl_shadow_alpha_slider.get_value() / 100:.2f}",
            "yiq_enable": "1" if self.hlsl_yiq_check.isChecked() else "0",

            # GLSL
            "gl_glsl": "1" if self.glsl_enable_check.isChecked() else "0",
            "gl_glsl_filter": "1" if self.glsl_filter_check.isChecked() else "0",
            "glsl_shader_mame0": self.glsl_shader_edit.text().strip(),
        }

        # Salva usando o parser que preserva comentários
        # Vamos ler o conteúdo original para preservar a estrutura
        try:
            with open(self.ini_path, 'r', encoding='utf-8-sig') as f:
                original_lines = f.readlines()
        except:
            original_lines = None

        MameIniParser.save(self.ini_path, config, original_lines)
        QMessageBox.information(self, "Sucesso", f"Configurações salvas em {self.ini_path}")

    def get_config(self) -> dict:
        """Retorna as configurações atuais."""
        return {
            "video": self.video_combo.get_value(),
            "numscreens": self.numscreens_slider.get_value(),
            "window": 1 if self.window_check.isChecked() else 0,
            "maximize": 1 if self.maximize_check.isChecked() else 0,
            "waitvsync": 1 if self.waitvsync_check.isChecked() else 0,
            "syncrefresh": 1 if self.syncrefresh_check.isChecked() else 0,
            "monitorprovider": self.monitor_combo.get_value(),
            "bgfx_backend": self.bgfx_backend_combo.get_value(),
            "bgfx_screen_chains": self.bgfx_chains_edit.text().strip(),
            "bgfx_shadow_mask": self.bgfx_shadow_combo.get_value(),
            "hlsl_enable": self.hlsl_enable_check.isChecked(),
            "gl_glsl": self.glsl_enable_check.isChecked(),
        }