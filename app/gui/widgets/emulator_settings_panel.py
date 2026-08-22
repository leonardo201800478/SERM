"""Layer-3 reusable emulator settings editor."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from app.emulators.config_backend import EmulatorConfigBackend
from app.emulators.config_mapping import physical_key
from app.emulators.config_resolver import ConfigResolver, ResolvedSetting
from app.emulators.config_schema import Setting
from app.emulators.settings_store import JsonSettingsStore


class EmulatorSettingsPanel(QWidget):
    """Standard settings editor with autosave, tooltips and safe reset."""

    value_changed = Signal(str, object)
    reset_requested = Signal()
    config_error = Signal(str)

    def __init__(self, emulator: str, domain: str, resolver: ConfigResolver | None = None,
                 store: JsonSettingsStore | None = None, backend: EmulatorConfigBackend | None = None,
                 config_path: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.emulator = emulator.strip().lower()
        self.domain = domain
        self.resolver = resolver or ConfigResolver()
        self.store = store or JsonSettingsStore("data/config/gui_settings.json")
        self.backend = backend
        self.config_path = config_path
        self._widgets: dict[str, QWidget] = {}
        self._resolved: dict[str, ResolvedSetting] = {}
        self._building = True
        self._build()
        self._building = False

    def _build(self) -> None:
        """Create one editor per canonical schema setting."""
        root = QVBoxLayout(self)
        form = QFormLayout()
        group = QGroupBox(self.domain.replace("_", " ").title(), self)
        group.setLayout(form)
        root.addWidget(group)

        for resolved in self.resolver.settings(self.emulator, self.domain):
            self._resolved[resolved.setting.key] = resolved
            widget = self._make_widget(resolved)
            if widget is None:
                continue
            widget.setEnabled(resolved.available)
            tooltip = resolved.setting.description
            if resolved.reason:
                tooltip += f"\n\n{resolved.reason}"
            widget.setToolTip(tooltip)
            form.addRow(resolved.setting.label, widget)
            self._widgets[resolved.setting.key] = widget

        reset = QPushButton("Restaurar padrões", self)
        reset.setToolTip("Restaura esta seção aos valores padrão e grava no emulador.")
        reset.clicked.connect(self.reset_defaults)
        root.addWidget(reset)

    def _make_widget(self, resolved: ResolvedSetting) -> QWidget | None:
        """Create a Qt control from the canonical schema contract."""
        setting: Setting = resolved.setting
        value = self._read_value(setting)

        if setting.control == "bool":
            widget = QCheckBox()
            widget.setChecked(bool(value))
            widget.toggled.connect(lambda v, k=setting.key: self._changed(k, v))
            return widget
        if setting.control == "choice":
            widget = QComboBox()
            for value_key, label in setting.choices:
                widget.addItem(label, value_key)
            index = widget.findData(value)
            if index >= 0:
                widget.setCurrentIndex(index)
            widget.currentIndexChanged.connect(lambda _i, k=setting.key, w=widget: self._changed(k, w.currentData()))
            return widget
        if setting.control == "int":
            widget = QSpinBox()
            widget.setRange(-2_147_483_648, 2_147_483_647)
            widget.setValue(int(value))
            widget.valueChanged.connect(lambda v, k=setting.key: self._changed(k, v))
            return widget
        if setting.control == "float":
            widget = QDoubleSpinBox()
            widget.setRange(-1_000_000.0, 1_000_000.0)
            widget.setValue(float(value))
            widget.valueChanged.connect(lambda v, k=setting.key: self._changed(k, v))
            return widget
        if setting.control in {"string", "path", "secret"}:
            widget = QLineEdit("" if value is None else str(value))
            if setting.control == "secret":
                widget.setEchoMode(QLineEdit.EchoMode.Password)
            widget.editingFinished.connect(lambda k=setting.key, w=widget: self._changed(k, w.text()))
            return widget
        return None

    def _read_value(self, setting: Setting) -> Any:
        """Read the physical emulator value first, falling back to GUI state/default."""
        key = physical_key(self.emulator, setting.key)
        if self.backend is not None and key is not None:
            return self.backend.get(key, self.store.get(self.emulator, setting.key, setting.default))
        return self.store.get(self.emulator, setting.key, setting.default)

    def _changed(self, key: str, value: Any) -> None:
        """Persist a change to the emulator and mirror it in application state."""
        if self._building:
            return
        self.store.set(self.emulator, key, value)
        physical = physical_key(self.emulator, key)
        if self.backend is not None and physical is not None:
            try:
                self.backend.set(physical, value)
            except Exception as exc:  # backend errors must not crash the GUI thread
                self.config_error.emit(str(exc))
                return
        self.value_changed.emit(key, value)

    def reset_defaults(self) -> None:
        """Restore visible defaults and persist them to both state and emulator."""
        defaults = self.resolver.defaults(self.emulator, self.domain)
        self.store.update(self.emulator, defaults)
        physical: dict[str, Any] = {}
        for key, value in defaults.items():
            mapped = physical_key(self.emulator, key)
            if mapped is not None:
                physical[mapped] = value
            widget = self._widgets.get(key)
            if widget is not None:
                self._set_widget_value(widget, value)
        if self.backend is not None and physical:
            try:
                self.backend.update(physical)
            except Exception as exc:
                self.config_error.emit(str(exc))
                return
        self.reset_requested.emit()

    @staticmethod
    def _set_widget_value(widget: QWidget, value: Any) -> None:
        """Update a supported Qt editor without duplicating persistence logic."""
        if isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QComboBox):
            index = widget.findData(value)
            if index >= 0:
                widget.setCurrentIndex(index)
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(value))
        elif isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(value))
        elif isinstance(widget, QLineEdit):
            widget.setText("" if value is None else str(value))
