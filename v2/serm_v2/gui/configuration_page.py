"""Workspace de configuração organizado do SERM V2."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QTabWidget, QVBoxLayout, QWidget

from .appearance_language_page import AppearanceLanguagePage
from .emulator_directories_page import DirectoriesPage
from .emulator_settings_page import EmulatorSettingsPage
from .emulator_shaders_bezels_page import EmulatorShadersBezelsPage
from .input_controls_page import InputControlsPage
from .sound_settings_page import SoundSettingsPage
from .tools_directories import ToolsDirectoriesPage
from .ui_preferences import UiPreferences


class ConfigurationPage(QWidget):
    """Centraliza as configurações do SERM em uma área única e compacta."""

    ENTRIES = (
        ("01", "Diretórios", "Pastas, arquivos de configuração e dados dos emuladores.", "directories"),
        ("02", "Ferramentas", "Executáveis auxiliares utilizados pelo SERM.", "tools"),
        ("03", "Emuladores", "Executáveis, versões e parâmetros dos emuladores.", "emulators"),
        ("04", "Vídeo", "Shaders, bezels e apresentação de vídeo.", "video"),
        ("05", "Som", "Configurações iniciais de áudio do ambiente SERM.", "sound"),
        ("06", "Controles", "Detecção, identidade e diagnóstico dos dispositivos de entrada.", "controls"),
        ("07", "Aparência e idioma", "Tema, idioma e preferências da interface.", "settings"),
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pages: list[QWidget] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)
        header = QFrame(); header.setObjectName("configurationHeader")
        header_layout = QVBoxLayout(header); header_layout.setContentsMargins(12, 9, 12, 9); header_layout.setSpacing(2)
        title = QLabel("CONFIGURAÇÃO"); title.setObjectName("configurationTitle")
        subtitle = QLabel("Central de configuração do ambiente SERM V2"); subtitle.setObjectName("configurationSubtitle")
        header_layout.addWidget(title); header_layout.addWidget(subtitle); root.addWidget(header)

        workspace = QFrame(); workspace.setObjectName("configurationWorkspace")
        workspace_layout = QHBoxLayout(workspace); workspace_layout.setContentsMargins(0, 0, 0, 0); workspace_layout.setSpacing(8)
        navigation = QFrame(); navigation.setObjectName("configurationNavigation"); navigation.setMinimumWidth(205); navigation.setMaximumWidth(245)
        nav_layout = QVBoxLayout(navigation); nav_layout.setContentsMargins(8, 8, 8, 8); nav_layout.setSpacing(6)
        nav_title = QLabel("SEÇÕES"); nav_title.setObjectName("configurationNavTitle")
        nav_hint = QLabel("Selecione uma área para editar."); nav_hint.setObjectName("configurationNavHint"); nav_hint.setWordWrap(True)
        nav_layout.addWidget(nav_title); nav_layout.addWidget(nav_hint)
        self.navigation_list = QListWidget(); self.navigation_list.setObjectName("configurationNavigationList"); self.navigation_list.setUniformItemSizes(True); self.navigation_list.setSpacing(2)
        for number, title_text, _, _ in self.ENTRIES:
            self.navigation_list.addItem(QListWidgetItem(f"{number}   {title_text}"))
        self.navigation_list.currentRowChanged.connect(self._select_page); nav_layout.addWidget(self.navigation_list, 1); workspace_layout.addWidget(navigation)

        content = QFrame(); content.setObjectName("configurationContent")
        content_layout = QVBoxLayout(content); content_layout.setContentsMargins(12, 10, 12, 10); content_layout.setSpacing(7)
        self.section_title = QLabel(); self.section_title.setObjectName("configurationSectionTitle")
        self.section_description = QLabel(); self.section_description.setObjectName("configurationSectionDescription"); self.section_description.setWordWrap(True)
        content_layout.addWidget(self.section_title); content_layout.addWidget(self.section_description)
        self.tabs = QTabWidget(); self.tabs.setObjectName("configurationPages"); self.tabs.tabBar().hide(); self.tabs.setDocumentMode(True)
        self.directories_page = DirectoriesPage(self)
        self.tools_page = ToolsDirectoriesPage(self)
        self.emulators_page = EmulatorSettingsPage(self)
        self.video_page = EmulatorShadersBezelsPage(self)
        self.sound_page = SoundSettingsPage(self)
        self.controls_page = InputControlsPage(self)
        self.appearance_page = AppearanceLanguagePage(self)
        self._pages = [self.directories_page, self.tools_page, self.emulators_page, self.video_page, self.sound_page, self.controls_page, self.appearance_page]
        for page in self._pages: self.tabs.addTab(page, "")
        content_layout.addWidget(self.tabs, 1); workspace_layout.addWidget(content, 1); root.addWidget(workspace, 1)
        self.appearance_page.language_changed.connect(lambda _language: self.retranslate_ui())
        self.retranslate_ui(); self.navigation_list.setCurrentRow(0)
        self.setStyleSheet(
            "QFrame#configurationHeader{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #111c2d,stop:1 #0d1727);border:1px solid #2a3b55;border-radius:9px;}"
            "QLabel#configurationTitle{color:#e7eef7;font-size:17px;font-weight:700;}QLabel#configurationSubtitle{color:#8fa5bb;font-size:8pt;}"
            "QFrame#configurationNavigation{background:#0c1422;border:1px solid #263750;border-radius:9px;}QLabel#configurationNavTitle{color:#a9bdd1;font-size:8pt;font-weight:700;}QLabel#configurationNavHint{color:#71859a;font-size:8pt;}"
            "QListWidget#configurationNavigationList{background:transparent;border:0;padding:2px;}QListWidget#configurationNavigationList::item{color:#9eb1c5;padding:8px 9px;border:1px solid transparent;border-radius:6px;min-height:20px;}QListWidget#configurationNavigationList::item:hover{background:#131f31;color:#dbe7f4;}QListWidget#configurationNavigationList::item:selected{background:#172b42;color:#eaf5ff;border:1px solid #3e6d8b;}"
            "QFrame#configurationContent{background:#0b1321;border:1px solid #263750;border-radius:9px;}QLabel#configurationSectionTitle{color:#e7eef7;font-size:14px;font-weight:650;}QLabel#configurationSectionDescription{color:#8fa5bb;font-size:8pt;}"
            "QTabWidget#configurationPages{border:0;background:transparent;}QTabWidget#configurationPages::pane{border:0;background:transparent;}")

    def _select_page(self, index: int) -> None:
        if 0 <= index < len(self._pages):
            self.tabs.setCurrentIndex(index); self.section_title.setText(self._entry_title(index)); self.section_description.setText(self.ENTRIES[index][2]); self._refresh_current()

    def _entry_title(self, index: int) -> str:
        return UiPreferences.text(self.ENTRIES[index][3])

    def _refresh_current(self) -> None:
        page = self.tabs.currentWidget(); refresh = getattr(page, "refresh", None)
        if callable(refresh): refresh()

    def retranslate_ui(self) -> None:
        for index, (_, _, _, key) in enumerate(self.ENTRIES):
            item = self.navigation_list.item(index)
            if item: item.setText(f"{self.ENTRIES[index][0]}   {UiPreferences.text(key)}")
        current = self.navigation_list.currentRow()
        if current >= 0:
            self.section_title.setText(self._entry_title(current)); self.section_description.setText(self.ENTRIES[current][2])

    def refresh(self) -> None:
        self._refresh_current()


__all__ = ["ConfigurationPage"]
