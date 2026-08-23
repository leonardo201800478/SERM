"""Interface de configuração do RetroArch."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.emulators.retroarch_config import RetroArchConfig


class RetroArchSettingsTab(QWidget):
    """Editor das configurações globais do retroarch.cfg."""

    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Cria as páginas Geral, Vídeo, Áudio, Controles e Shaders."""
        root = QVBoxLayout(self)
        self.status_label = QLabel()
        root.addWidget(self.status_label)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        general = QWidget()
        form = QFormLayout(general)
        self.video_driver = QComboBox()
        self.video_driver.addItems(["auto", "gl", "glcore", "vulkan", "d3d11", "d3d12", "d3d10", "d3d9", "sdl2", "sdl3", "gdi"])
        self.audio_driver = QLineEdit()
        self.input_driver = QLineEdit()
        form.addRow("Driver de vídeo", self.video_driver)
        form.addRow("Driver de áudio", self.audio_driver)
        form.addRow("Driver de input", self.input_driver)
        self.tabs.addTab(general, "Geral")

        video = QWidget()
        form = QFormLayout(video)
        self.fullscreen = QCheckBox("Tela cheia")
        self.windowed_fullscreen = QCheckBox("Fullscreen sem borda")
        self.vsync = QCheckBox("VSync")
        self.threaded = QCheckBox("Vídeo em thread")
        self.resolution_x = QSpinBox(); self.resolution_x.setRange(0, 16384)
        self.resolution_y = QSpinBox(); self.resolution_y.setRange(0, 16384)
        self.refresh_rate = QLineEdit()
        self.hdr = QCheckBox("HDR")
        self.hdr_nits = QSpinBox(); self.hdr_nits.setRange(100, 10000)
        form.addRow("Tela cheia", self.fullscreen)
        form.addRow("Fullscreen sem borda", self.windowed_fullscreen)
        form.addRow("VSync", self.vsync)
        form.addRow("Threaded vídeo", self.threaded)
        form.addRow("Resolução X", self.resolution_x)
        form.addRow("Resolução Y", self.resolution_y)
        form.addRow("Refresh rate", self.refresh_rate)
        form.addRow("HDR", self.hdr)
        form.addRow("HDR máximo (nits)", self.hdr_nits)
        self.tabs.addTab(video, "Vídeo")

        audio = QWidget()
        form = QFormLayout(audio)
        self.audio_enable = QCheckBox("Áudio habilitado")
        self.audio_rate = QSpinBox(); self.audio_rate.setRange(8000, 192000)
        self.audio_latency = QSpinBox(); self.audio_latency.setRange(0, 1000)
        self.audio_sync = QCheckBox("Sincronização de áudio")
        self.audio_rate_control = QCheckBox("Controle de taxa")
        form.addRow("Áudio", self.audio_enable)
        form.addRow("Sample rate", self.audio_rate)
        form.addRow("Latência (ms)", self.audio_latency)
        form.addRow("Audio sync", self.audio_sync)
        form.addRow("Rate control", self.audio_rate_control)
        self.tabs.addTab(audio, "Áudio")

        controls = QWidget()
        form = QFormLayout(controls)
        self.joypad_driver = QLineEdit()
        self.autodetect = QCheckBox("Autodetecção")
        self.axis_threshold = QLineEdit()
        self.deadzone = QLineEdit()
        self.sensitivity = QLineEdit()
        self.remap = QCheckBox("Remapeamento habilitado")
        form.addRow("Joypad driver", self.joypad_driver)
        form.addRow("Autodetecção", self.autodetect)
        form.addRow("Axis threshold", self.axis_threshold)
        form.addRow("Analog deadzone", self.deadzone)
        form.addRow("Analog sensitivity", self.sensitivity)
        form.addRow("Remapping", self.remap)
        self.tabs.addTab(controls, "Controles")

        shaders = QWidget()
        form = QFormLayout(shaders)
        self.shader_enable = QCheckBox("Shader habilitado")
        self.shader = QLineEdit()
        self.shader_dir = QLineEdit()
        form.addRow("Shaders", self.shader_enable)
        form.addRow("Preset", self.shader)
        form.addRow("Diretório", self.shader_dir)
        self.tabs.addTab(shaders, "Shaders")

        files = QGroupBox("Configuração")
        file_layout = QVBoxLayout(files)
        self.path_label = QLabel()
        self.save_button = QPushButton("Salvar configuração")
        self.reload_button = QPushButton("Recarregar")
        file_layout.addWidget(self.path_label)
        file_layout.addWidget(self.save_button)
        file_layout.addWidget(self.reload_button)
        root.addWidget(files)
        self.save_button.clicked.connect(self._save)
        self.reload_button.clicked.connect(self.refresh)

    def _config_path(self) -> Path | None:
        """Localiza retroarch.cfg a partir da instalação configurada."""
        config = getattr(getattr(self, "parent_window", None), "config", None)
        install_dir = getattr(config, "retroarch_dir", None)
        if not install_dir:
            return None
        candidates = [Path(install_dir) / "retroarch.cfg", Path(install_dir) / "config" / "retroarch.cfg"]
        return next((path for path in candidates if path.is_file()), candidates[0])

    def _config(self) -> RetroArchConfig | None:
        """Retorna o adapter associado ao retroarch.cfg."""
        path = self._config_path()
        return RetroArchConfig(path) if path else None

    @staticmethod
    def _bool(value: str, default: bool = False) -> bool:
        """Converte booleanos do RetroArch."""
        if not value:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def _set_combo(self, combo: QComboBox, value: str) -> None:
        """Seleciona um driver existente ou o adiciona à lista."""
        index = combo.findText(value)
        if index < 0 and value:
            combo.addItem(value)
            index = combo.findText(value)
        combo.setCurrentIndex(max(index, 0))

    def refresh(self) -> None:
        """Recarrega as configurações atuais do RetroArch."""
        config = self._config()
        path = self._config_path()
        if not config or not path:
            self.status_label.setText("RetroArch não configurado.")
            return
        self.path_label.setText(str(path))
        self.status_label.setText("Configuração carregada.")
        self._set_combo(self.video_driver, config.get("video_driver", "auto"))
        self.audio_driver.setText(config.get("audio_driver"))
        self.input_driver.setText(config.get("input_driver"))
        self.fullscreen.setChecked(self._bool(config.get("video_fullscreen")))
        self.windowed_fullscreen.setChecked(self._bool(config.get("video_windowed_fullscreen"), True))
        self.vsync.setChecked(self._bool(config.get("video_vsync"), True))
        self.threaded.setChecked(self._bool(config.get("video_threaded")))
        self.resolution_x.setValue(self._int(config.get("video_fullscreen_x"), 0))
        self.resolution_y.setValue(self._int(config.get("video_fullscreen_y"), 0))
        self.refresh_rate.setText(config.get("video_refresh_rate", "59.94"))
        self.hdr.setChecked(self._bool(config.get("video_hdr_enable")))
        self.hdr_nits.setValue(self._int(config.get("video_hdr_max_nits"), 1000))
        self.audio_enable.setChecked(self._bool(config.get("audio_enable"), True))
        self.audio_rate.setValue(self._int(config.get("audio_out_rate"), 48000))
        self.audio_latency.setValue(self._int(config.get("audio_latency"), 64))
        self.audio_sync.setChecked(self._bool(config.get("audio_sync"), True))
        self.audio_rate_control.setChecked(self._bool(config.get("audio_rate_control"), True))
        self.joypad_driver.setText(config.get("input_joypad_driver"))
        self.autodetect.setChecked(self._bool(config.get("input_autodetect_enable"), True))
        self.axis_threshold.setText(config.get("input_axis_threshold", "0.5"))
        self.deadzone.setText(config.get("input_analog_deadzone", "0.0"))
        self.sensitivity.setText(config.get("input_analog_sensitivity", "1.0"))
        self.remap.setChecked(self._bool(config.get("input_remap_binds_enable"), True))
        self.shader.setText(config.get("video_shader"))
        self.shader_enable.setChecked(self._bool(config.get("video_shader_enable"), bool(self.shader.text())))
        self.shader_dir.setText(config.get("video_shader_dir"))

    @staticmethod
    def _int(value: str, default: int) -> int:
        """Converte texto para inteiro com fallback."""
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    def _save(self) -> None:
        """Grava somente opções administradas pelo ARCADE MANAGER."""
        config = self._config()
        path = self._config_path()
        if not config or not path:
            self.status_label.setText("RetroArch não configurado.")
            return
        values = {
            "video_driver": self.video_driver.currentText(),
            "audio_driver": self.audio_driver.text().strip(),
            "input_driver": self.input_driver.text().strip(),
            "video_fullscreen": self.fullscreen.isChecked(),
            "video_windowed_fullscreen": self.windowed_fullscreen.isChecked(),
            "video_vsync": self.vsync.isChecked(),
            "video_threaded": self.threaded.isChecked(),
            "video_fullscreen_x": self.resolution_x.value(),
            "video_fullscreen_y": self.resolution_y.value(),
            "video_refresh_rate": self.refresh_rate.text().strip(),
            "video_hdr_enable": self.hdr.isChecked(),
            "video_hdr_max_nits": self.hdr_nits.value(),
            "audio_enable": self.audio_enable.isChecked(),
            "audio_out_rate": self.audio_rate.value(),
            "audio_latency": self.audio_latency.value(),
            "audio_sync": self.audio_sync.isChecked(),
            "audio_rate_control": self.audio_rate_control.isChecked(),
            "input_joypad_driver": self.joypad_driver.text().strip(),
            "input_autodetect_enable": self.autodetect.isChecked(),
            "input_axis_threshold": self.axis_threshold.text().strip(),
            "input_analog_deadzone": self.deadzone.text().strip(),
            "input_analog_sensitivity": self.sensitivity.text().strip(),
            "input_remap_binds_enable": self.remap.isChecked(),
            "video_shader": self.shader.text().strip(),
            "video_shader_enable": self.shader_enable.isChecked(),
            "video_shader_dir": self.shader_dir.text().strip(),
        }
        config.set_many(values)
        config.save(create_backup=True)
        self.status_label.setText("Configuração salva com sucesso.")
        self.settings_changed.emit()
