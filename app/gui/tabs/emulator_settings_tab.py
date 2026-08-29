"""Aba central de configurações dos emuladores do ARCADE MANAGER.

A identidade e o rótulo dos emuladores vêm do ``adapter_registry``. As classes
GUI continuam sendo adapters de apresentação e permanecem específicas porque
cada emulador possui uma interface de configuração própria.

As subabas são criadas sob demanda. MAME continua sendo materializado durante
a inicialização porque a MainWindow possui um alvo explícito para o teste de
shaders que depende dessa aba.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from app.emulators.adapter_registry import get_adapter, list_adapters
from app.gui.tabs.fbneo_settings_tab import FBNeoSettingsTab
from app.gui.tabs.flycast_settings_tab import FlycastSettingsTab
from app.gui.tabs.mame_settings_tab import MameSettingsTab
from app.gui.tabs.retroarch_settings_tab import RetroArchSettingsTab
from app.gui.tabs.supermodel_settings_tab import SupermodelSettingsTab


class EmulatorSettingsTab(QWidget):
    """Container das configurações específicas dos cinco emuladores."""

    settings_changed = Signal()

    # O registry é a fonte de verdade para identidade e ordem dos emuladores.
    # Apenas a classe visual permanece aqui, pois ela é responsabilidade da GUI.
    _WIDGET_FACTORIES: dict[str, type[QWidget]] = {
        "mame": MameSettingsTab,
        "flycast": FlycastSettingsTab,
        "supermodel": SupermodelSettingsTab,
        "fbneo": FBNeoSettingsTab,
        "retroarch": RetroArchSettingsTab,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self._tabs: dict[str, QWidget | None] = {
            adapter.emulator: None for adapter in list_adapters()
        }
        self._factories: dict[str, Callable[[], QWidget]] = {}
        self._placeholders: dict[str, QWidget] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        """Cria os containers das subabas usando o registro central."""
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.tab_widget = QTabWidget()
        root.addWidget(self.tab_widget)

        for adapter in list_adapters():
            key = adapter.emulator
            widget_type = self._WIDGET_FACTORIES.get(key)
            if widget_type is None:
                raise RuntimeError(f"Não existe widget de configurações para {key}.")

            self._factories[key] = lambda cls=widget_type: cls(self)
            if key == "mame":
                widget = self._create_tab(key)
            else:
                widget = QWidget()
                widget.setObjectName(f"lazy_{key}_settings")
                self._placeholders[key] = widget
            self.tab_widget.addTab(widget, adapter.label)

        self.tab_widget.currentChanged.connect(self._on_subtab_changed)

        # MAME precisa existir durante a inicialização porque o controlador
        # de teste de shaders da MainWindow usa shader_test_target.
        self._ensure_tab("mame")

    def _create_tab(self, key: str) -> QWidget:
        """Instancia uma subaba específica e registra seus sinais."""
        if key not in self._factories:
            raise KeyError(f"Subaba desconhecida: {key}")
        widget = self._factories[key]()
        self._tabs[key] = widget
        # Mantém os atributos legados usados por código da GUI durante a
        # transição, mas a fonte de verdade passa a ser ``_tabs``.
        setattr(self, f"{key}_tab", widget)
        self._connect_settings_changed(widget)
        return widget

    def _ensure_tab(self, key: str) -> QWidget:
        """Inicializa a subaba sob demanda e substitui seu placeholder."""
        if key not in self._tabs:
            raise KeyError(f"Subaba desconhecida: {key}")
        current = self._tabs[key]
        if current is not None:
            return current

        placeholder = self._placeholders.get(key)
        if placeholder is None:
            raise KeyError(f"Placeholder ausente para a subaba: {key}")
        index = self.tab_widget.indexOf(placeholder)
        widget = self._create_tab(key)
        self._placeholders.pop(key, None)
        self.tab_widget.removeTab(index)
        self.tab_widget.insertTab(index, widget, get_adapter(key).label)
        return widget

    def _connect_settings_changed(self, widget: QWidget | None) -> None:
        """Conecta o sinal de alteração somente quando o widget o fornece."""
        signal = getattr(widget, "settings_changed", None)
        if signal is not None and hasattr(signal, "connect"):
            signal.connect(self.settings_changed)

    def _key_for_widget(self, widget: QWidget | None) -> str | None:
        """Resolve a chave do registry a partir do widget ou placeholder."""
        if widget is None:
            return None
        for adapter in list_adapters():
            key = adapter.emulator
            if widget is self._tabs.get(key) or widget is self._placeholders.get(key):
                return key
        return None

    def _on_subtab_changed(self, index: int) -> None:
        """Inicializa e atualiza somente a subaba selecionada."""
        if index < 0:
            return
        widget = self.tab_widget.widget(index)
        key = self._key_for_widget(widget)
        if key is None:
            return
        if self._tabs[key] is None:
            widget = self._ensure_tab(key)
        self._refresh_widget(key, widget)

    def _refresh_widget(self, key: str, widget: QWidget | None = None) -> None:
        """Recarrega o estado nativo da subaba já inicializada."""
        widget = widget or self._tabs.get(key)
        if widget is None:
            return
        if key == "mame":
            widget._load_ini()
        elif key == "flycast":
            widget.refresh()
        elif key == "supermodel":
            widget._load_installation()
        elif key == "fbneo" or key == "retroarch":
            widget.refresh()

    def refresh(self) -> None:
        """Recarrega somente a subaba atualmente selecionada."""
        index = self.tab_widget.currentIndex()
        if index < 0:
            return
        widget = self.tab_widget.widget(index)
        key = self._key_for_widget(widget)
        if key is None:
            return
        if self._tabs[key] is None:
            widget = self._ensure_tab(key)
        self._refresh_widget(key, widget)

    @property
    def shader_test_target(self) -> MameSettingsTab:
        """Retorna o widget MAME usado pelo teste de shaders existente."""
        widget = self._ensure_tab("mame")
        if not isinstance(widget, MameSettingsTab):
            raise RuntimeError("A subaba MAME foi inicializada com tipo inesperado.")
        return widget
