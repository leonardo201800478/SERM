"""Interface gráfica das configurações nativas do Flycast."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config.app_config import AppConfig
from app.emulators.flycast_config import FlycastConfig, FlycastConfigError


class FlycastSettingsTab(QWidget):
    """Editor das configurações suportadas do Flycast."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = getattr(parent, "parent_window", None)
        self.app_config: AppConfig = getattr(self.config, "config", None) or AppConfig()
        self.flycast_config: FlycastConfig | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Monta as subabas Geral, Vídeo, Áudio e Controles."""
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        self.status_label = QLabel("Configuração do Flycast")
        self.reload_button = QPushButton("Recarregar")
        self.save_button = QPushButton("Salvar")
        header.addWidget(self.status_label)
        header.addStretch()
        header.addWidget(self.reload_button)
        header.addWidget(self.save_button)
        root.addLayout(header)

        self.tabs = QTabWidget()
        self.general = self._build_general()
        self.video = self._build_video()
        self.audio = self._build_audio()
        self.input = self._build_input()
        self.tabs.addTab(self.general, "Geral")
        self.tabs.addTab(self.video, "Vídeo")
        self.tabs.addTab(self.audio, "Áudio")
        self.tabs.addTab(self.input, "Controles")
        root.addWidget(self.tabs)

        self.reload_button.clicked.connect(self.refresh)
        self.save_button.clicked.connect(self.save)

    @staticmethod
    def _scroll(group: QGroupBox) -> QWidget:
        """Coloca um grupo em uma área rolável."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(group)
        return scroll

    def _build_general(self) -> QWidget:
        """Cria controles gerais do Dreamcast/Flycast."""
        group = QGroupBox()
        form = QFormLayout(group)
        self.region = QComboBox(); self.region.addItem("Automático", "0"); self.region.addItem("Japão", "1"); self.region.addItem("EUA", "2"); self.region.addItem("Europa", "3")
        self.language = QComboBox(); self.language.addItem("Japonês", "0"); self.language.addItem("Inglês", "1")
        self.cable = QComboBox(); self.cable.addItem("VGA", "0"); self.cable.addItem("RGB", "1"); self.cable.addItem("TV", "2")
        self.broadcast = QComboBox(); self.broadcast.addItem("NTSC", "0"); self.broadcast.addItem("PAL", "1"); self.broadcast.addItem("PAL-M", "2"); self.broadcast.addItem("PAL-N", "3"); self.broadcast.addItem("PAL-60", "4")
        self.ram_mod = QCheckBox("RAM adicional de 32 MB")
        self.per_game_vmu = QCheckBox("VMU por jogo")
        self.physical_vmu = QCheckBox("Usar memória física da VMU")
        self.dynarec = QCheckBox("Dynarec")
        self.sh4_clock = QSpinBox(); self.sh4_clock.setRange(1, 1000); self.sh4_clock.setSuffix(" MHz")
        form.addRow("Região", self.region); form.addRow("Idioma", self.language); form.addRow("Cabo", self.cable); form.addRow("Broadcast", self.broadcast)
        form.addRow(self.ram_mod); form.addRow(self.per_game_vmu); form.addRow(self.physical_vmu); form.addRow(self.dynarec); form.addRow("Clock SH4", self.sh4_clock)
        return self._scroll(group)

    def _build_video(self) -> QWidget:
        """Cria controles de vídeo e renderer do Flycast."""
        group = QGroupBox(); form = QFormLayout(group)
        self.renderer = QComboBox(); self.renderer.addItem("OpenGL", "4"); self.renderer.addItem("Vulkan", "5")
        self.resolution = QSpinBox(); self.resolution.setRange(240, 16384); self.resolution.setSuffix(" px")
        self.fullscreen = QCheckBox("Tela cheia")
        self.vsync = QCheckBox("VSync")
        self.filtering = QSpinBox(); self.filtering.setRange(0, 8)
        self.anisotropic = QSpinBox(); self.anisotropic.setRange(0, 16)
        self.texture_upscale = QSpinBox(); self.texture_upscale.setRange(0, 8)
        self.texture_upscale2 = QSpinBox(); self.texture_upscale2.setRange(0, 8)
        self.widescreen = QCheckBox("Widescreen")
        self.super_wide = QCheckBox("Super widescreen")
        self.threaded = QCheckBox("Threaded rendering")
        self.fog = QCheckBox("Fog")
        self.mipmaps = QCheckBox("Mipmaps")
        self.framebuffer = QCheckBox("Emular framebuffer")
        form.addRow("Renderer", self.renderer); form.addRow("Resolução", self.resolution); form.addRow(self.fullscreen); form.addRow(self.vsync)
        form.addRow("Texture filtering", self.filtering); form.addRow("Anisotropic", self.anisotropic)
        form.addRow("Texture upscale", self.texture_upscale); form.addRow("Texture upscale 2", self.texture_upscale2)
        form.addRow(self.widescreen); form.addRow(self.super_wide); form.addRow(self.threaded); form.addRow(self.fog); form.addRow(self.mipmaps); form.addRow(self.framebuffer)
        return self._scroll(group)

    def _build_audio(self) -> QWidget:
        """Cria controles de áudio do Flycast."""
        group = QGroupBox(); form = QFormLayout(group)
        self.vmu_sound = QCheckBox("Som da VMU")
        self.auto_latency = QCheckBox("Auto latency")
        self.buffer_size = QSpinBox(); self.buffer_size.setRange(0, 65536)
        self.dsp = QCheckBox("DSP")
        self.volume = QSpinBox(); self.volume.setRange(0, 200); self.volume.setSuffix(" %")
        form.addRow(self.vmu_sound); form.addRow(self.auto_latency); form.addRow("Buffer", self.buffer_size); form.addRow(self.dsp); form.addRow("Volume", self.volume)
        return self._scroll(group)

    def _build_input(self) -> QWidget:
        """Cria controles gerais de entrada do Flycast."""
        group = QGroupBox(); form = QFormLayout(group)
        self.raw_input = QCheckBox("Raw Input")
        self.mouse_sensitivity = QSpinBox(); self.mouse_sensitivity.setRange(1, 500); self.mouse_sensitivity.setSuffix(" %")
        self.vibration = QSpinBox(); self.vibration.setRange(0, 100); self.vibration.setSuffix(" %")
        self.controller = QCheckBox("Controles habilitados"); self.controller.setChecked(True)
        self.wheel = QCheckBox("Volante")
        self.lightgun = QCheckBox("Lightgun")
        self.force_feedback = QCheckBox("Force Feedback")
        form.addRow(self.controller); form.addRow(self.wheel); form.addRow(self.force_feedback); form.addRow(self.lightgun); form.addRow(self.raw_input); form.addRow("Sensibilidade do mouse", self.mouse_sensitivity); form.addRow("Vibração", self.vibration)
        return self._scroll(group)

    @staticmethod
    def _bool(value: str | None, default: bool = False) -> bool:
        """Converte yes/no, true/false e 1/0 para bool."""
        if value is None:
            return default
        return value.strip().casefold() in {"yes", "true", "1", "on"}

    @staticmethod
    def _int(value: str | None, default: int = 0) -> int:
        """Converte valor textual para inteiro com fallback seguro."""
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return default

    def _config_path(self) -> Path | None:
        """Localiza o arquivo nativo do Flycast na instalação configurada."""
        directory = self.app_config.flycast_dir
        if not directory:
            return None
        candidates = (directory / "emu.cfg", directory / "data" / "emu.cfg", directory / "flycast.cfg")
        return next((path for path in candidates if path.is_file()), candidates[0])

    def refresh(self) -> None:
        """Carrega a configuração nativa do Flycast para a interface."""
        path = self._config_path()
        if not path:
            self.status_label.setText("Flycast não configurado na aba Diretórios")
            return
        self.flycast_config = FlycastConfig(path)
        try:
            values = self.flycast_config.read_named()
        except FlycastConfigError as exc:
            self.status_label.setText(str(exc))
            return

        self._set_combo(self.region, values.get("region"), "2")
        self._set_combo(self.language, values.get("language"), "1")
        self._set_combo(self.cable, values.get("cable"), "2")
        self._set_combo(self.broadcast, values.get("broadcast"), "4")
        self.ram_mod.setChecked(self._bool(values.get("ram_mod_32mb")))
        self.per_game_vmu.setChecked(self._bool(values.get("per_game_vmu"), True))
        self.physical_vmu.setChecked(self._bool(values.get("physical_vmu"), True))
        self.dynarec.setChecked(self._bool(values.get("dynarec"), True))
        self.sh4_clock.setValue(self._int(values.get("sh4_clock"), 200))
        self._set_combo(self.renderer, values.get("renderer"), "5")
        self.resolution.setValue(self._int(values.get("resolution"), 1440))
        self.fullscreen.setChecked(self._bool(values.get("fullscreen"), True))
        self.vsync.setChecked(self._bool(values.get("vsync"), True))
        self.filtering.setValue(self._int(values.get("filtering"), 2))
        self.anisotropic.setValue(self._int(values.get("anisotropic"), 1))
        self.texture_upscale.setValue(self._int(values.get("texture_upscale"), 1))
        self.texture_upscale2.setValue(self._int(values.get("texture_upscale2"), 1))
        self.widescreen.setChecked(self._bool(values.get("widescreen")))
        self.super_wide.setChecked(self._bool(values.get("super_wide")))
        self.threaded.setChecked(self._bool(values.get("threaded"), True))
        self.fog.setChecked(self._bool(values.get("fog"), True))
        self.mipmaps.setChecked(self._bool(values.get("mipmaps"), True))
        self.framebuffer.setChecked(self._bool(values.get("framebuffer")))
        self.vmu_sound.setChecked(self._bool(values.get("vmu_sound"), True))
        self.auto_latency.setChecked(self._bool(values.get("auto_latency")))
        self.buffer_size.setValue(self._int(values.get("buffer_size"), 2822))
        self.dsp.setChecked(self._bool(values.get("dsp"), True))
        self.volume.setValue(self._int(values.get("volume"), 100))
        self.raw_input.setChecked(self._bool(values.get("raw_input")))
        self.mouse_sensitivity.setValue(self._int(values.get("mouse_sensitivity"), 100))
        self.vibration.setValue(self._int(values.get("vibration"), 20))
        self.status_label.setText(f"Flycast: {path}")

    @staticmethod
    def _set_combo(combo: QComboBox, value: str | None, default: str) -> None:
        """Seleciona uma opção pelo valor nativo, mantendo fallback."""
        wanted = str(value if value is not None else default)
        index = combo.findData(wanted)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def save(self) -> None:
        """Grava as alterações no arquivo nativo do Flycast."""
        if not self.flycast_config:
            self.status_label.setText("Flycast não configurado")
            return
        values = {
            "region": self.region.currentData(), "language": self.language.currentData(), "cable": self.cable.currentData(), "broadcast": self.broadcast.currentData(),
            "ram_mod_32mb": self.ram_mod.isChecked(), "per_game_vmu": self.per_game_vmu.isChecked(), "physical_vmu": self.physical_vmu.isChecked(), "dynarec": self.dynarec.isChecked(), "sh4_clock": self.sh4_clock.value(),
            "renderer": self.renderer.currentData(), "resolution": self.resolution.value(), "fullscreen": self.fullscreen.isChecked(), "vsync": self.vsync.isChecked(),
            "filtering": self.filtering.value(), "anisotropic": self.anisotropic.value(), "texture_upscale": self.texture_upscale.value(), "texture_upscale2": self.texture_upscale2.value(),
            "widescreen": self.widescreen.isChecked(), "super_wide": self.super_wide.isChecked(), "threaded": self.threaded.isChecked(), "fog": self.fog.isChecked(), "mipmaps": self.mipmaps.isChecked(), "framebuffer": self.framebuffer.isChecked(),
            "vmu_sound": self.vmu_sound.isChecked(), "auto_latency": self.auto_latency.isChecked(), "buffer_size": self.buffer_size.value(), "dsp": self.dsp.isChecked(), "volume": self.volume.value(),
            "raw_input": self.raw_input.isChecked(), "mouse_sensitivity": self.mouse_sensitivity.value(), "vibration": self.vibration.value(),
        }
        try:
            self.flycast_config.update_named(values)
            self.status_label.setText(f"Configuração salva: {self.flycast_config.config_path}")
        except FlycastConfigError as exc:
            self.status_label.setText(str(exc))
