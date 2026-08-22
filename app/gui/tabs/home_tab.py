"""Home do MAME Set Builder.

A Home apresenta o estado dos emuladores e concentra o fluxo de instalação.
Downloads e instalações executam em QThread; toda atualização de widgets ocorre
exclusivamente na thread principal da GUI.
"""
from __future__ import annotations

import logging
import webbrowser
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Slot
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

logger = logging.getLogger(__name__)


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
        self.cards = {}
        self._install_thread: QThread | None = None
        self._install_worker: EmulatorInstallWorker | None = None
        self._install_emulator: str | None = None
        self.setup_ui()
        self.refresh_status()

    def setup_ui(self):
        """Monta a interface da Home."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title = QLabel("MAME Set Builder")
        title.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(28)
        font.setBold(True)
        title.setFont(font)
        main_layout.addWidget(title)

        subtitle = QLabel("Gerenciamento, filtragem e construção de conjuntos de ROMs para arcades")
        subtitle.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(subtitle)

        status_frame = QFrame()
        status_frame.setObjectName("emulatorStatusFrame")
        status_frame.setStyleSheet(
            "QFrame#emulatorStatusFrame{background:#151515;border:1px solid #3d3d3d;"
            "border-radius:8px;padding:10px;} "
            "QFrame#emulatorCard{background:#202020;border:1px solid #414141;"
            "border-radius:7px;} "
            "QLabel#emulatorName{font-size:15px;font-weight:bold;} "
            "QLabel#emulatorDetail{color:#b8b8b8;} "
            "QProgressBar{min-height:8px;max-height:8px;}"
        )
        grid = QGridLayout(status_frame)

        for index, name in enumerate(self.EMULATOR_LABELS):
            card, labels = self._create_emulator_card(name)
            row, column = divmod(index, 2)
            grid.addWidget(card, row, column)
            self.cards[name] = labels

        main_layout.addWidget(status_frame)

        actions = QHBoxLayout()
        refresh = QPushButton("🔄 Atualizar emuladores")
        refresh.setToolTip("Redescobre os emuladores configurados.")
        refresh.clicked.connect(self.refresh_status)
        actions.addWidget(refresh)

        directories = QPushButton("📁 Configurar diretórios")
        directories.setToolTip("Define as pastas padrão de instalação.")
        directories.clicked.connect(self.open_emulator_directories)
        actions.addWidget(directories)
        actions.addStretch()
        main_layout.addLayout(actions)
        main_layout.addStretch()

        footer = QLabel("O software não distribui ROMs. Trabalha apenas com arquivos que o usuário já possui.")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color:#888;font-size:10px;")
        main_layout.addWidget(footer)

    def _create_emulator_card(self, name: str):
        """Cria o card visual e seus controles."""
        card = QFrame()
        card.setObjectName("emulatorCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)

        name_label = QLabel(self.EMULATOR_LABELS[name])
        name_label.setObjectName("emulatorName")
        layout.addWidget(name_label)

        status = QLabel("⏳ Verificando…")
        status.setObjectName("emulatorDetail")
        layout.addWidget(status)

        version = QLabel("Versão: —")
        version.setObjectName("emulatorDetail")
        layout.addWidget(version)

        path = QLabel("Instalação: —")
        path.setObjectName("emulatorDetail")
        path.setWordWrap(True)
        layout.addWidget(path)

        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setTextVisible(False)
        progress.hide()
        layout.addWidget(progress)

        row = QHBoxLayout()
        install = QPushButton("⬇ Baixar / atualizar")
        install.setToolTip("Baixa o pacote oficial Windows x64 e instala diretamente no diretório configurado.")
        install.clicked.connect(lambda _=False, key=name: self.install_emulator(key))
        row.addWidget(install)

        site = QPushButton("🌐 Repositório")
        site.setToolTip("Abre o repositório oficial no GitHub.")
        site.clicked.connect(lambda _=False, key=name: self.open_official_site(key))
        row.addWidget(site)
        layout.addLayout(row)

        return card, (status, version, path, progress, install)

    def refresh_status(self):
        """Atualiza a descoberta dos emuladores sem interromper a aplicação."""
        logger.info("Home: iniciando descoberta dos emuladores")
        try:
            self.config.load()
            self.statuses = self.status_service.refresh()
            for name in self.EMULATOR_LABELS:
                self._set_card_from_status(name, self.statuses[name])
            logger.info("Home: descoberta concluída")
        except Exception as exc:
            logger.exception("Home: falha na descoberta dos emuladores")
            for name in self.EMULATOR_LABELS:
                self._set_card(name, "error", None, None, f"{type(exc).__name__}: {exc}")

    def _set_card_from_status(self, name: str, status: EmulatorStatus):
        """Renderiza o estado normalizado do serviço de descoberta."""
        directory = getattr(self.config, f"{name}_dir", None)
        self._set_card(
            name,
            status.status,
            status.version,
            str(directory or status.root or status.executable or "—"),
        )

    def _set_card(self, name: str, status: str, version: str | None, path: str | None, detail: str | None = None):
        """Aplica textos e estado visual ao card."""
        labels = self.cards.get(name)
        if not labels:
            return

        status_label, version_label, path_label, progress, button = labels
        texts = {
            "ready": ("● Pronto", "#55d66b"),
            "ready_generated": ("● Pronto (configuração gerada)", "#55d66b"),
            "configuration_missing": ("● Configuração ausente", "#e5c454"),
            "configuration_corrupt": ("● Configuração inválida", "#e59b54"),
            "error": ("● Erro na descoberta", "#e05a5a"),
            "not_found": ("● Não configurado", "#a8a8a8"),
        }
        text, color = texts.get(status, (f"● {status}", "#a8a8a8"))
        status_label.setText(text)
        status_label.setStyleSheet(f"color:{color};font-weight:bold;")
        version_label.setText(f"Versão: {version or '—'}")
        path_label.setText(f"Instalação: {detail or path or '—'}")
        button.setEnabled(self._install_thread is None)

    def open_emulator_directories(self):
        """Abre o diálogo de configuração dos diretórios."""
        dialog = EmulatorDirectoriesDialog(self.config, self)
        if dialog.exec():
            self.config.load()
            self.refresh_status()

    def install_emulator(self, emulator: str):
        """Inicia a instalação em background sem bloquear ou encerrar a GUI."""
        if emulator not in self.EMULATOR_LABELS:
            logger.error("Home: emulador inválido | emulator=%s", emulator)
            return

        if self._install_thread is not None:
            logger.warning("Home: instalação recusada; outra instalação está em andamento")
            return

        destination = getattr(self.config, f"{emulator}_dir", None)
        if not destination:
            logger.info("Home: diretório ausente; abrindo configuração | emulator=%s", emulator)
            self.open_emulator_directories()
            destination = getattr(self.config, f"{emulator}_dir", None)
            if not destination:
                return

        destination = Path(destination)
        logger.info("Home: iniciando download | emulator=%s | destination=%s", emulator, destination)

        progress = self.cards[emulator][3]
        progress.show()
        progress.setRange(0, 0)
        self.cards[emulator][0].setText("● Baixando / instalando…")
        self.cards[emulator][0].setStyleSheet("color:#e5c454;font-weight:bold;")

        self._install_emulator = emulator
        self._install_thread = QThread(self)
        self._install_worker = EmulatorInstallWorker(emulator, destination)
        self._install_worker.moveToThread(self._install_thread)

        # IMPORTANTE: não conectar progress a lambda que manipula widgets.
        # O slot QObject abaixo é executado na thread da HomeTab (GUI).
        self._install_worker.progress.connect(self._on_download_progress)
        self._install_worker.status.connect(self._on_install_status)
        self._install_worker.finished.connect(self._install_finished)
        self._install_worker.failed.connect(self._install_failed)

        self._install_worker.finished.connect(self._install_thread.quit)
        self._install_worker.failed.connect(self._install_thread.quit)
        self._install_worker.finished.connect(self._install_worker.deleteLater)
        self._install_worker.failed.connect(self._install_worker.deleteLater)
        self._install_thread.finished.connect(self._install_thread_finished)
        self._install_thread.finished.connect(self._install_thread.deleteLater)

        self._set_install_buttons_enabled(False)
        self._install_thread.start()

    @Slot(int, int)
    def _on_download_progress(self, received: int, total: int):
        """Atualiza a barra exclusivamente na thread principal da GUI."""
        emulator = self._install_emulator
        if not emulator:
            return
        labels = self.cards.get(emulator)
        if not labels:
            return
        self._update_download_progress(labels[3], received, total)

    @Slot(str)
    def _on_install_status(self, message: str):
        """Exibe no card o estágio atual da instalação."""
        emulator = self._install_emulator
        if not emulator:
            return
        labels = self.cards.get(emulator)
        if labels:
            labels[0].setText(f"● {message}")

    @staticmethod
    def _update_download_progress(progress: QProgressBar, received: int, total: int):
        """Atualiza uma barra que já pertence à thread da GUI."""
        if total > 0:
            progress.setRange(0, 100)
            progress.setValue(min(100, int(received * 100 / total)))
        else:
            progress.setRange(0, 0)

    @Slot(str, str, str)
    def _install_finished(self, emulator: str, version: str, executable: str):
        """Registra instalação concluída e mantém a janela principal aberta."""
        logger.info(
            "Home: download concluído | emulator=%s | version=%s | executable=%s",
            emulator,
            version,
            executable,
        )

        path = Path(executable)
        setattr(self.config, f"{emulator}_path", path)
        setattr(self.config, f"{emulator}_dir", path.parent)
        self.config.save()
        self._finish_card_progress(emulator)
        self.refresh_status()

        QMessageBox.information(
            self,
            "Instalação concluída",
            f"{self.EMULATOR_LABELS.get(emulator, emulator)} foi instalado/atualizado com sucesso.\n\n"
            f"Versão: {version}\n"
            f"Executável: {executable}",
        )

    @Slot(str)
    def _install_failed(self, message: str):
        """Registra a falha sem encerrar a aplicação."""
        emulator = self._install_emulator
        logger.error("Home: download falhou | emulator=%s\n%s", emulator, message)
        if emulator:
            self._finish_card_progress(emulator)
        QMessageBox.critical(self, "Falha na instalação", message)

    @Slot()
    def _install_thread_finished(self):
        """Libera a thread concluída sem fechar a aplicação."""
        emulator = self._install_emulator
        logger.info("Home: thread de instalação finalizada | emulator=%s", emulator)

        if emulator:
            self._finish_card_progress(emulator)

        self._install_worker = None
        self._install_thread = None
        self._install_emulator = None
        self._set_install_buttons_enabled(True)

        # Deliberadamente não há QApplication.quit(), close(), sys.exit() ou wait().
        # A janela principal permanece aberta após a instalação.

    def _set_install_buttons_enabled(self, enabled: bool):
        """Habilita ou desabilita os botões de instalação."""
        for labels in self.cards.values():
            labels[4].setEnabled(enabled)

    def _finish_card_progress(self, emulator: str):
        """Oculta a barra de progresso do card."""
        labels = self.cards.get(emulator)
        if labels:
            labels[3].hide()

    def open_directories(self):
        """Mantém compatibilidade com a navegação antiga."""
        self.open_emulator_directories()

    def open_official_site(self, emulator: str):
        """Abre o repositório oficial do emulador."""
        url = self.EMULATOR_SITES.get(emulator)
        if url:
            webbrowser.open(url)
