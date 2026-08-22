"""Dashboard inicial com estado dos emuladores configurados."""
from __future__ import annotations

import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.config.app_config import AppConfig
from app.core.services.emulator_version_service import EmulatorVersionService
from app.gui.widgets.action_button import ActionButton
from app.gui.widgets.base_tab import BaseTab
from app.gui.widgets.emulator_card import EmulatorStatusCard
from app.gui.widgets.section import Section


class HomeTab(BaseTab):
    """Apresenta o estado do projeto e dos emuladores sem executar lógica de negócio."""

    # ------------------------------------------------------------------
    # GRUPO: inicialização e estado
    # ------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = AppConfig()
        self.version_service = EmulatorVersionService()
        self.cards: dict[str, EmulatorStatusCard] = {}
        self._build_ui()
        self.refresh_status()

    # ------------------------------------------------------------------
    # GRUPO: construção da interface
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Monta os grupos visuais da Home usando somente widgets compartilhados."""
        header = Section("MAME Set Builder")
        title = QLabel("Gerenciamento, filtragem e construção de conjuntos de ROMs")
        title.setObjectName("sectionDescription")
        header.add_widget(title)
        self.add_content(header)

        emulators = Section("Emuladores", "Estado dos executáveis configurados para o projeto.")
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        definitions = (
            ("mame", "MAME"),
            ("flycast", "Flycast"),
            ("supermodel", "Supermodel"),
            ("fbneo", "FBNeo"),
        )
        for index, (key, label) in enumerate(definitions):
            card = EmulatorStatusCard(label, emulators)
            self.cards[key] = card
            grid.addWidget(card, index // 2, index % 2)
        emulators.add_layout(grid)
        self.add_content(emulators)

        actions = Section("Ações")
        row = QHBoxLayout()
        refresh = ActionButton(
            "↻ Atualizar",
            "Atualiza silenciosamente o estado e a versão dos executáveis configurados.",
        )
        refresh.clicked.connect(self.refresh_status)
        row.addWidget(refresh)
        mame_site = ActionButton(
            "🌐 Site do MAME",
            "Abre o site oficial do projeto MAME no navegador padrão.",
        )
        mame_site.clicked.connect(self.open_official_site)
        row.addWidget(mame_site)
        row.addStretch(1)
        actions.add_layout(row)
        self.add_content(actions)

        self.set_status("Pronto", "info", "Versões detectadas silenciosamente; nenhum popup é usado.")

    # ------------------------------------------------------------------
    # GRUPO: estado dos emuladores
    # ------------------------------------------------------------------
    def refresh_status(self) -> None:
        """Atualiza os quatro cards sem lançar exceções ou diálogos na interface."""
        paths = {
            "mame": self.config.mame_path,
            "flycast": self.config.flycast_path,
            "supermodel": self.config.supermodel_path,
            "fbneo": self.config.fbneo_path,
        }
        versions = self.version_service.detect_all(paths)
        for name, path in paths.items():
            if not path:
                state = "missing"
            elif not path.is_file():
                state = "warning"
            elif versions.get(name):
                state = "ok"
            else:
                state = "warning"
            self.cards[name].set_state(state, versions.get(name), path)
        self.set_status("Estado atualizado", "success")

    # ------------------------------------------------------------------
    # GRUPO: ações externas
    # ------------------------------------------------------------------
    def open_official_site(self) -> None:
        """Abre o site oficial do MAME no navegador padrão."""
        webbrowser.open("https://www.mamedev.org/")
