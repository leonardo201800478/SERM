"""Aba central de configurações dos emuladores do ARCADE MANAGER.

As subabas específicas são criadas sob demanda. A aba MAME é a única
inicializada antecipadamente porque o teste de shaders existente depende dela.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from app.gui.tabs.mame_settings_tab import MameSettingsTab
from app.gui.tabs.flycast_settings_tab import FlycastSettingsTab
from app.gui.tabs.supermodel_settings_tab import SupermodelSettingsTab
from app.gui.tabs.fbneo_settings_tab import FBNeoSettingsTab
from app.gui.tabs.retroarch_settings_tab import RetroArchSettingsTab


class EmulatorSettingsTab(QWidget):
    """Container das configurações específicas dos cinco emuladores."""

    settings_changed = Signal()

    _TAB_DEFINITIONS = (
        ("mame", "MAME", MameSettingsTab),
        ("flycast", "Flycast", FlycastSettingsTab),
        ("supermodel", "Supermodel", SupermodelSettingsTab),
        ("fbneo", "FBNeo", FBNeoSettingsTab),
        ("retroarch", "RetroArch", RetroArchSettingsTab),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.mame_tab: MameSettingsTab | None = None
        self.flycast_tab: FlycastSettingsTab | None = None
        self.supermodel_tab: SupermodelSettingsTab | None = None
        self.fbneo_tab: FBNeoSettingsTab | None = None
        self.retroarch_tab: RetroArchSettingsTab | None = None
        self._factories: dict[str, Callable[[], QWidget]] = {}
        self._placeholders: dict[str, QWidget] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        """Cria apenas os containers das cinco subabas e inicializa MAME."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.tab_widget = QTabWidget()
        root.addWidget(self.tab_widget)

        for key, label, widget_type in self._TAB_DEFINITIONS:
            self._factories[key] = lambda cls=widget_type: cls(self)
            if key == "mame":
                widget = self._create_tab(key)
            else:
                widget = QWidget()
                widget.setObjectName(f"lazy_{key}_settings")
                self._placeholders[key] = widget
            self.tab_widget.addTab(widget, label)

        self.tab_widget.currentChanged.connect(self._on_subtab_changed)

        # MAME precisa existir durante a inicialização porque o controlador
        # de teste de shaders da MainWindow usa shader_test_target.
        self._ensure_tab("mame")

    def _create_tab(self, key: str) -> QWidget:
        """Instancia uma subaba específica e registra seus sinais."""
        widget = self._factories[key]()
        setattr(self, f"{key}_tab", widget)
        self._connect_settings_changed(widget)
        return widget

    def _ensure_tab(self, key: str) -> QWidget:
        """Inicializa a subaba sob demanda e substitui seu placeholder."""
        current = getattr(self, f"{key}_tab")
        if current is not None:
            return current

        placeholder = self._placeholders.get(key)
        if placeholder is None:
            raise KeyError(f"Subaba desconhecida: {key}")
        index = self.tab_widget.indexOf(placeholder)
        widget = self._create_tab(key)
        self._placeholders.pop(key, None)
        self.tab_widget.removeTab(index)
        self.tab_widget.insertTab(index, widget, dict((item[0], item[1]) for item in self._TAB_DEFINITIONS)[key])
        return widget

    def _connect_settings_changed(self, widget: QWidget | None) -> None:
        """Conecta o sinal de alteração somente quando o widget o fornece."""
        signal = getattr(widget, "settings_changed", None)
        if signal is not None and hasattr(signal, "connect"):
            signal.connect(self.settings_changed)

    def _on_subtab_changed(self, index: int) -> None:
        """Inicializa e atualiza somente a subaba selecionada."""
        widget = self.tab_widget.widget(index)
        key = next((item[0] for item in self._TAB_DEFINITIONS if dict((x[0], x[2]) for x in self._TAB_DEFINITIONS)[item[0]] is type(widget)), None)
        if key is None:
            for candidate, placeholder in self._placeholders.items():
                if widget is placeholder:
                    key = candidate
                    break
        if key is None:
            return

        if key != "mame" and key in self._placeholders:
            widget = self._ensure_tab(key)
        self._refresh_widget(key, widget)

    def _refresh_widget(self, key: str, widget: QWidget | None = None) -> None:
        """Recarrega o estado nativo da subaba já inicializada."""
        widget = widget or getattr(self, f"{key}_tab", None)
        if widget is None:
            return
        if key == "mame":
            widget._load_ini()
        elif key == "flycast":
            widget.refresh()
        elif key == "supermodel":
            widget._load_installation()
        elif key == "fbneo":
            widget.refresh()
        elif key == "retroarch":
            widget.refresh()

    def refresh(self) -> None:
        """Recarrega somente a subaba atualmente selecionada."""
        index = self.tab_widget.currentIndex()
        if index < 0:
            return
        widget = self.tab_widget.widget(index)
        for key, _label, _widget_type in self._TAB_DEFINITIONS:
            if widget is getattr(self, f"{key}_tab", None):
                self._refresh_widget(key, widget)
                return
            if widget is self._placeholders.get(key):
                widget = self._ensure_tab(key)
                self._refresh_widget(key, widget)
                return

    @property
    def shader_test_target(self) -> MameSettingsTab:
        """Retorna o widget MAME usado pelo teste de shaders existente."""
        widget = self._ensure_tab("mame")
        if not isinstance(widget, MameSettingsTab):
            raise RuntimeError("A subaba MAME foi inicializada com tipo inesperado.")
        return widget
