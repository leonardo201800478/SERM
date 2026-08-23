"""Interface de configurações do FBNeo para o ARCADE MANAGER."""
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
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.emulators.fbneo_config import FBNeoConfig


class FBNeoSettingsTab(QWidget):
    """Editor das opções principais do FBNeo, preservando o arquivo nativo."""

    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Cria as categorias Geral, Vídeo, Áudio e Controles."""
        root = QVBoxLayout(self)
        self.status_label = QLabel()
        root.addWidget(self.status_label)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        general_page = QWidget()
        general = QFormLayout(general_page)
        self.fullscreen = QCheckBox("Tela cheia")
        self.vsync = QCheckBox("VSync")
        self.frameskip = QSpinBox()
        self.frameskip.setRange(0, 10)
        self.frameskip.setToolTip("0 = automático/desativado conforme a configuração do FBNeo")
        general.addRow("Tela cheia", self.fullscreen)
        general.addRow("VSync", self.vsync)
        general.addRow("Frameskip", self.frameskip)
        self.tabs.addTab(general_page, "Geral")

        video_page = QWidget()
        video = QFormLayout(video_page)
        self.filtering = QCheckBox("Filtragem bilinear")
        self.integer_scale = QCheckBox("Escala inteira")
        self.aspect_ratio = QComboBox()
        self.aspect_ratio.addItems(["Auto", "4:3", "16:9", "Custom"])
        video.addRow("Filtragem", self.filtering)
        video.addRow("Escala inteira", self.integer_scale)
        video.addRow("Aspect Ratio", self.aspect_ratio)
        self.tabs.addTab(video_page, "Vídeo")

        audio_page = QWidget()
        audio = QFormLayout(audio_page)
        self.audio_enabled = QCheckBox("Áudio habilitado")
        self.sample_rate = QSpinBox()
        self.sample_rate.setRange(8000, 192000)
        self.sample_rate.setSingleStep(1000)
        self.volume = QSpinBox()
        self.volume.setRange(0, 200)
        audio.addRow("Áudio", self.audio_enabled)
        audio.addRow("Sample rate", self.sample_rate)
        audio.addRow("Volume", self.volume)
        self.tabs.addTab(audio_page, "Áudio")

        controls_page = QWidget()
        controls = QFormLayout(controls_page)
        self.joypad = QCheckBox("Joystick/Gamepad")
        self.lightgun = QCheckBox("Lightgun")
        self.raw_input = QCheckBox("Raw Input")
        self.deadzone = QSpinBox()
        self.deadzone.setRange(0, 100)
        controls.addRow("Gamepad", self.joypad)
        controls.addRow("Lightgun", self.lightgun)
        controls.addRow("Raw Input", self.raw_input)
        controls.addRow("Deadzone", self.deadzone)
        self.tabs.addTab(controls_page, "Controles")

        directories = QGroupBox("Diretórios FBNeo")
        directory_layout = QFormLayout(directories)
        self.rom_paths: list[QLineEdit] = []
        for index in range(4):
            edit = QLineEdit()
            edit.setPlaceholderText(f"Caminho de ROM {index + 1}")
            self.rom_paths.append(edit)
            directory_layout.addRow(f"ROM {index + 1}", edit)
        root.addWidget(directories)

        buttons = QGroupBox("Configuração")
        button_layout = QVBoxLayout(buttons)
        self.path_label = QLabel()
        self.save_button = QPushButton("Salvar configuração")
        self.reload_button = QPushButton("Recarregar")
        button_layout.addWidget(self.path_label)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.reload_button)
        root.addWidget(buttons)
        self.save_button.clicked.connect(self._save)
        self.reload_button.clicked.connect(self.refresh)

    def _ini_path(self) -> Path | None:
        """Resolve o arquivo de configuração FBNeo da instalação selecionada."""
        config = getattr(getattr(self, "parent_window", None), "config", None)
        install_dir = getattr(config, "fbneo_dir", None)
        if not install_dir:
            return None
        for name in ("fbneo64.ini", "fbneo.ini"):
            candidate = Path(install_dir) / name
            if candidate.is_file():
                return candidate
        return Path(install_dir) / "fbneo64.ini"

    def _config(self) -> FBNeoConfig | None:
        """Cria o adapter FBNeo para o arquivo detectado."""
        path = self._ini_path()
        return FBNeoConfig(path) if path else None

    @staticmethod
    def _bool_value(value: str, default: bool = False) -> bool:
        """Converte valores booleanos comuns do FBNeo."""
        if not value:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _int_value(value: str, default: int) -> int:
        """Converte inteiro com fallback seguro."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def refresh(self) -> None:
        """Carrega novamente as opções existentes no arquivo nativo."""
        config = self._config()
        path = self._ini_path()
        if not config or not path:
            self.status_label.setText("FBNeo não configurado.")
            return
        self.path_label.setText(str(path))
        self.status_label.setText("Configuração carregada.")
        self.fullscreen.setChecked(self._bool_value(config.get("bFullScreen"), True))
        self.vsync.setChecked(self._bool_value(config.get("bVSync"), False))
        self.frameskip.setValue(self._int_value(config.get("nFrameskip"), 0))
        self.filtering.setChecked(self._bool_value(config.get("bFilter"), False))
        self.integer_scale.setChecked(self._bool_value(config.get("bIntegerScale"), False))
        ratio = config.get("nAspectRatio", "0")
        ratio_map = {"0": 0, "1": 1, "2": 2, "3": 3}
        self.aspect_ratio.setCurrentIndex(ratio_map.get(ratio, 0))
        self.audio_enabled.setChecked(not self._bool_value(config.get("bNoSound"), False))
        self.sample_rate.setValue(self._int_value(config.get("nAudSampleRate"), 48000))
        self.volume.setValue(self._int_value(config.get("nAudVolume"), 100))
        self.joypad.setChecked(self._bool_value(config.get("bUseDirectInput"), True))
        self.lightgun.setChecked(self._bool_value(config.get("bLightgun"), False))
        self.raw_input.setChecked(self._bool_value(config.get("bRawInput"), False))
        self.deadzone.setValue(self._int_value(config.get("nJoyDeadZone"), 0))
        paths = config.get_rom_paths(4)
        for edit, value in zip(self.rom_paths, paths):
            edit.setText(value)

    def _save(self) -> None:
        """Grava as opções suportadas, preservando chaves e comentários desconhecidos."""
        config = self._config()
        path = self._ini_path()
        if not config or not path:
            self.status_label.setText("FBNeo não configurado.")
            return
        values = {
            "bFullScreen": "1" if self.fullscreen.isChecked() else "0",
            "bVSync": "1" if self.vsync.isChecked() else "0",
            "nFrameskip": str(self.frameskip.value()),
            "bFilter": "1" if self.filtering.isChecked() else "0",
            "bIntegerScale": "1" if self.integer_scale.isChecked() else "0",
            "nAspectRatio": str(self.aspect_ratio.currentIndex()),
            "bNoSound": "0" if self.audio_enabled.isChecked() else "1",
            "nAudSampleRate": str(self.sample_rate.value()),
            "nAudVolume": str(self.volume.value()),
            "bUseDirectInput": "1" if self.joypad.isChecked() else "0",
            "bLightgun": "1" if self.lightgun.isChecked() else "0",
            "bRawInput": "1" if self.raw_input.isChecked() else "0",
            "nJoyDeadZone": str(self.deadzone.value()),
        }
        for key, value in values.items():
            config.set(key, value)
        config.set_rom_paths([edit.text().strip() for edit in self.rom_paths], limit=4)
        config.save(create_backup=True)
        self.status_label.setText("Configuração salva com sucesso.")
        self.settings_changed.emit()
