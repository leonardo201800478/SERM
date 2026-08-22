"""Home do MAME Set Builder.

A Home apresenta o estado normalizado dos emuladores e concentra o fluxo de
instalação oficial. Descoberta, persistência e instalação permanecem em serviços.
"""
from __future__ import annotations

import webbrowser
from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config.app_config import AppConfig
from app.core.services.emulator_persistence_service import EmulatorPersistenceService
from app.core.services.emulator_status_service import EmulatorStatus, EmulatorStatusService
from app.gui.widgets.emulator_directories_dialog import EmulatorDirectoriesDialog
from app.gui.widgets.emulator_install_worker import EmulatorInstallWorker


class HomeTab(QWidget):
    """Apresenta o estado e a instalação dos emuladores suportados."""

    EMULATOR_LABELS = {
        "mame": "MAME",
        "flycast": "Flycast",
        "supermodel": "Supermodel",
        "fbneo": "FBNeo",
    }

    EMULATOR_SITES = {
        "mame": "https://github.com/mamedev/mame",
        "flycast": "https://github.com/flyinghead/flycast",
        "supermodel": "https://github.com/trzy/supermodel",
        "fbneo": "https://github.com/finalburnneo/FBNeo",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = getattr(parent, "config", None) or AppConfig()
        database = getattr(parent, "db", None)
        persistence = EmulatorPersistenceService(database) if database is not None else None
        self.status_service = EmulatorStatusService(config=self.config, persistence=persistence)
        self.statuses: dict[str, EmulatorStatus] = {}
        self.cards: dict[str, tuple[QLabel, QLabel, QLabel, QProgressBar, QPushButton]] = {}
        self._install_thread: QThread | None = None
        self._install_worker: EmulatorInstallWorker | None = None
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

        subtitle = QLabel("Gerenciamento, filtragem e construção de conjuntos de ROMs para arcades")
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
            QFrame#emulatorStatusFrame { background-color: #151515; border: 1px solid #3d3d3d; border-radius: 8px; padding: 10px; }
            QFrame#emulatorCard { background-color: #202020; border: 1px solid #414141; border-radius: 7px; }
            QLabel#emulatorName { font-size: 15px; font-weight: bold; }
            QLabel#emulatorDetail { color: #b8b8b8; }
            QProgressBar { min-height: 8px; max-height: 8px; }
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
        # AÇÕES GERAIS
        # ------------------------------------------------------------------
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        btn_refresh = QPushButton("🔄 Atualizar emuladores")
        btn_refresh.setToolTip("Redescobre os emuladores configurados e atualiza os estados exibidos na Home.")
        btn_refresh.clicked.connect(self.refresh_status)
        actions_layout.addWidget(btn_refresh)

        btn_directories = QPushButton("📁 Configurar diretórios")
        btn_directories.setToolTip(
            "Define a pasta padrão de instalação de MAME, Flycast, Supermodel e FBNeo. "
            "Esses diretórios também serão usados pelos botões de download."
        )
        btn_directories.clicked.connect(self.open_emulator_directories)
        actions_layout.addWidget(btn_directories)

        actions_layout.addStretch()
        main_layout.addLayout(actions_layout)
        main_layout.addStretch()

        footer = QLabel("O software não distribui ROMs. Trabalha apenas com arquivos que o usuário já possui.")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color: #888; font-size: 10px;")
        main_layout.addWidget(footer)

    def _create_emulator_card(self, name: str):
        """Cria o card do emulador, incluindo instalação e progresso."""
        card = QFrame()
        card.setObjectName("emulatorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)

        name_label = QLabel(self.EMULATOR_LABELS[name])
        name_label.setObjectName("emulatorName")
        layout.addWidget(name_label)

        status_label = QLabel("⏳ Verificando…")
        status_label.setObjectName("emulatorDetail")
        layout.addWidget(status_label)

        version_label = QLabel("Versão: —")
        version_label.setObjectName("emulatorDetail")
        layout.addWidget(version_label)

        path_label = QLabel("Instalação: —")
        path_label.setObjectName("emulatorDetail")
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setTextVisible(False)
        progress.hide()
        layout.addWidget(progress)

        row = QHBoxLayout()
        install_button = QPushButton("⬇ Baixar / atualizar")
        install_button.setToolTip(
            "Baixa o pacote oficial Windows x64 e o extrai diretamente no diretório configurado, "
            "sem criar uma pasta extra."
        )
        install_button.clicked.connect(lambda _checked=False, key=name: self.install_emulator(key))
        row.addWidget(install_button)

        site_button = QPushButton("🌐 Repositório")
        site_button.setToolTip("Abre o repositório oficial do emulador no GitHub.")
        site_button.clicked.connect(lambda _checked=False, key=name: self.open_official_site(key))
        row.addWidget(site_button)
        layout.addLayout(row)

        return card, (status_label, version_label, path_label, progress, install_button)

    def refresh_status(self):
        """Atualiza a descoberta dos emuladores e os cards silenciosamente."""
        try:
            self.config.load()
            self.statuses = self.status_service.refresh()
        except Exception as exc:
            self.statuses = {name: EmulatorStatus(name, None, None, None, "error") for name in self.EMULATOR_LABELS}
            for name in self.EMULATOR_LABELS:
                self._set_card(name, "error", None, None, str(exc))
            return

        for name in self.EMULATOR_LABELS:
            self._set_card_from_status(name, self.statuses[name])

    def _set_card_from_status(self, name: str, status: EmulatorStatus):
        """Renderiza o estado normalizado de um emulador."""
        directory = getattr(self.config, f"{name}_dir", None)
        path = str(directory or status.root or status.executable or "—")
        self._set_card(name, status.status, status.version, path)

    def _set_card(self, name: str, status: str, version: str | None, path: str | None, detail: str | None = None):
        """Aplica textos e estado visual ao card de um emulador."""
        labels = self.cards.get(name)
        if labels is None:
            return
        status_label, version_label, path_label, progress, install_button = labels
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
        path_label.setText(f"Instalação: {detail or path or '—'}")
        install_button.setEnabled(self._install_thread is None)

    def open_emulator_directories(self):
        """Abre o diálogo dos diretórios de instalação e atualiza a Home após salvar."""
        dialog = EmulatorDirectoriesDialog(self.config, self)
        if dialog.exec():
            self.config.load()
            self.refresh_status()

    def install_emulator(self, emulator: str):
        """Valida o diretório e inicia a instalação oficial em segundo plano."""
        destination = getattr(self.config, f"{emulator}_dir", None)
        if not destination:
            self.open_emulator_directories()
            destination = getattr(self.config, f"{emulator}_dir", None)
            if not destination:
                return

        destination = Path(destination)
        labels = self.cards[emulator]
        progress = labels[3]
        progress.show()
        progress.setRange(0, 0)
        labels[0].setText("● Baixando / instalando…")
        labels[0].setStyleSheet("color: #e5c454; font-weight: bold;")

        self._install_thread = QThread(self)
        self._install_worker = EmulatorInstallWorker(emulator, destination)
        self._install_worker.moveToThread(self._install_thread)
        self._install_thread.started.connect(self._install_worker.run)
        self._install_worker.progress.connect(lambda received, total, p=progress: self._update_download_progress(p, received, total))
        self._install_worker.finished.connect(self._install_finished)
        self._install_worker.failed.connect(self._install_failed)
        self._install_worker.finished.connect(self._cleanup_install_thread)
        self._install_worker.failed.connect(self._cleanup_install_thread)
        self._install_thread.start()

    @staticmethod
    def _update_download_progress(progress: QProgressBar, received: int, total: int):
        """Atualiza a barra de download sem bloquear a thread da GUI."""
        if total > 0:
            progress.setRange(0, 100)
            progress.setValue(min(100, int(received * 100 / total)))
        else:
            progress.setRange(0, 0)

    def _install_finished(self, emulator: str, version: str, executable: str):
        """Registra a instalação concluída e atualiza a descoberta."""
        path = Path(executable)
        setattr(self.config, f"{emulator}_path", path)
        setattr(self.config, f"{emulator}_dir", path.parent)
        self.config.save()
        self._finish_card_progress(emulator)
        self.refresh_status()

    def _install_failed(self, message: str):
        """Apresenta uma falha de instalação somente como erro da operação."""
        for _name, labels in self.cards.items():
            if labels[3].isVisible() and labels[0].text().startswith("● Baixando"):
                self._finish_card_progress(_name)
                break
        QMessageBox.critical(self, "Falha na instalação", message)

    def _finish_card_progress(self, emulator: str):
        """Restaura o card após o término do download."""
        labels = self.cards.get(emulator)
        if labels:
            labels[3].hide()

    def _cleanup_install_thread(self, *_args):
        """Finaliza a thread de instalação após o sinal de conclusão/erro."""
        if self._install_thread is None:
            return
        self._install_thread.quit()
        self._install_thread.wait()
        self._install_worker = None
        self._install_thread.deleteLater()
        self._install_thread = None
        for name in self.EMULATOR_LABELS:
            self.cards[name][4].setEnabled(True)

    def open_directories(self):
        """Mantém compatibilidade com a navegação antiga da Home."""
        self.open_emulator_directories()

    def open_official_site(self, emulator: str):
        """Abre o repositório oficial do emulador selecionado."""
        url = self.EMULATOR_SITES.get(emulator)
        if url:
            webbrowser.open(url)
