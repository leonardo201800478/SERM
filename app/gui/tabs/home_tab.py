"""Home do MAME Set Builder.

A Home somente apresenta o estado normalizado dos emuladores. Descoberta,
validação de configuração e persistência ficam nos serviços de domínio.
"""
from __future__ import annotations

import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config.app_config import AppConfig
from app.core.services.emulator_status_service import EmulatorStatus, EmulatorStatusService


class HomeTab(QWidget):
    """Apresenta o estado dos emuladores suportados pelo projeto."""

    EMULATOR_LABELS = {
        "mame": "MAME",
        "flycast": "Flycast",
        "supermodel": "Supermodel",
        "fbneo": "FBNeo",
    }

    EMULATOR_SITES = {
        "mame": "https://www.mamedev.org/",
        "flycast": "https://flycast.dev/",
        "supermodel": "https://supermodel3.com/",
        "fbneo": "https://github.com/finalburnneo/FBNeo",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = AppConfig()
        self.status_service = EmulatorStatusService(config=self.config)
        self.statuses: dict[str, EmulatorStatus] = {}
        self.cards: dict[str, tuple[QLabel, QLabel, QLabel]] = {}
        self.setup_ui()
        self.refresh_status()

    def setup_ui(self):
        """Monta a Home em grupos independentes para facilitar manutenção."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # ------------------------------------------------------------------
        # CABEÇALHO
        # ------------------------------------------------------------------
        title = QLabel("MAME Set Builder")
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(28)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)

        subtitle = QLabel(
            "Gerenciamento, filtragem e construção de conjuntos de ROMs para arcades"
        )
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle_font = QFont()
        subtitle_font.setPointSize(12)
        subtitle.setFont(subtitle_font)
        main_layout.addWidget(subtitle)
        main_layout.addSpacing(10)

        # ------------------------------------------------------------------
        # STATUS DOS EMULADORES
        # ------------------------------------------------------------------
        status_frame = QFrame()
        status_frame.setObjectName("emulatorStatusFrame")
        status_frame.setStyleSheet(
            """
            QFrame#emulatorStatusFrame {
                background-color: #151515;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                padding: 10px;
            }
            QFrame#emulatorCard {
                background-color: #202020;
                border: 1px solid #414141;
                border-radius: 7px;
            }
            QLabel#emulatorName {
                font-size: 15px;
                font-weight: bold;
            }
            QLabel#emulatorDetail {
                color: #b8b8b8;
            }
            """
        )
        status_layout = QGridLayout(status_frame)
        status_layout.setHorizontalSpacing(10)
        status_layout.setVerticalSpacing(10)

        for index, name in enumerate(self.EMULATOR_LABELS):
            card, labels = self._create_emulator_card(name)
            row, column = divmod(index, 2)
            status_layout.addWidget(card, row, column)
            self.cards[name] = labels

        main_layout.addWidget(status_frame)

        # ------------------------------------------------------------------
        # AÇÕES
        # ------------------------------------------------------------------
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        btn_refresh = QPushButton("🔄 Atualizar emuladores")
        btn_refresh.setToolTip(
            "Redescobre os quatro emuladores configurados, valida suas configurações "
            "e atualiza o estado apresentado nesta tela."
        )
        btn_refresh.clicked.connect(self.refresh_status)
        actions_layout.addWidget(btn_refresh)

        btn_directories = QPushButton("📁 Configurar diretórios")
        btn_directories.setToolTip(
            "Abre a aba Diretórios para configurar os executáveis e caminhos utilizados "
            "pelo MAME Set Builder."
        )
        btn_directories.clicked.connect(self.open_directories)
        actions_layout.addWidget(btn_directories)

        actions_layout.addStretch()
        main_layout.addLayout(actions_layout)
        main_layout.addStretch()

        # ------------------------------------------------------------------
        # RODAPÉ
        # ------------------------------------------------------------------
        footer = QLabel(
            "O software não distribui ROMs. Trabalha apenas com arquivos que o usuário já possui."
        )
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color: #888; font-size: 10px;")
        main_layout.addWidget(footer)

    def _create_emulator_card(self, name: str) -> tuple[QFrame, tuple[QLabel, QLabel, QLabel]]:
        """Cria um card padronizado para um emulador."""
        card = QFrame()
        card.setObjectName("emulatorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)

        name_label = QLabel(self.EMULATOR_LABELS[name])
        name_label.setObjectName("emulatorName")
        layout.addWidget(name_label)

        status_label = QLabel("⏳ Verificando...")
        status_label.setObjectName("emulatorDetail")
        layout.addWidget(status_label)

        version_label = QLabel("Versão: —")
        version_label.setObjectName("emulatorDetail")
        layout.addWidget(version_label)

        path_label = QLabel("Caminho: —")
        path_label.setObjectName("emulatorDetail")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        site_button = QPushButton("🌐 Site oficial")
        site_button.setToolTip("Abre o site oficial do emulador no navegador.")
        site_button.clicked.connect(lambda _checked=False, key=name: self.open_official_site(key))
        layout.addWidget(site_button)

        return card, (status_label, version_label, path_label)

    def refresh_status(self):
        """Atualiza a descoberta dos emuladores e os cards da Home silenciosamente."""
        try:
            self.config.load()
            self.statuses = self.status_service.refresh()
        except Exception as exc:
            # A Home não deve impedir a inicialização da aplicação por uma falha
            # de descoberta. O erro é apresentado somente no card correspondente.
            self.statuses = {
                name: EmulatorStatus(name, None, None, None, "error")
                for name in self.EMULATOR_LABELS
            }
            for name in self.EMULATOR_LABELS:
                self._set_card(name, "error", None, None, str(exc))
            return

        for name in self.EMULATOR_LABELS:
            self._set_card_from_status(name, self.statuses[name])

    def _set_card_from_status(self, name: str, status: EmulatorStatus):
        """Renderiza o estado normalizado de um emulador."""
        path = str(status.executable or status.root or "—")
        self._set_card(name, status.status, status.version, path)

    def _set_card(
        self,
        name: str,
        status: str,
        version: str | None,
        path: str | None,
        detail: str | None = None,
    ):
        """Aplica textos e estado visual ao card de um emulador."""
        labels = self.cards.get(name)
        if labels is None:
            return
        status_label, version_label, path_label = labels

        status_text, status_color = {
            "ready": ("● Pronto", "#55d66b"),
            "ready_generated": ("● Pronto (configuração gerada)", "#55d66b"),
            "configuration_missing": ("● Configuração ausente", "#e5c454"),
            "configuration_corrupt": ("● Configuração inválida", "#e59b54"),
            "error": ("● Erro na descoberta", "#e05a5a"),
            "not_found": ("● Não configurado", "#a8a8a8"),
        }.get(status, (f"● {status}", "#a8a8a8"))

        status_label.setText(status_text)
        status_label.setStyleSheet(f"color: {status_color}; font-weight: bold;")
        version_label.setText(f"Versão: {version or '—'}")
        path_label.setText(f"Caminho: {detail or path or '—'}")

    def open_directories(self):
        """Seleciona a aba Diretórios sem duplicar a lógica de navegação."""
        if self.parent_window and hasattr(self.parent_window, "tab_widget"):
            for index in range(self.parent_window.tab_widget.count()):
                if self.parent_window.tab_widget.tabText(index) == "Diretórios":
                    self.parent_window.tab_widget.setCurrentIndex(index)
                    return

    def open_official_site(self, emulator: str):
        """Abre o endereço oficial do emulador selecionado."""
        url = self.EMULATOR_SITES.get(emulator)
        if url:
            webbrowser.open(url)
