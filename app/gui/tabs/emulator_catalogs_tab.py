"""GUI de teste e operação dos catálogos multi-emulador."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Slot
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config.app_config import AppConfig
from app.core.services.emulator_catalog_build_service import CatalogBuildContext
from app.core.services.emulator_catalog_repository import EmulatorCatalogRepository
from app.gui.widgets.emulator_catalog_worker import EmulatorCatalogBatchWorker, EmulatorCatalogWorker

logger = logging.getLogger(__name__)


class EmulatorCatalogsTab(QWidget):
    """Permite gerar, validar e inspecionar os catálogos dos quatro emuladores."""

    EMULATORS = ("mame", "flycast", "supermodel", "fbneo")
    LABELS = {
        "mame": "MAME",
        "flycast": "Flycast",
        "supermodel": "Supermodel",
        "fbneo": "FBNeo",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.config = getattr(parent, "config", None) or AppConfig()
        self.db = getattr(parent, "db", None)
        self._thread: QThread | None = None
        self._worker = None
        self.cards: dict[str, tuple[QLabel, QLabel, QLabel, QProgressBar, QPushButton]] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Monta a tela em grupos independentes para facilitar manutenção."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Catálogos dos Emuladores")
        title.setStyleSheet("font-size:22px;font-weight:bold;")
        layout.addWidget(title)
        description = QLabel(
            "Gera as bases de jogos a partir das fontes oficiais dos emuladores. "
            "A publicação no SQLite é atômica e não altera o dataset MAME legado."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color:#aaa;")
        layout.addWidget(description)

        # Grupo: estado dos catálogos.
        frame = QFrame()
        frame.setObjectName("catalogCards")
        frame.setStyleSheet(
            "QFrame#catalogCards{background:#151515;border:1px solid #383838;border-radius:8px;}"
            "QFrame#catalogCard{background:#202020;border:1px solid #414141;border-radius:7px;}"
        )
        grid = QGridLayout(frame)
        for index, emulator in enumerate(self.EMULATORS):
            card, labels = self._create_card(emulator)
            grid.addWidget(card, index // 2, index % 2)
            self.cards[emulator] = labels
        layout.addWidget(frame)

        # Grupo: operações.
        actions = QHBoxLayout()
        self.generate_all_button = QPushButton("⚙ Gerar todos os catálogos")
        self.generate_all_button.setToolTip(
            "Executa a geração de MAME, FBNeo, Supermodel e Flycast em sequência. "
            "O Flycast usa o LISTXML MAME como fonte e exclui Dreamcast."
        )
        self.generate_all_button.clicked.connect(self.generate_all)
        actions.addWidget(self.generate_all_button)

        refresh = QPushButton("↻ Atualizar estado")
        refresh.setToolTip("Relê os metadados dos catálogos já publicados no banco.")
        refresh.clicked.connect(self.refresh)
        actions.addWidget(refresh)

        clear = QPushButton("Limpar log")
        clear.clicked.connect(self.clear_log)
        actions.addWidget(clear)
        actions.addStretch()
        layout.addLayout(actions)

        # Grupo: diagnóstico operacional.
        layout.addWidget(QLabel("Log da geração e publicação"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(3000)
        self.log.setStyleSheet(
            "QPlainTextEdit{background:#0b0b0b;color:#d7d7d7;font-family:Consolas;font-size:10px;}"
        )
        layout.addWidget(self.log, 1)

        self.footer = QLabel("Catálogo não publicado")
        self.footer.setStyleSheet("color:#888;font-size:10px;")
        layout.addWidget(self.footer)

    def _create_card(self, emulator: str):
        """Cria o card independente de um emulador."""
        card = QFrame()
        card.setObjectName("catalogCard")
        box = QVBoxLayout(card)
        name = QLabel(self.LABELS[emulator])
        name.setStyleSheet("font-size:15px;font-weight:bold;")
        box.addWidget(name)
        status = QLabel("● Não publicado")
        box.addWidget(status)
        version = QLabel("Versão: —")
        box.addWidget(version)
        counts = QLabel("Máquinas: — | ROMs: —")
        box.addWidget(counts)
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
        return card, (status, version, counts, progress, button)

    def _context(self) -> CatalogBuildContext:
        """Monta o contexto usando somente instalações já detectadas/configuradas."""
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
        """Converte uma configuração de caminho em Path somente quando existente."""
        value = getattr(self.config, attr, None)
        return Path(value).expanduser() if value else None

    def refresh(self) -> None:
        """Atualiza os cards lendo apenas o estado persistido do SQLite."""
        if self.db is None:
            self.footer.setText("Banco SQLite indisponível")
            return
        try:
            repository = EmulatorCatalogRepository(self.db)
            catalogs = {row["emulator"]: row for row in repository.list_catalogs()}
            for emulator in self.EMULATORS:
                labels = self.cards[emulator]
                row = catalogs.get(emulator)
                if row is None:
                    labels[0].setText("● Não publicado")
                    labels[0].setStyleSheet("color:#999;font-weight:bold;")
                    labels[1].setText("Versão: —")
                    labels[2].setText("Máquinas: — | ROMs: —")
                    continue
                labels[0].setText("● Publicado")
                labels[0].setStyleSheet("color:#55d66b;font-weight:bold;")
                labels[1].setText(f"Versão: {row['version'] or 'unknown'}")
                labels[2].setText(
                    f"Máquinas: {row['machine_count']} | fonte: {row['source']}"
                )
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
        """Cria e conecta o worker Qt responsável pela operação selecionada."""
        context = self._context()
        self._thread = QThread(self)
        if emulator is None:
            worker = worker_type(self.db, context)
        else:
            worker = worker_type(self.db, context, emulator)
        self._worker = worker
        worker.moveToThread(self._thread)
        worker.log_message.connect(self._append_log)
        worker.catalog_finished.connect(self._catalog_finished)
        worker.failed.connect(self._catalog_failed)
        worker.finished.connect(self._thread.quit)
        worker.finished.connect(worker.deleteLater)
        self._thread.finished.connect(self._worker_thread_finished)
        self._thread.finished.connect(self._thread.deleteLater)
        self._set_busy(True)
        self._thread.started.connect(worker.run)
        self._thread.start()

    @Slot(str)
    def _append_log(self, message: str) -> None:
        """Adiciona diagnóstico operacional ao console da aba."""
        self.log.appendPlainText(str(message).rstrip())
        self.log.ensureCursorVisible()

    @Slot(str, int, int, str)
    def _catalog_finished(self, emulator: str, machines: int, roms: int, version: str) -> None:
        """Atualiza o card após publicação bem-sucedida."""
        self._append_log(
            f"OK | {self.LABELS.get(emulator, emulator)} | machines={machines} | roms={roms} | version={version}"
        )
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
        """Libera referências e reativa os controles após a thread."""
        self._thread = None
        self._worker = None
        self._set_busy(False)
        self.refresh()

    def _set_busy(self, busy: bool) -> None:
        """Padroniza o estado dos controles durante uma geração."""
        self.generate_all_button.setEnabled(not busy)
        for labels in self.cards.values():
            labels[3].setVisible(busy)
            labels[4].setEnabled(not busy)
            if busy:
                labels[3].setRange(0, 0)
            else:
                labels[3].setRange(0, 1)
                labels[3].setValue(0)

    def clear_log(self) -> None:
        """Limpa o console operacional sem alterar os catálogos."""
        self.log.clear()

    def closeEvent(self, event) -> None:
        """Espera uma geração em andamento antes de fechar a aba/janela."""
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(10000)
        event.accept()
