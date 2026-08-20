"""Aba de configurações gerais do MAME baseada no mame.ini real.

A interface trata HLSL/CRT e GLSL como subsistemas de primeira classe. O arquivo
mame.ini continua sendo a fonte de verdade e é editado pelo MameIniEditor,
que preserva comentários, seções, ordem e opções desconhecidas.

Observação sobre áudio: as opções globais ficam no mame.ini. O MAME também
possui o Audio Mixer e Audio Effects por sistema; essas rotas são salvas nos
arquivos de configuração do sistema, não como opções globais do mame.ini.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config.app_config import AppConfig
from app.mame.mame_ini_editor import MameIniEditor, resolve_mame_ini


class MameSettingsTab(QWidget):
    """Editor visual das configurações globais relevantes do MAME."""

    VIDEO_OPTIONS = ["auto", "bgfx", "d3d", "opengl", "soft", "accel", "none"]
    HLSL_RASTER_BLOOM = [1.00, 0.64, 0.32, 0.16, 0.08, 0.06, 0.04, 0.02, 0.01]
    HLSL_VECTOR_BLOOM = [1.00, 0.48, 0.32, 0.24, 0.16, 0.24, 0.32, 0.48, 0.64]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = AppConfig()
        self.editor: MameIniEditor | None = None
        self.widgets: dict[str, QWidget] = {}
        self._build_ui()
        self._load_ini()

    def _build_ui(self) -> None:
        """Cria a interface principal e separa Som, Vídeo e Shaders em subguias."""
        root = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel("Configurações Gerais do MAME")
        title.setStyleSheet("font-size:20px;font-weight:bold")
        header.addWidget(title)
        header.addStretch()
        self.path_label = QLabel("mame.ini: não carregado")
        header.addWidget(self.path_label)
        root.addLayout(header)

        actions = QHBoxLayout()
        self.reload_button = QPushButton("Recarregar mame.ini")
        self.save_button = QPushButton("Salvar configurações")
        self.browse_button = QPushButton("Selecionar mame.ini")
        actions.addWidget(self.reload_button)
        actions.addWidget(self.save_button)
        actions.addWidget(self.browse_button)
        actions.addStretch()
        root.addLayout(actions)

        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setStyleSheet("padding:6px")
        root.addWidget(self.info)

        self.subtabs = QTabWidget()
        root.addWidget(self.subtabs, 1)

        self._create_subtab("Som", self._build_audio_group)
        self._create_subtab("Vídeo", self._build_video_page)
        self._create_subtab("Shaders", self._build_shader_page)

        self.reload_button.clicked.connect(self._load_ini)
        self.save_button.clicked.connect(self._save_ini)
        self.browse_button.clicked.connect(self._select_ini)

    def _create_subtab(self, title: str, builder) -> None:
        """Cria uma subguia rolável e executa nela o construtor correspondente."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.form_layout = QVBoxLayout(container)
        builder()
        self.form_layout.addStretch()
        scroll.setWidget(container)
        self.subtabs.addTab(scroll, title)

    def _build_video_page(self) -> None:
        """Agrupa as opções de vídeo global e imagem/rotação em uma única subguia."""
        self._build_video_group()
        self._build_general_group()

    def _build_shader_page(self) -> None:
        """Agrupa HLSL/CRT e GLSL na subguia dedicada a shaders."""
        self._build_crt_group()
        self._build_glsl_group()

    def _add_group(self, title: str) -> QFormLayout:
        """Cria um grupo com formulário e adiciona-o à área rolável atual."""
        group = QGroupBox(title)
        form = QFormLayout(group)
        self.form_layout.addWidget(group)
        return form

    def _add_combo(self, form: QFormLayout, key: str, label: str, values: list[str]) -> None:
        """Adiciona combo para uma opção textual do mame.ini."""
        widget = QComboBox()
        widget.addItems(values)
        widget.setEditable(True)
        self.widgets[key] = widget
        form.addRow(label, widget)

    def _add_check(self, form: QFormLayout, key: str, label: str) -> None:
        """Adiciona checkbox para opções booleanas 0/1."""
        widget = QCheckBox()
        self.widgets[key] = widget
        form.addRow(label, widget)

    def _add_int(self, form: QFormLayout, key: str, label: str, minimum: int, maximum: int) -> None:
        """Adiciona campo inteiro limitado à faixa segura da opção."""
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        self.widgets[key] = widget
        form.addRow(label, widget)

    def _add_float(self, form: QFormLayout, key: str, label: str, minimum: float, maximum: float, decimals: int = 3) -> None:
        """Adiciona campo decimal para parâmetros de imagem/áudio."""
        widget = QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(decimals)
        widget.setSingleStep(0.01)
        self.widgets[key] = widget
        form.addRow(label, widget)

    def _add_text(self, form: QFormLayout, key: str, label: str) -> None:
        """Adiciona campo textual, útil para caminhos e vetores RGB do HLSL."""
        widget = QLineEdit()
        self.widgets[key] = widget
        form.addRow(label, widget)

    def _add_hlsl_float(self, form: QFormLayout, key: str, label: str, minimum: float, maximum: float) -> None:
        """Adiciona um parâmetro escalar HLSL com faixa explicitamente limitada."""
        self._add_float(form, key, label, minimum, maximum, 4)

    def _build_video_group(self) -> None:
        """Configura renderer, janela, sincronização, escala e filtragem básica."""
        form = self._add_group("Vídeo")
        self._add_combo(form, "video", "Backend de vídeo", self.VIDEO_OPTIONS)
        self._add_check(form, "window", "Executar em janela")
        self._add_check(form, "maximize", "Maximizar janela")
        self._add_check(form, "keepaspect", "Manter proporção")
        self._add_check(form, "unevenstretch", "Permitir escala não inteira")
        self._add_check(form, "waitvsync", "Aguardar VSync")
        self._add_check(form, "syncrefresh", "Sincronizar atualização")
        self._add_check(form, "filter", "Filtro bilinear")
        self._add_int(form, "prescale", "Prescale", 1, 10)
        self._add_combo(form, "view", "View", ["auto", "standard", "pixel", "cocktail", "p1", "p2"])
        self._add_combo(form, "effect", "Effect", ["none"])

    def _build_audio_group(self) -> None:
        """Configura as opções globais de áudio suportadas diretamente pelo mame.ini.

        O MAME 0.289 também oferece Audio Mixer e Audio Effects por sistema.
        Essas rotas são persistidas na configuração do sistema e não devem ser
        simuladas como opções globais do mame.ini.
        """
        form = self._add_group("Áudio global")
        self._add_combo(form, "sound", "Backend de áudio", ["auto", "none"])
        self._add_int(form, "samplerate", "Sample rate (Hz)", 8000, 192000)
        self._add_check(form, "samples", "Samples")
        self._add_int(form, "volume", "Volume (dB)", -96, 12)
        self._add_float(form, "audio_latency", "Latência de áudio", 0.0, 1.0, 3)

        mixer_info = QLabel(
            "O MAME possui Audio Mixer para rotas full/channel e controle de "
            "volume por canal. Essas rotas são salvas na configuração de cada "
            "sistema, portanto não serão gravadas artificialmente no mame.ini."
        )
        mixer_info.setWordWrap(True)
        mixer_info.setStyleSheet("padding:8px")
        self.form_layout.addWidget(mixer_info)

    def _build_crt_group(self) -> None:
        """Configura HLSL/CRT completo: scanlines, máscara, geometria, cor e bloom."""
        form = self._add_group("CRT / HLSL")
        self._add_check(form, "hlsl_enable", "Ativar HLSL")
        self._add_text(form, "hlslpath", "Pasta HLSL")
        self._add_check(form, "hlsl_oversampling", "HLSL oversampling")
        self._add_combo(form, "hlsl_write", "Gravar HLSL em AVI", ["auto", "0", "1"])
        self._add_int(form, "hlsl_snap_width", "Screenshot HLSL — largura", 320, 16384)
        self._add_int(form, "hlsl_snap_height", "Screenshot HLSL — altura", 240, 16384)

        presets = QHBoxLayout()
        for title, callback in (
            ("HLSL desligado", self._preset_hlsl_off),
            ("CRT leve", self._preset_crt_light),
            ("CRT arcade", self._preset_crt_arcade),
            ("CRT forte", self._preset_crt_strong),
        ):
            button = QPushButton(title)
            button.clicked.connect(callback)
            presets.addWidget(button)
        wrapper = QWidget()
        wrapper.setLayout(presets)
        form.addRow("Presets", wrapper)

        self._build_hlsl_scanlines(form)
        self._build_hlsl_geometry(form)
        self._build_hlsl_color(form)
        self._build_hlsl_shadow_mask(form)
        self._build_hlsl_bloom(form)

    def _build_hlsl_scanlines(self, form: QFormLayout) -> None:
        """Cria os controles de scanlines documentados pelo MAME 0.289."""
        self._add_hlsl_float(form, "scanline_alpha", "Scanline alpha", 0.0, 1.0)
        self._add_hlsl_float(form, "scanline_size", "Scanline size", 0.1, 4.0)
        self._add_hlsl_float(form, "scanline_height", "Scanline height", 0.1, 4.0)
        self._add_hlsl_float(form, "scanline_variation", "Scanline variation", 0.0, 2.0)
        self._add_hlsl_float(form, "scanline_bright_scale", "Scanline brightness", 0.0, 4.0)
        self._add_hlsl_float(form, "scanline_bright_offset", "Scanline brightness offset", -1.0, 1.0)
        self._add_hlsl_float(form, "scanline_jitter", "Scanline jitter", 0.0, 1.0)
        self._add_hlsl_float(form, "hum_bar_alpha", "Hum bar", 0.0, 1.0)

    def _build_hlsl_geometry(self, form: QFormLayout) -> None:
        """Cria controles de distorção, borda, defocus e convergência RGB."""
        self._add_hlsl_float(form, "distortion", "Quadric distortion", 0.0, 1.0)
        self._add_hlsl_float(form, "cubic_distortion", "Cubic distortion", 0.0, 1.0)
        self._add_hlsl_float(form, "distort_corner", "Distort corner", 0.0, 1.0)
        self._add_hlsl_float(form, "round_corner", "Round corner", 0.0, 1.0)
        self._add_hlsl_float(form, "smooth_border", "Smooth border", 0.0, 1.0)
        self._add_hlsl_float(form, "reflection", "Reflection", 0.0, 1.0)
        self._add_hlsl_float(form, "vignetting", "Vignetting", 0.0, 1.0)
        self._add_text(form, "defocus", "Defocus X,Y")
        self._add_text(form, "converge_x", "Convergence X RGB")
        self._add_text(form, "converge_y", "Convergence Y RGB")
        self._add_text(form, "radial_converge_x", "Radial convergence X RGB")
        self._add_text(form, "radial_converge_y", "Radial convergence Y RGB")

    def _build_hlsl_color(self, form: QFormLayout) -> None:
        """Cria controles de matriz RGB, sinal, saturação e persistência do fósforo."""
        self._add_text(form, "red_ratio", "Red ratio")
        self._add_text(form, "grn_ratio", "Green ratio")
        self._add_text(form, "blu_ratio", "Blue ratio")
        self._add_text(form, "offset", "Signal offset RGB")
        self._add_text(form, "scale", "Signal scale RGB")
        self._add_text(form, "power", "Signal power RGB")
        self._add_text(form, "floor", "Signal floor RGB")
        self._add_text(form, "phosphor_life", "Phosphor persistence RGB")
        self._add_hlsl_float(form, "saturation", "Saturation", 0.0, 2.0)

    def _build_hlsl_shadow_mask(self, form: QFormLayout) -> None:
        """Cria todos os parâmetros de shadow mask HLSL."""
        self._add_text(form, "shadow_mask_texture", "Shadow mask texture")
        self._add_int(form, "shadow_mask_tile_mode", "Shadow mask tile mode", 0, 1)
        self._add_hlsl_float(form, "shadow_mask_alpha", "Shadow mask alpha", 0.0, 1.0)
        self._add_int(form, "shadow_mask_x_count", "Shadow mask pixels X", 1, 4096)
        self._add_int(form, "shadow_mask_y_count", "Shadow mask pixels Y", 1, 4096)
        self._add_hlsl_float(form, "shadow_mask_usize", "Shadow mask U size", 0.001, 1.0)
        self._add_hlsl_float(form, "shadow_mask_vsize", "Shadow mask V size", 0.001, 1.0)
        self._add_hlsl_float(form, "shadow_mask_uoffset", "Shadow mask U offset", -1.0, 1.0)
        self._add_hlsl_float(form, "shadow_mask_voffset", "Shadow mask V offset", -1.0, 1.0)

    def _build_hlsl_bloom(self, form: QFormLayout) -> None:
        """Cria os controles de bloom e oferece valores de referência para raster/vector."""
        self._add_int(form, "bloom_blend_mode", "Bloom blend mode", 0, 1)
        self._add_hlsl_float(form, "bloom_scale", "Bloom scale", 0.0, 1.0)
        self._add_text(form, "bloom_overdrive", "Bloom overdrive RGB")
        for index in range(9):
            self._add_hlsl_float(form, f"bloom_lvl{index}_weight", f"Bloom level {index}", 0.0, 1.0)

        row = QHBoxLayout()
        raster = QPushButton("Preset bloom raster")
        vector = QPushButton("Preset bloom vector")
        raster.clicked.connect(lambda: self._set_bloom(self.HLSL_RASTER_BLOOM))
        vector.clicked.connect(lambda: self._set_bloom(self.HLSL_VECTOR_BLOOM))
        row.addWidget(raster)
        row.addWidget(vector)
        wrapper = QWidget()
        wrapper.setLayout(row)
        form.addRow("Bloom presets", wrapper)

    def _build_glsl_group(self) -> None:
        """Configura GLSL e slots de shaders sem exigir que shaders existam."""
        form = self._add_group("GLSL")
        self._add_check(form, "gl_glsl", "Ativar GLSL")
        self._add_combo(form, "gl_glsl_filter", "Filtro GLSL", ["0", "1", "2"])
        for prefix in ("glsl_shader_mame", "glsl_shader_screen"):
            for index in range(10):
                self._add_text(form, f"{prefix}{index}", f"{prefix}{index}")

    def _build_general_group(self) -> None:
        """Exibe ajustes de brilho, contraste, gamma, rotação e vector CRT."""
        form = self._add_group("Imagem / Rotação / Vetor")
        self._add_float(form, "brightness", "Brilho", 0.1, 2.0)
        self._add_float(form, "contrast", "Contraste", 0.1, 2.0)
        self._add_float(form, "gamma", "Gamma", 0.1, 3.0)
        self._add_float(form, "pause_brightness", "Brilho em pausa", 0.1, 1.0)
        self._add_check(form, "rotate", "Permitir rotação")
        self._add_check(form, "ror", "Rotação 90° direita")
        self._add_check(form, "rol", "Rotação 90° esquerda")
        self._add_check(form, "autoror", "Rotação automática direita")
        self._add_check(form, "autorol", "Rotação automática esquerda")
        self._add_check(form, "flipx", "Inverter X")
        self._add_check(form, "flipy", "Inverter Y")
        self._add_float(form, "beam_width_min", "Vector beam width min", 0.0, 10.0)
        self._add_float(form, "beam_width_max", "Vector beam width max", 0.0, 10.0)
        self._add_float(form, "beam_dot_size", "Vector beam dot size", 0.0, 10.0)
        self._add_float(form, "beam_intensity_weight", "Vector intensity weight", 0.0, 10.0)
        self._add_float(form, "flicker", "Vector flicker", 0.0, 1.0)
        self._add_float(form, "vector_beam_smooth", "Vector beam smooth", 0.0, 1.0)
        self._add_float(form, "vector_length_scale", "Vector length scale", 0.0, 1.0)
        self._add_float(form, "vector_length_ratio", "Vector length ratio", 0.0, 1.0)

    def _populate_widgets(self) -> None:
        """Transfere os valores do arquivo para os controles."""
        if not self.editor:
            return
        for key, widget in self.widgets.items():
            value = self.editor.get(key, "")
            if isinstance(widget, QCheckBox):
                widget.setChecked(value.lower() in {"1", "yes", "true", "on"})
            elif isinstance(widget, QComboBox):
                index = widget.findText(value)
                if index >= 0:
                    widget.setCurrentIndex(index)
                else:
                    widget.setCurrentText(value)
            elif isinstance(widget, QSpinBox):
                try:
                    widget.setValue(int(float(value)))
                except (ValueError, TypeError):
                    pass
            elif isinstance(widget, QDoubleSpinBox):
                try:
                    widget.setValue(float(value.split(",")[0]))
                except (ValueError, TypeError):
                    pass
            elif isinstance(widget, QLineEdit):
                widget.setText(value)

    def _collect_values(self) -> dict[str, str]:
        """Coleta os valores da interface para atualizar somente opções existentes."""
        result: dict[str, str] = {}
        for key, widget in self.widgets.items():
            if isinstance(widget, QCheckBox):
                result[key] = "1" if widget.isChecked() else "0"
            elif isinstance(widget, QComboBox):
                result[key] = widget.currentText().strip()
            elif isinstance(widget, QSpinBox):
                result[key] = str(widget.value())
            elif isinstance(widget, QDoubleSpinBox):
                result[key] = f"{widget.value():g}"
            elif isinstance(widget, QLineEdit):
                result[key] = widget.text().strip()
        return result

    def _set_bloom(self, values: list[float]) -> None:
        """Aplica os pesos de bloom de referência do MAME para raster ou vector."""
        for index, value in enumerate(values):
            widget = self.widgets.get(f"bloom_lvl{index}_weight")
            if isinstance(widget, QDoubleSpinBox):
                widget.setValue(value)

    def _set_values(self, values: dict[str, str]) -> None:
        """Aplica valores de preset à interface sem escrever imediatamente no INI."""
        for key, value in values.items():
            widget = self.widgets.get(key)
            if widget is None:
                continue
            if isinstance(widget, QCheckBox):
                widget.setChecked(value.lower() in {"1", "true", "yes", "on"})
            elif isinstance(widget, QComboBox):
                widget.setCurrentText(value)
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(float(value)))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(value))
            elif isinstance(widget, QLineEdit):
                widget.setText(value)

    def _preset_hlsl_off(self) -> None:
        """Desativa HLSL e restaura filtragem convencional."""
        self._set_values({"hlsl_enable": "0", "filter": "1"})
        self._set_status("Preset aplicado na interface. Salve para gravar no mame.ini.")

    def _preset_crt_light(self) -> None:
        """Aplica um CRT discreto, adequado para LCD sem exagerar nos artefatos."""
        self._set_values({
            "video": "d3d", "filter": "0", "hlsl_enable": "1",
            "scanline_alpha": "0.25", "scanline_size": "1.0", "scanline_height": "0.9",
            "scanline_variation": "1.0", "scanline_bright_scale": "1.0",
            "scanline_bright_offset": "0.0", "distortion": "0.03", "round_corner": "0.02",
            "shadow_mask_alpha": "0.15", "bloom_scale": "0.05", "saturation": "1.0",
        })
        self._set_status("CRT leve aplicado. HLSL exige video=d3d e filter=0; salve para confirmar.")

    def _preset_crt_arcade(self) -> None:
        """Aplica uma base equilibrada de CRT arcade conforme a orientação oficial do MAME."""
        self._set_values({
            "video": "d3d", "filter": "0", "hlsl_enable": "1",
            "scanline_alpha": "0.45", "scanline_size": "1.0", "scanline_height": "1.0",
            "scanline_variation": "1.0", "scanline_bright_scale": "1.0",
            "scanline_bright_offset": "0.0", "shadow_mask_alpha": "0.35",
            "shadow_mask_texture": "shadow-mask.png", "shadow_mask_x_count": "12",
            "shadow_mask_y_count": "12", "shadow_mask_usize": "0.5", "shadow_mask_vsize": "0.5",
            "distortion": "0.08", "cubic_distortion": "0.0", "round_corner": "0.04",
            "vignetting": "0.10", "bloom_scale": "0.10", "saturation": "1.0",
        })
        self._set_bloom(self.HLSL_RASTER_BLOOM)
        self._set_status("CRT arcade aplicado. Ajuste a intensidade conforme resolução e monitor.")

    def _preset_crt_strong(self) -> None:
        """Aplica um CRT forte com scanlines, máscara, distorção e bloom mais pronunciados."""
        self._set_values({
            "video": "d3d", "filter": "0", "hlsl_enable": "1",
            "scanline_alpha": "0.65", "scanline_size": "1.0", "scanline_height": "1.05",
            "scanline_variation": "1.0", "scanline_bright_scale": "1.0",
            "scanline_bright_offset": "0.03", "scanline_jitter": "0.01",
            "shadow_mask_alpha": "0.55", "shadow_mask_texture": "slot-mask.png",
            "shadow_mask_x_count": "12", "shadow_mask_y_count": "8",
            "shadow_mask_usize": "0.5", "shadow_mask_vsize": "0.5",
            "distortion": "0.15", "cubic_distortion": "0.03", "round_corner": "0.08",
            "smooth_border": "0.04", "vignetting": "0.18", "bloom_scale": "0.18",
            "saturation": "1.05",
        })
        self._set_bloom(self.HLSL_RASTER_BLOOM)
        self._set_status("CRT forte aplicado. É um ponto de partida; o efeito depende da resolução/GPU/monitor.")

    def _load_ini(self) -> None:
        """Carrega o mame.ini configurado e preenche os controles."""
        self.config = AppConfig()
        path = resolve_mame_ini(self.config.mame_path, self.config.ini_path)
        if path is None:
            self._set_status("Nenhum caminho de MAME configurado.")
            return
        try:
            self.editor = MameIniEditor(path)
        except (OSError, UnicodeError) as exc:
            self.editor = None
            self._set_status(str(exc))
            return
        self.path_label.setText(f"mame.ini: {path}")
        self._populate_widgets()
        self._set_status("mame.ini carregado. HLSL/CRT está integrado e opções desconhecidas são preservadas.")

    def _save_ini(self) -> None:
        """Salva as alterações atomicamente e mantém backup do mame.ini anterior."""
        if not self.editor:
            QMessageBox.warning(self, "MAME", "Nenhum mame.ini carregado.")
            return
        try:
            self.editor.set_many(self._collect_values())
            self.editor.save(create_backup=True)
            self._set_status("Configurações salvas. Backup criado como mame.ini.bak.")
            QMessageBox.information(self, "MAME", "Configurações salvas com segurança.")
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.critical(self, "MAME", f"Não foi possível salvar o mame.ini:\n{exc}")

    def _select_ini(self) -> None:
        """Permite selecionar manualmente o mame.ini quando o caminho ainda não estiver configurado."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar mame.ini", str(Path.home()), "MAME INI (*.ini);;Todos os arquivos (*)"
        )
        if not path:
            return
        self.config.ini_path = Path(path)
        self.config.save()
        self._load_ini()

    def _set_status(self, message: str) -> None:
        """Atualiza a mensagem contextual da aba."""
        self.info.setText(message)
