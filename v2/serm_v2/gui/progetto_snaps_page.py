"""Interface gráfica para gerenciamento dos recursos do projeto-SNAPS."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

LOGGER = logging.getLogger(__name__)
SNAPS_HOME = "https://www.progettosnaps.net/"
SNAPS_SNAPSHOTS = urljoin(SNAPS_HOME, "snapshots/")
SNAPS_DATS = urljoin(SNAPS_HOME, "dats/")


class _WorkerSignals(QObject):
    """Sinais emitidos por tarefas executadas fora da thread da interface."""

    finished = Signal(object)
    error = Signal(str)


class _FetchWorker(QRunnable):
    """Executa uma consulta HTTP simples sem bloquear a GUI."""

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url
        self.signals = _WorkerSignals()

    def run(self) -> None:
        """Baixa a página solicitada e devolve o conteúdo como texto."""
        try:
            request = Request(self.url, headers={"User-Agent": "SERM-V2/2.0"})
            with urlopen(request, timeout=15) as response:
                self.signals.finished.emit(response.read().decode("utf-8", errors="replace"))
        except Exception as exc:  # noqa: BLE001 - erro de rede deve chegar à GUI.
            self.signals.error.emit(str(exc))


class ProgettoSnapsPage(QWidget):
    """Painel para acompanhar e validar uma coleção local do progetto-SNAPS."""

    CATEGORIES = (
        ("Snap", "Snapshots principais", "0.288"),
        ("Titles", "Tela de títulos", "0.288"),
        ("ArtPreview", "Artwork Preview", "0.288"),
        ("Bosses", "Chefes", "0.288"),
        ("Ends", "Finais", "0.288"),
        ("GameOver", "Telas de Game Over", "0.288"),
        ("HowTo", "Instruções / How To", "0.288"),
        ("Logo", "Logotipos", "0.288"),
        ("Scores", "Pontuações", "0.288"),
        ("Select", "Telas de seleção", "0.288"),
        ("Versus", "Telas versus", "0.288"),
        ("Warning", "Avisos", "0.288"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """Monta a interface, separando configuração, resumo e categorias."""
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        title = QLabel("progetto-SNAPS")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Gerencie snapshots do MAME, valide sua coleção local e acompanhe a versão do pacote."
        )
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        location = QGroupBox("Coleção local")
        location_layout = QHBoxLayout(location)
        self.root_edit = QLineEdit()
        self.root_edit.setPlaceholderText("Pasta raiz que contém as categorias do projeto-SNAPS")
        browse = QPushButton("Selecionar…")
        browse.clicked.connect(self._choose_root)
        scan = QPushButton("Verificar coleção")
        scan.clicked.connect(self._scan_local)
        location_layout.addWidget(self.root_edit, 1)
        location_layout.addWidget(browse)
        location_layout.addWidget(scan)
        root.addWidget(location)

        summary = QFrame()
        summary.setObjectName("snapsSummary")
        summary_layout = QGridLayout(summary)
        self.version_label = QLabel("MAME: —")
        self.online_label = QLabel("Status: aguardando consulta")
        self.local_label = QLabel("Coleção: não verificada")
        refresh = QPushButton("Atualizar informações online")
        refresh.clicked.connect(self._refresh_online)
        open_site = QPushButton("Abrir projeto-SNAPS")
        open_site.clicked.connect(lambda: self._open_url(SNAPS_HOME))
        summary_layout.addWidget(self.version_label, 0, 0)
        summary_layout.addWidget(self.online_label, 0, 1)
        summary_layout.addWidget(self.local_label, 1, 0)
        summary_layout.addWidget(refresh, 1, 1)
        summary_layout.addWidget(open_site, 1, 2)
        root.addWidget(summary)

        self.table = QTableWidget(len(self.CATEGORIES), 5)
        self.table.setHorizontalHeaderLabels(("Categoria", "Descrição", "Versão", "Local", "Ação"))
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(360)
        for row, (name, description, version) in enumerate(self.CATEGORIES):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(description))
            self.table.setItem(row, 2, QTableWidgetItem(version))
            self.table.setItem(row, 3, QTableWidgetItem("—"))
            button = QPushButton("Abrir página")
            button.clicked.connect(lambda _checked=False, category=name: self._open_category(category))
            self.table.setCellWidget(row, 4, button)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        root.addWidget(self.progress)

        dat_button = QPushButton("Abrir página de DATs do projeto-SNAPS")
        dat_button.clicked.connect(lambda: self._open_url(SNAPS_DATS))
        root.addWidget(dat_button)

    def refresh(self) -> None:
        """Atualiza o estado da coleção sem executar uma operação de rede pesada."""
        self._scan_local()

    def _choose_root(self) -> None:
        """Seleciona a pasta raiz onde os recursos SNAPS estão armazenados."""
        selected = QFileDialog.getExistingDirectory(self, "Selecionar coleção do projeto-SNAPS")
        if selected:
            self.root_edit.setText(selected)
            self._scan_local()

    def _scan_local(self) -> None:
        """Verifica quais categorias do projeto-SNAPS existem na pasta configurada."""
        raw_root = self.root_edit.text().strip()
        if not raw_root:
            self.local_label.setText("Coleção: não configurada")
            for row in range(self.table.rowCount()):
                self.table.item(row, 3).setText("—")
            return

        root = Path(os.path.expandvars(os.path.expanduser(raw_root)))
        if not root.is_dir():
            self.local_label.setText("Coleção: pasta inválida")
            return

        found = 0
        for row, (category, _description, _version) in enumerate(self.CATEGORIES):
            category_dir = self._find_category_dir(root, category)
            status = "Encontrado" if category_dir else "Ausente"
            if category_dir:
                found += 1
            self.table.item(row, 3).setText(status)
        self.local_label.setText(f"Coleção: {found}/{len(self.CATEGORIES)} categorias encontradas")

    @staticmethod
    def _find_category_dir(root: Path, category: str) -> Path | None:
        """Localiza uma pasta de categoria tolerando diferenças de maiúsculas/minúsculas."""
        expected = category.casefold()
        try:
            return next((path for path in root.iterdir() if path.is_dir() and path.name.casefold() == expected), None)
        except OSError as exc:
            LOGGER.warning("Não foi possível ler %s: %s", root, exc)
            return None

    def _refresh_online(self) -> None:
        """Consulta a página oficial sem bloquear a interface."""
        self.progress.show()
        self.online_label.setText("Status: consultando projeto-SNAPS…")
        worker = _FetchWorker(SNAPS_HOME)
        worker.signals.finished.connect(self._online_finished)
        worker.signals.error.connect(self._online_error)
        self._pool.start(worker)

    def _online_finished(self, html: str) -> None:
        """Interpreta a resposta oficial e atualiza o status da interface."""
        self.progress.hide()
        if "0.289" in html:
            self.version_label.setText("MAME: 0.289")
        elif "0.288" in html:
            self.version_label.setText("MAME: 0.288")
        else:
            self.version_label.setText("MAME: versão não identificada")
        self.online_label.setText("Status: projeto-SNAPS acessível")

    def _online_error(self, message: str) -> None:
        """Apresenta uma falha de rede sem interromper a aplicação."""
        self.progress.hide()
        self.online_label.setText("Status: falha na consulta online")
        LOGGER.warning("Falha ao consultar projeto-SNAPS: %s", message)

    def _open_category(self, category: str) -> None:
        """Abre a página oficial correspondente à categoria de snapshots."""
        self._open_url(urljoin(SNAPS_SNAPSHOTS, ""))

    @staticmethod
    def _open_url(url: str) -> None:
        """Abre um endereço oficial no navegador padrão do sistema."""
        import webbrowser

        webbrowser.open(url)

    def closeEvent(self, event) -> None:
        """Libera o widget normalmente quando a janela é encerrada."""
        self._pool.clear()
        super().closeEvent(event)
