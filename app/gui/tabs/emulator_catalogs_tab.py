"""GUI de operação e diagnóstico dos catálogos multi-emulador."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Slot
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget

from app.config.app_config import AppConfig
from app.core.services.emulator_catalog_build_service import CatalogBuildContext
from app.core.services.emulator_catalog_repository import EmulatorCatalogRepository
from app.gui.widgets.emulator_catalog_worker import EmulatorCatalogBatchWorker, EmulatorCatalogWorker

logger = logging.getLogger(__name__)


class EmulatorCatalogsTab(QWidget):
    """Permite gerar e inspecionar os catálogos dos quatro emuladores.

    Todos os cards usam a mesma semântica: ``Jogos suportados`` representa
    máquinas/jogos do catálogo, nunca a quantidade de arquivos ROM. A
    quantidade de ROMs permanece disponível no detalhe/log para diagnóstico.
    """

    EMULATORS = ("mame", "flycast", "supermodel", "fbneo")
    LABELS = {"mame": "MAME", "flycast": "Flycast", "supermodel": "Supermodel", "fbneo": "FBNeo"}
    DESCRIPTIONS = {
        "mame": "Catálogo completo produzido pelo MAME instalado.",
        "flycast": "Arcade suportado pelo Flycast: NAOMI, NAOMI 2, GD-ROM, Atomiswave e System SP. Dreamcast não entra neste catálogo.",
        "supermodel": "Jogos Sega Model 3 obtidos da base oficial Games.xml.",
        "fbneo": "Jogos Arcade que o FBNeo publica através de -listinfo; consoles não são considerados neste perfil.",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = getattr(parent, "config", None) or AppConfig()
        self.db = getattr(parent, "db", None)
        self._thread: QThread | None = None
        self._worker = None
        self._active_emulator: str | None = None
        self.cards: dict[str, tuple[QLabel, QLabel, QLabel, QLabel, QProgressBar, QPushButton]] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Monta a interface em grupos independentes para manutenção."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        title = QLabel("Catálogos dos Emuladores")
        title.setStyleSheet("font-size:22px;font-weight:bold;")
        layout.addWidget(title)
        description = QLabel(
            "As informações abaixo representam jogos/máquinas suportados. A quantidade de ROMs é um dado técnico separado e não define o tamanho do set."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color:#aaa;")
        layout.addWidget(description)

        frame = QFrame()
        frame.setObjectName("catalogCards")
        frame.setStyleSheet("QFrame#catalogCards{background:#151515;border:1px solid #383838;border-radius:8px;} QFrame#catalogCard{background:#202020;border:1px solid #414141;border-radius:7px;}")
        grid = QGridLayout(frame)
        for index, emulator in enumerate(self.EMULATORS):
            card, labels = self._create_card(emulator)
            grid.addWidget(card, index // 2, index % 2)
            self.cards[emulator] = labels
        layout.addWidget(frame)

        actions = QHBoxLayout()
        self.generate_all_button = QPushButton("⚙ Gerar todos os catálogos")
        self.generate_all_button.setToolTip("Gera os quatro catálogos em sequência. O Flycast utiliza o LISTXML do MAME como fonte.")
        self.generate_all_button.clicked.connect(self.generate_all)
        actions.addWidget(self.generate_all_button)
        refresh = QPushButton("↻ Atualizar estado")
        refresh.setToolTip("Relê os metadados dos catálogos publicados no SQLite.")
        refresh.clicked.connect(self.refresh)
        actions.addWidget(refresh)
        clear = QPushButton("Limpar log")
        clear.clicked.connect(self.clear_log)
        actions.addWidget(clear)
        actions.addStretch()
        layout.addLayout(actions)

        layout.addWidget(QLabel("Log da geração e publicação"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(3000)
        self.log.setStyleSheet("QPlainTextEdit{background:#0b0b0b;color:#d7d7d7;font-family:Consolas;font-size:10px;}")
        layout.addWidget(self.log, 1)
        self.footer = QLabel("Catálogo não publicado")
        self.footer.setStyleSheet("color:#888;font-size:10px;")
        layout.addWidget(self.footer)

    def _create_card(self, emulator: str):
        """Cria um card padronizado mostrando jogos suportados e ROMs separadamente."""
        card = QFrame()
        card.setObjectName("catalogCard")
        box = QVBoxLayout(card)
        name = QLabel(self.LABELS[emulator])
        name.setStyleSheet("font-size:15px;font-weight:bold;")
        box.addWidget(name)
        description = QLabel(self.DESCRIPTIONS[emulator])
        description.setWordWrap(True)
        description.setStyleSheet("color:#aaa;font-size:10px;")
        box.addWidget(description)
        status = QLabel("● Não publicado")
        box.addWidget(status)
        version = QLabel("Versão: —")
        box.addWidget(version)
        games = QLabel("Jogos suportados: —")
        box.addWidget(games)
        roms = QLabel("ROMs no catálogo: —")
        roms.setStyleSheet("color:#888;font-size:10px;")
        box.addWidget(roms)
        progress = QProgressBar()
        progress.setTextVisible(False)
        progress.setRange(0, 1)
        progress.setValue(0)
        progress.hide()
        box.addWidget(progress)
        button = QPushButton("Gerar catálogo")
        button.setToolTip("Gera somente o catálogo deste emulador e publica o resultado no SQLite.")
        button.clicked.connect(lambda _=False, key=emulator: self.generate_one(key))
        box.addWidget(button)
        return card, (status, version, games, roms, progress, button)

    def _context(self) -> CatalogBuildContext:
        """Monta o contexto usando somente instalações configuradas."""
        self.config.load()
        return CatalogBuildContext(
            mame_executable=self._path("mame_path"),
            mame_version=getattr(self.config, "mame_version", None),
            fbneo_executable=self._path("fbneo_path"),
            fbneo_version=getattr(self.config, "fbneo_version", None),
            supermodel_root=self._path("supermodel_dir"),
            supermodel_version=getattr(self.config, "supermodel_version", None),
            flycast_version=getattr(self.config, "flycast_version", None),
        )

    def _path(self, attr: str) -> Path | None:
        """Converte uma configuração de caminho em Path."""
        value = getattr(self.config, attr, None)
        return Path(value).expanduser() if value else None

    def refresh(self) -> None:
        """Atualiza os cards lendo o estado persistido no SQLite."""
        if self.db is None:
            self.footer.setText("Banco SQLite indisponível")
            return
        try:
            repository = EmulatorCatalogRepository(self.db)
            catalogs = {row["emulator"]: row for row in repository.list_catalogs()}
            for emulator in self.EMULATORS:
                status, version, games, roms, progress, button = self.cards[emulator]
                row = catalogs.get(emulator)
                if row is None:
                    status.setText("● Não publicado")
                    status.setStyleSheet("color:#999;font-weight:bold;")
                    version.setText("Versão: —")
                    games.setText("Jogos suportados: —")
                    roms.setText("ROMs no catálogo: —")
                    continue
                status.setText("● Publicado")
                status.setStyleSheet("color:#55d66b;font-weight:bold;")
                version.setText(f"Versão: {row['version'] or 'unknown'}")
                games.setText(f"Jogos suportados: {row['machine_count']:,}".replace(",", "."))
                roms.setText(f"ROMs no catálogo: {row['rom_count']:,}".replace(",", "."))
            self.footer.setText("Estado dos catálogos atualizado")
        except Exception as exc:
            logger.exception("Falha ao atualizar GUI de catálogos")
            self.footer.setText(f"Erro: {exc}")

    def generate_one(self, emulator: str) -> None:
        """Inicia a geração de um catálogo em background."""
        if self._thread is not None or self.db is None:
            return
        self._start_worker(EmulatorCatalogWorker, emulator)

    def generate_all(self) -> None:
        """Inicia a geração dos quatro catálogos em background."""
        if self._thread is not None or self.db is None:
            return
        self._start_worker(EmulatorCatalogBatchWorker, None)

    def _start_worker(self, worker_type, emulator: str | None) -> None:
        """Cria e conecta o worker responsável pela operação selecionada."""
        context = self._context()
        self._active_emulator = emulator
        self._thread = QThread(self)
        worker = worker_type(self.db, context) if emulator is None else worker_type(self.db, context, emulator)
        self._worker = worker
        worker.moveToThread(self._thread)
        worker.log_message.connect(self._append_log)
        worker.catalog_finished.connect(self._catalog_finished)
        worker.failed.connect(self._catalog_failed)
        worker.finished.connect(self._thread.quit)
        worker.finished.connect(worker.deleteLater)
        self._thread.finished.connect(self._worker_thread_finished)
        self._thread.finished.connect(self._thread.deleteLater)
        self._set_busy(True, emulator)
        self._thread.started.connect(worker.run)
        self._thread.start()

    @Slot(str)
    def _append_log(self, message: str) -> None:
        """Adiciona diagnóstico operacional ao console."""
        self.log.appendPlainText(str(message).rstrip())
        self.log.ensureCursorVisible()

    @Slot(str, int, int, str)
    def _catalog_finished(self, emulator: str, machines: int, roms: int, version: str) -> None:
        """Atualiza o card após publicação."""
        self._append_log(f"OK | {self.LABELS.get(emulator, emulator)} | jogos={machines} | roms={roms} | version={version}")
        self.refresh()

    @Slot(str, str)
    def _catalog_failed(self, emulator: str, message: str) -> None:
        """Exibe falha sem interromper a aplicação."""
        self._append_log(f"ERRO | {self.LABELS.get(emulator, emulator)} | {message}")
        labels = self.cards.get(emulator)
        if labels:
            labels[0].setText("● Erro")
            labels[0].setStyleSheet("color:#e05a5a;font-weight:bold;")

    @Slot()
    def _worker_thread_finished(self) -> None:
        """Libera referências e reativa controles."""
        self._thread = None
        self._worker = None
        active = self._active_emulator
        self._active_emulator = None
        self._set_busy(False, active)
        self.refresh()

    def _set_busy(self, busy: bool, active_emulator: str | None = None) -> None:
        """Ativa progresso somente no emulador em execução."""
        self.generate_all_button.setEnabled(not busy)
        for emulator, labels in self.cards.items():
            progress = labels[4]
            button = labels[5]
            is_active = busy and (active_emulator is None or emulator == active_emulator)
            progress.setVisible(is_active)
            button.setEnabled(not busy)
            if is_active:
                progress.setRange(0, 0)
            else:
                progress.setRange(0, 1)
                progress.setValue(0)

    def clear_log(self) -> None:
        """Limpa o console sem alterar os catálogos."""
        self.log.clear()

    def closeEvent(self, event) -> None:
        """Espera a geração em andamento antes de fechar."""
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(10000)
        event.accept()
