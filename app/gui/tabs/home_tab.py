"""Home do MAME Set Builder."""
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
    QPlainTextEdit,
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
    """Apresenta o estado dos emuladores e controla instalações individuais ou em lote."""

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
        self._update_queue: list[str] = []
        self._bulk_update = False
        self._bulk_successes: list[str] = []
        self._bulk_failures: list[str] = []
        self.setup_ui()
        self.refresh_status()

    def setup_ui(self):
        """Monta a interface da Home, incluindo o console de instalação."""
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
            "QFrame#emulatorStatusFrame{background:#151515;border:1px solid #3d3d3d;border-radius:8px;padding:10px;}"
            "QFrame#emulatorCard{background:#202020;border:1px solid #414141;border-radius:7px;}"
            "QLabel#emulatorName{font-size:15px;font-weight:bold;} QLabel#emulatorDetail{color:#b8b8b8;}"
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
        update_all = QPushButton("🔄 Atualizar todos os emuladores")
        update_all.setToolTip("Baixa e instala a versão oficial mais recente de MAME, Flycast, Supermodel e FBNeo, em sequência.")
        update_all.clicked.connect(self.update_all_emulators)
        actions.addWidget(update_all)
        self.update_all_button = update_all

        directories = QPushButton("📁 Configurar diretórios")
        directories.clicked.connect(self.open_emulator_directories)
        actions.addWidget(directories)

        clear_log = QPushButton("🧹 Limpar log")
        clear_log.clicked.connect(self.clear_install_log)
        actions.addWidget(clear_log)
        actions.addStretch()
        main_layout.addLayout(actions)

        self.install_log = QPlainTextEdit()
        self.install_log.setReadOnly(True)
        self.install_log.setMaximumBlockCount(3000)
        self.install_log.setPlaceholderText("O diagnóstico detalhado da instalação aparecerá aqui…")
        self.install_log.setStyleSheet("QPlainTextEdit{background:#0b0b0b;color:#d7d7d7;font-family:Consolas;font-size:10px;}")
        main_layout.addWidget(QLabel("Log detalhado da instalação"))
        main_layout.addWidget(self.install_log, 1)

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
        site.clicked.connect(lambda _=False, key=name: self.open_official_site(key))
        row.addWidget(site)
        layout.addLayout(row)
        return card, (status, version, path, progress, install)

    def refresh_status(self):
        """Atualiza a descoberta sem iniciar emuladores, instaladores ou 7-Zip."""
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
        """Renderiza o estado normalizado."""
        directory = getattr(self.config, f"{name}_dir", None)
        detail = str(directory or status.root or status.executable or "—")
        if status.status == "executable_missing":
            detail += " | configuração encontrada, executável não localizado"
        self._set_card(name, status.status, status.version, detail)

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
            "executable_missing": ("● Configuração encontrada; executável ausente", "#e5c454"),
            "error": ("● Erro na descoberta", "#e05a5a"),
            "not_found": ("● Não configurado", "#a8a8a8"),
        }
        text, color = texts.get(status, (f"● {status}", "#a8a8a8"))
        status_label.setText(text)
        status_label.setStyleSheet(f"color:{color};font-weight:bold;")
        version_label.setText(f"Versão: {version or '—'}")
        path_label.setText(f"Instalação: {detail or path or '—'}")
        button.setEnabled(self._install_thread is None and not self._bulk_update)

    def open_emulator_directories(self):
        """Abre o diálogo de configuração dos diretórios."""
        dialog = EmulatorDirectoriesDialog(self.config, self)
        if dialog.exec():
            self.config.load()
            self.refresh_status()

    def update_all_emulators(self):
        """Atualiza os quatro emuladores sequencialmente, mantendo a GUI responsiva."""
        if self._install_thread is not None or self._bulk_update:
            return
        self._bulk_update = True
        self._bulk_successes.clear()
        self._bulk_failures.clear()
        self._update_queue = list(self.EMULATOR_LABELS.keys())
        self.install_log.appendPlainText("=" * 100)
        self.install_log.appendPlainText("ATUALIZAÇÃO COMPLETA | MAME + Flycast + Supermodel + FBNeo")
        self.install_log.appendPlainText("Os quatro emuladores serão processados em sequência.")
        self.update_all_button.setEnabled(False)
        self._set_install_buttons_enabled(False)
        self._start_next_bulk_update()

    def _start_next_bulk_update(self):
        """Inicia o próximo emulador da fila de atualização."""
        if not self._update_queue:
            self._finish_bulk_update()
            return
        emulator = self._update_queue.pop(0)
        self.install_log.appendPlainText(f"ATUALIZAÇÃO EM LOTE | {self.EMULATOR_LABELS[emulator]} | restante={len(self._update_queue)}")
        self.install_emulator(emulator)

    def install_emulator(self, emulator: str):
        """Inicia a instalação em background sem bloquear ou encerrar a GUI."""
        if emulator not in self.EMULATOR_LABELS or self._install_thread is not None:
            return
        destination = getattr(self.config, f"{emulator}_dir", None)
        if not destination:
            if self._bulk_update:
                self._bulk_failures.append(emulator)
                self._on_install_log(f"ERRO | {self.EMULATOR_LABELS[emulator]} não possui diretório configurado.")
                self._start_next_bulk_update()
                return
            self.open_emulator_directories()
            destination = getattr(self.config, f"{emulator}_dir", None)
            if not destination:
                return
        destination = Path(destination)
        self.install_log.appendPlainText("=" * 100)
        self.install_log.appendPlainText(f"INICIANDO INSTALAÇÃO | {self.EMULATOR_LABELS[emulator]} | destino={destination}")
        self.install_log.appendPlainText("Aguardando início do worker…")
        self.install_log.ensureCursorVisible()
        progress = self.cards[emulator][3]
        progress.show()
        progress.setRange(0, 0)
        self.cards[emulator][0].setText("● Iniciando…")
        self.cards[emulator][0].setStyleSheet("color:#e5c454;font-weight:bold;")
        self._install_emulator = emulator
        self._install_thread = QThread(self)
        self._install_worker = EmulatorInstallWorker(emulator, destination)
        self._install_worker.moveToThread(self._install_thread)
        self._install_worker.progress.connect(self._on_download_progress)
        self._install_worker.status.connect(self._on_install_status)
        self._install_worker.log_message.connect(self._on_install_log)
        self._install_worker.finished.connect(self._install_finished)
        self._install_worker.failed.connect(self._install_failed)
        self._install_worker.finished.connect(self._install_thread.quit)
        self._install_worker.failed.connect(self._install_thread.quit)
        self._install_worker.finished.connect(self._install_worker.deleteLater)
        self._install_worker.failed.connect(self._install_worker.deleteLater)
        self._install_thread.finished.connect(self._install_thread_finished)
        self._install_thread.finished.connect(self._install_thread.deleteLater)
        self._set_install_buttons_enabled(False)
        self._install_thread.started.connect(self._install_worker.run)
        self._install_thread.start()

    @Slot(int, int)
    def _on_download_progress(self, received: int, total: int):
        """Atualiza a barra na thread principal."""
        emulator = self._install_emulator
        if not emulator or emulator not in self.cards:
            return
        progress = self.cards[emulator][3]
        if total > 0:
            progress.setRange(0, 100)
            progress.setValue(min(100, int(received * 100 / total)))
        else:
            progress.setRange(0, 0)

    @Slot(str)
    def _on_install_status(self, message: str):
        """Atualiza o estágio atual no card."""
        if self._install_emulator and self._install_emulator in self.cards:
            self.cards[self._install_emulator][0].setText(f"● {message}")

    @Slot(str)
    def _on_install_log(self, message: str):
        """Adiciona uma linha operacional ao console visual."""
        text = str(message).rstrip()
        self.install_log.appendPlainText(text)
        self.install_log.ensureCursorVisible()

    @Slot(str, str, str)
    def _install_finished(self, emulator: str, version: str, executable: str):
        """Registra conclusão, atualiza configuração e mantém a janela aberta."""
        self._on_install_log(f"SUCESSO | {self.EMULATOR_LABELS.get(emulator, emulator)} | versão={version} | executável={executable}")
        path = Path(executable)
        setattr(self.config, f"{emulator}_path", path)
        setattr(self.config, f"{emulator}_dir", path.parent)
        self.config.save()
        self._finish_card_progress(emulator)
        if self._bulk_update:
            self._bulk_successes.append(emulator)
        self.refresh_status()
        if not self._bulk_update:
            QMessageBox.information(self, "Instalação concluída", f"{self.EMULATOR_LABELS.get(emulator, emulator)} foi instalado/atualizado com sucesso.\n\nVersão: {version}\nExecutável: {executable}")

    @Slot(str)
    def _install_failed(self, message: str):
        """Mostra o diagnóstico da falha sem encerrar a aplicação."""
        self._on_install_log("=" * 100)
        self._on_install_log("FALHA NA INSTALAÇÃO")
        self._on_install_log(message)
        if self._install_emulator:
            self._finish_card_progress(self._install_emulator)
            if self._bulk_update:
                self._bulk_failures.append(self._install_emulator)
        if not self._bulk_update:
            QMessageBox.critical(self, "Falha na instalação", message)

    @Slot()
    def _install_thread_finished(self):
        """Libera referências da thread concluída e continua a atualização em lote."""
        emulator = self._install_emulator
        self._on_install_log(f"THREAD FINALIZADA | emulator={emulator}")
        if emulator:
            self._finish_card_progress(emulator)
        self._install_worker = None
        self._install_thread = None
        self._install_emulator = None
        if self._bulk_update:
            self._start_next_bulk_update()
        else:
            self._set_install_buttons_enabled(True)

    def _finish_bulk_update(self):
        """Finaliza a atualização em lote e apresenta um resumo único."""
        self._bulk_update = False
        self.update_all_button.setEnabled(True)
        self._set_install_buttons_enabled(True)
        successes = ", ".join(self.EMULATOR_LABELS[name] for name in self._bulk_successes) or "nenhum"
        failures = ", ".join(self.EMULATOR_LABELS[name] for name in self._bulk_failures) or "nenhum"
        self._on_install_log("=" * 100)
        self._on_install_log(f"ATUALIZAÇÃO COMPLETA FINALIZADA | sucesso={successes} | falha={failures}")
        QMessageBox.information(self, "Atualização dos emuladores", f"Atualização concluída.\n\nSucesso: {successes}\nFalhas: {failures}")

    def _set_install_buttons_enabled(self, enabled: bool):
        """Habilita ou desabilita os botões de instalação."""
        for labels in self.cards.values():
            labels[4].setEnabled(enabled)

    def _finish_card_progress(self, emulator: str):
        """Oculta a barra de progresso."""
        labels = self.cards.get(emulator)
        if labels:
            labels[3].hide()

    def clear_install_log(self):
        """Limpa o console visual de instalação."""
        self.install_log.clear()

    def open_directories(self):
        """Mantém compatibilidade com navegação antiga."""
        self.open_emulator_directories()

    def open_official_site(self, emulator: str):
        """Abre o repositório oficial do emulador."""
        url = self.EMULATOR_SITES.get(emulator)
        if url:
            webbrowser.open(url)
