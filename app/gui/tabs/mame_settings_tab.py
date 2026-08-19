"""Aba de configurações gerais do MAME baseada no mame.ini real."""
from __future__ import annotations

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
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config.app_config import AppConfig
from app.mame.mame_ini_editor import MameIniEditor, resolve_mame_ini


class MameSettingsTab(QWidget):
    """Editor visual das configurações globais mais relevantes do MAME."""

    VIDEO_OPTIONS = {
        "video": ["auto", "bgfx", "d3d", "opengl", "soft", "accel", "none"],
        "monitorprovider": ["auto"],
        "view": ["auto", "standard", "pixel", "cocktail", "p1", "p2"],
        "effect": ["none"],
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = AppConfig()
        self.editor: MameIniEditor | None = None
        self.widgets: dict[str, QWidget] = {}
        self._build_ui()
        self._load_ini()

    def _build_ui(self) -> None:
        """Cria a interface organizada por subsistemas do MAME."""
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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self.form_layout = QVBoxLayout(container)
        self._build_video_group()
        self._build_audio_group()
        self._build_crt_group()
        self._build_glsl_group()
        self._build_general_group()
        self.form_layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        self.reload_button.clicked.connect(self._load_ini)
        self.save_button.clicked.connect(self._save_ini)
        self.browse_button.clicked.connect(self._select_ini)

    def _add_group(self, title: str) -> QFormLayout:
        """Cria um grupo com formulário e adiciona-o à área rolável."""
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

    def _build_video_group(self) -> None:
        """Configura renderer, janela, sincronização, escala e filtragem básica."""
        form = self._add_group("Vídeo")
        self._add_combo(form, "video", "Backend de vídeo", self.VIDEO_OPTIONS["video"])
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
        """Configura saída de áudio, frequência, samples e volume."""
        form = self._add_group("Áudio")
        self._add_combo(form, "sound", "Backend de áudio", ["auto", "none", "dsound", "wasapi"])
        self._add_int(form, "samplerate", "Sample rate (Hz)", 8000, 192000)
        self._add_check(form, "samples", "Samples")
        self._add_int(form, "volume", "Volume (dB)", -32, 0)
        self._add_float(form, "audio_latency", "Latência de áudio", 0.0, 1.0, 3)

    def _build_crt_group(self) -> None:
        """Configura HLSL/CRT, scanlines, máscara, convergência e bloom."""
        form = self._add_group("CRT / Scanlines — HLSL")
        self._add_check(form, "hlsl_enable", "Ativar HLSL")
        self._add_check(form, "hlsl_oversampling", "HLSL oversampling")
        self._add_float(form, "scanline_alpha", "Scanline alpha", 0.0, 1.0)
        self._add_float(form, "scanline_size", "Scanline size", 0.1, 4.0)
        self._add_float(form, "scanline_height", "Scanline height", 0.1, 4.0)
        self._add_float(form, "scanline_variation", "Scanline variation", 0.0, 2.0)
        self._add_float(form, "scanline_bright_scale", "Scanline brightness", 0.0, 4.0)
        self._add_float(form, "scanline_bright_offset", "Scanline brightness offset", -1.0, 1.0)
        self._add_float(form, "scanline_jitter", "Scanline jitter", 0.0, 1.0)
        self._add_float(form, "hum_bar_alpha", "Hum bar", 0.0, 1.0)
        self._add_float(form, "shadow_mask_alpha", "Shadow mask alpha", 0.0, 1.0)
        self._add_int(form, "shadow_mask_tile_mode", "Shadow mask tile mode", 0, 1)
        self._add_int(form, "shadow_mask_x_count", "Shadow mask pixels X", 1, 32)
        self._add_int(form, "shadow_mask_y_count", "Shadow mask pixels Y", 1, 32)
        self._add_float(form, "distortion", "Distortion", 0.0, 1.0)
        self._add_float(form, "cubic_distortion", "Cubic distortion", 0.0, 1.0)
        self._add_float(form, "round_corner", "Round corner", 0.0, 1.0)
        self._add_float(form, "vignetting", "Vignetting", 0.0, 1.0)
        self._add_float(form, "bloom_scale", "Bloom scale", 0.0, 1.0)
        self._add_float(form, "saturation", "Saturation", 0.0, 2.0)
        self._add_float(form, "defocus", "Defocus X", 0.0, 2.0)

    def _build_glsl_group(self) -> None:
        """Configura GLSL e slots de shaders sem exigir que shaders existam."""
        form = self._add_group("GLSL")
        self._add_check(form, "gl_glsl", "Ativar GLSL")
        self._add_combo(form, "gl_glsl_filter", "Filtro GLSL", ["0", "1", "2"])
        for prefix in ("glsl_shader_mame", "glsl_shader_screen"):
            for index in range(10):
                key = f"{prefix}{index}"
                widget = QLineEdit()
                self.widgets[key] = widget
                form.addRow(key, widget)

    def _build_general_group(self) -> None:
        """Exibe ajustes de brilho, contraste, gamma e rotação mais usados."""
        form = self._add_group("Imagem / Rotação")
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
        self._set_status("Arquivo carregado. Comentários, seções e opções não editadas serão preservados.")

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
        """Coleta apenas os valores dos controles que correspondem a opções existentes."""
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

    def _save_ini(self) -> None:
        """Salva as alterações atomicamente e mantém um backup do mame.ini anterior."""
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
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar mame.ini", str(Path.home()), "MAME INI (*.ini);;Todos os arquivos (*)")
        if not path:
            return
        self.config.ini_path = Path(path)
        self.config.save()
        self._load_ini()

    def _set_status(self, message: str) -> None:
        """Atualiza a mensagem contextual da aba."""
        self.info.setText(message)
