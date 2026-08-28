"""Interface de configuração do RetroArch orientada pelo schema canônico."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from app.emulators.adapter_registry import get_adapter
from app.emulators.config_schema import Setting
from app.emulators.retroarch_config import RetroArchConfig


class RetroArchSettingsTab(QWidget):
    """Editor das configurações globais do retroarch.cfg.

    Os controles são derivados exclusivamente do ``RETROARCH_SCHEMA`` exposto
    pelo adapter. A classe mantém os atributos históricos dos widgets para
    compatibilidade com código externo e testes existentes.
    """

    settings_changed = Signal()
    DOMAINS = ("general", "video", "audio", "input", "shaders")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.widgets: dict[str, QWidget] = {}
        self._build_ui()
        self.refresh()

    @property
    def adapter(self):
        """Retorna o contrato central do RetroArch."""
        return get_adapter("retroarch")

    def _build_ui(self) -> None:
        """Cria as páginas de configuração diretamente do schema."""
        root = QVBoxLayout(self)
        self.status_label = QLabel()
        root.addWidget(self.status_label)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        for domain in self.DOMAINS:
            self._create_schema_tab(domain)

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

    def _create_schema_tab(self, domain: str) -> None:
        """Materializa uma página e seus controles a partir do schema."""
        page = QWidget()
        form = QFormLayout(page)
        for setting in self.adapter.schema(domain):
            widget = self._create_control(setting)
            self.widgets[setting.key] = widget
            form.addRow(setting.label, widget)
            if setting.description:
                widget.setToolTip(setting.description)
            setattr(self, self._attribute_name(setting.key), widget)
        self.tabs.addTab(page, self._domain_label(domain))

    @staticmethod
    def _attribute_name(key: str) -> str:
        """Converte uma chave canônica em nome de atributo da GUI."""
        return key

    @staticmethod
    def _domain_label(domain: str) -> str:
        """Converte identificadores de domínio em títulos da interface."""
        return {
            "general": "Geral",
            "video": "Vídeo",
            "audio": "Áudio",
            "input": "Controles",
            "shaders": "Shaders",
        }.get(domain, domain.title())

    def _create_control(self, setting: Setting) -> QWidget:
        """Cria o widget adequado ao ``control`` declarado no schema."""
        if setting.control == "bool":
            return QCheckBox(setting.label)
        if setting.control == "choice":
            combo = QComboBox()
            combo.addItems([value for value, _label in setting.choices])
            combo.setEditable(True)
            return combo
        if setting.control == "int":
            spin = QSpinBox()
            minimum, maximum = self._int_range(setting.key)
            spin.setRange(minimum, maximum)
            return spin
        if setting.control == "float":
            spin = QDoubleSpinBox()
            minimum, maximum = self._float_range(setting.key)
            spin.setRange(minimum, maximum)
            spin.setDecimals(3)
            spin.setSingleStep(0.01)
            return spin
        return QLineEdit()

    @staticmethod
    def _int_range(key: str) -> tuple[int, int]:
        """Retorna limites seguros para inteiros administrados pelo RetroArch."""
        ranges = {
            "video_fullscreen_x": (0, 16384),
            "video_fullscreen_y": (0, 16384),
            "video_hdr_max_nits": (100, 10000),
            "audio_out_rate": (8000, 192000),
            "audio_latency": (0, 1000),
        }
        return ranges.get(key, (-2_147_483_648, 2_147_483_647))

    @staticmethod
    def _float_range(key: str) -> tuple[float, float]:
        """Retorna limites seguros para floats do schema RetroArch."""
        ranges = {
            "video_refresh_rate": (1.0, 1000.0),
            "input_axis_threshold": (0.0, 1.0),
            "input_analog_deadzone": (0.0, 1.0),
            "input_analog_sensitivity": (0.0, 10.0),
        }
        return ranges.get(key, (-1_000_000.0, 1_000_000.0))

    @staticmethod
    def _bool(value: str | None, default: bool = False) -> bool:
        """Converte booleanos do RetroArch com fallback explícito."""
        if value is None or not value.strip():
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _int(value: str | None, default: int) -> int:
        """Converte texto para inteiro com fallback."""
        try:
            return int(float(value)) if value is not None and value.strip() else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _float(value: str | None, default: float) -> float:
        """Converte texto para float com fallback."""
        try:
            return float(value) if value is not None and value.strip() else default
        except (TypeError, ValueError):
            return default

    def _set_combo(self, combo: QComboBox, value: str, default: str) -> None:
        """Seleciona valor conhecido ou preserva valor desconhecido."""
        index = combo.findText(value)
        if index < 0 and value:
            combo.addItem(value)
            index = combo.findText(value)
        combo.setCurrentIndex(index if index >= 0 else combo.findText(default))

    def _set_widget_value(self, setting: Setting, value: str | None) -> None:
        """Aplica um valor físico ao widget conforme o tipo declarado no schema."""
        widget = self.widgets[setting.key]
        if setting.control == "bool":
            assert isinstance(widget, QCheckBox)
            widget.setChecked(self._bool(value, bool(setting.default)))
        elif setting.control == "choice":
            assert isinstance(widget, QComboBox)
            self._set_combo(widget, value or str(setting.default), str(setting.default))
        elif setting.control == "int":
            assert isinstance(widget, QSpinBox)
            widget.setValue(self._int(value, int(setting.default)))
        elif setting.control == "float":
            assert isinstance(widget, QDoubleSpinBox)
            widget.setValue(self._float(value, float(setting.default)))
        else:
            assert isinstance(widget, QLineEdit)
            widget.setText(value or str(setting.default) if setting.default is not None else "")

    def _widget_value(self, setting: Setting) -> Any:
        """Extrai o valor canônico do widget segundo o tipo declarado."""
        widget = self.widgets[setting.key]
        if setting.control == "bool":
            return isinstance(widget, QCheckBox) and widget.isChecked()
        if setting.control == "choice":
            return widget.currentText() if isinstance(widget, QComboBox) else setting.default
        if setting.control == "int":
            return widget.value() if isinstance(widget, QSpinBox) else setting.default
        if setting.control == "float":
            return widget.value() if isinstance(widget, QDoubleSpinBox) else setting.default
        return widget.text().strip() if isinstance(widget, QLineEdit) else setting.default

    def _config_path(self) -> Path | None:
        """Localiza retroarch.cfg a partir da instalação configurada pelo projeto."""
        config = getattr(self.parent_window, "config", None)
        install_dir = getattr(config, "retroarch_dir", None)
        if not install_dir:
            return None
        candidates = [Path(install_dir) / "retroarch.cfg", Path(install_dir) / "config" / "retroarch.cfg"]
        return next((path for path in candidates if path.is_file()), candidates[0])

    def _config(self) -> RetroArchConfig | None:
        """Cria o adapter nativo para o arquivo configurado."""
        path = self._config_path()
        return RetroArchConfig(path) if path else None

    def refresh(self) -> None:
        """Recarrega os valores físicos sem reconstruir a interface."""
        config = self._config()
        path = self._config_path()
        if not config or not path:
            self.status_label.setText("RetroArch não configurado.")
            return
        self.path_label.setText(str(path))
        self.status_label.setText("Configuração carregada.")
        for domain in self.DOMAINS:
            for setting in self.adapter.schema(domain):
                self._set_widget_value(setting, config.get(setting.key))

    def _save(self) -> None:
        """Grava somente as opções pertencentes ao schema canônico do RetroArch."""
        config = self._config()
        path = self._config_path()
        if not config or not path:
            self.status_label.setText("RetroArch não configurado.")
            return
        values: dict[str, Any] = {}
        for domain in self.DOMAINS:
            for setting in self.adapter.schema(domain):
                values[setting.key] = self._widget_value(setting)
        config.set_many(values)
        config.save(create_backup=True)
        self.status_label.setText("Configuração salva com sucesso.")
        self.settings_changed.emit()
