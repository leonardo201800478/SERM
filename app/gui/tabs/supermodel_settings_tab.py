"""Interface de configurações do Supermodel para o ARCADE MANAGER."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
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

from app.emulators.supermodel_config import SupermodelConfig


class SupermodelSettingsTab(QWidget):
    """Editor seguro das configurações globais do Supermodel.ini."""

    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self._build_ui()
        self._load_installation()

    def _build_ui(self) -> None:
        """Cria as categorias Geral, Vídeo, Áudio e Controles."""
        root = QVBoxLayout(self)
        self.status_label = QLabel()
        root.addWidget(self.status_label)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        self.general_page = QWidget()
        general = QFormLayout(self.general_page)
        self.fullscreen = QCheckBox("Tela cheia")
        self.show_fps = QCheckBox("Mostrar FPS")
        general.addRow("Modo de exibição", self.fullscreen)
        general.addRow("Overlay", self.show_fps)
        self.tabs.addTab(self.general_page, "Geral")

        self.video_page = QWidget()
        video = QFormLayout(self.video_page)
        self.resolution = QLineEdit()
        self.vsync = QCheckBox("VSync")
        self.widescreen = QCheckBox("Widescreen")
        video.addRow("Resolução", self.resolution)
        video.addRow("Sincronização", self.vsync)
        video.addRow("Widescreen", self.widescreen)
        self.tabs.addTab(self.video_page, "Vídeo")

        self.audio_page = QWidget()
        audio = QFormLayout(self.audio_page)
        self.sound = QCheckBox("Som")
        self.mpeg_audio = QCheckBox("Áudio MPEG")
        self.music_volume = QSpinBox()
        self.music_volume.setRange(0, 200)
        self.sound_volume = QSpinBox()
        self.sound_volume.setRange(0, 200)
        audio.addRow("Som", self.sound)
        audio.addRow("MPEG Audio", self.mpeg_audio)
        audio.addRow("Volume da música", self.music_volume)
        audio.addRow("Volume dos efeitos", self.sound_volume)
        self.tabs.addTab(self.audio_page, "Áudio")

        self.input_page = QWidget()
        controls = QFormLayout(self.input_page)
        self.keyboard = QCheckBox("Teclado")
        self.gamepad = QCheckBox("Gamepad")
        self.wheel = QCheckBox("Volante")
        self.pedal = QCheckBox("Pedais")
        self.force_feedback = QCheckBox("Force Feedback")
        controls.addRow("Teclado", self.keyboard)
        controls.addRow("Gamepad", self.gamepad)
        controls.addRow("Volante", self.wheel)
        controls.addRow("Pedais", self.pedal)
        controls.addRow("Force Feedback", self.force_feedback)
        self.tabs.addTab(self.input_page, "Controles")

        buttons = QGroupBox("Arquivo de configuração")
        button_layout = QVBoxLayout(buttons)
        self.path_label = QLabel()
        self.save_button = QPushButton("Salvar configuração")
        self.reload_button = QPushButton("Recarregar")
        button_layout.addWidget(self.path_label)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.reload_button)
        root.addWidget(buttons)

        self.save_button.clicked.connect(self._save)
        self.reload_button.clicked.connect(self._load_installation)

    def _config(self) -> SupermodelConfig | None:
        """Retorna o adapter do Supermodel associado à instalação configurada."""
        config = getattr(getattr(self, "parent_window", None), "config", None)
        install_dir = getattr(config, "supermodel_dir", None)
        return SupermodelConfig(install_dir) if install_dir else None

    def _load_installation(self) -> None:
        """Carrega os valores existentes do Supermodel.ini."""
        adapter = self._config()
        if not adapter or not adapter.ini_path:
            self.status_label.setText("Supermodel não configurado.")
            return
        self.path_label.setText(str(adapter.ini_path))
        self.status_label.setText("Configuração carregada.")
        self._load_bool(self.fullscreen, adapter, "FullScreen", True)
        self._load_bool(self.show_fps, adapter, "ShowFPS", False)
        self.resolution.setText(str(adapter._read_global_key(adapter.ini_path.read_text(encoding="utf-8-sig") if adapter.ini_path.is_file() else "", "XResolution") or "auto"))
        self._load_bool(self.vsync, adapter, "VSync", False)
        self._load_bool(self.widescreen, adapter, "WideScreen", False)
        self._load_bool(self.sound, adapter, "Sound", True)
        self._load_bool(self.mpeg_audio, adapter, "MpegAudio", True)
        self.music_volume.setValue(self._load_int(adapter, "MusicVolume", 100))
        self.sound_volume.setValue(self._load_int(adapter, "SoundVolume", 100))
        self._load_bool(self.keyboard, adapter, "InputAutoTrigger", True)
        self._load_bool(self.gamepad, adapter, "InputSystem", True)
        self._load_bool(self.wheel, adapter, "ForceFeedback", True)
        self._load_bool(self.pedal, adapter, "ForceFeedback", True)
        self._load_bool(self.force_feedback, adapter, "ForceFeedback", True)

    @staticmethod
    def _read_key(adapter: SupermodelConfig, key: str) -> str | None:
        """Lê uma chave global do arquivo de configuração."""
        if not adapter.ini_path or not adapter.ini_path.is_file():
            return None
        return adapter._read_global_key(adapter.ini_path.read_text(encoding="utf-8-sig"), key)

    def _load_bool(self, widget: QCheckBox, adapter: SupermodelConfig, key: str, default: bool) -> None:
        """Carrega uma opção booleana do INI."""
        value = self._read_key(adapter, key)
        widget.setChecked(default if value is None else value.strip().lower() in {"1", "true", "yes", "on"})

    def _load_int(self, adapter: SupermodelConfig, key: str, default: int) -> int:
        """Carrega uma opção inteira com fallback seguro."""
        value = self._read_key(adapter, key)
        try:
            return int(value) if value is not None else default
        except ValueError:
            return default

    def _save(self) -> None:
        """Persiste somente as opções editadas, preservando o restante do INI."""
        adapter = self._config()
        if not adapter:
            self.status_label.setText("Supermodel não configurado.")
            return
        values = {
            "FullScreen": "1" if self.fullscreen.isChecked() else "0",
            "ShowFPS": "1" if self.show_fps.isChecked() else "0",
            "XResolution": self.resolution.text().strip() or "auto",
            "VSync": "1" if self.vsync.isChecked() else "0",
            "WideScreen": "1" if self.widescreen.isChecked() else "0",
            "Sound": "1" if self.sound.isChecked() else "0",
            "MpegAudio": "1" if self.mpeg_audio.isChecked() else "0",
            "MusicVolume": self.music_volume.value(),
            "SoundVolume": self.sound_volume.value(),
            "ForceFeedback": "1" if self.force_feedback.isChecked() else "0",
        }
        try:
            path = adapter.write_settings(values)
        except AttributeError:
            path = adapter.write_global_settings(values)
        self.path_label.setText(str(path))
        self.status_label.setText("Configuração salva com sucesso.")
        self.settings_changed.emit()
