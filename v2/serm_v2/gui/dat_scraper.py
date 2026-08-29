"""Scraper unificado de DATs do SERM V2.

No-Intro e Redump usam os backends existentes e validados do projeto. As
sessões históricas WHLOADER, ExoDOS, C64 e MAME ficam explicitamente isoladas
até que seus backends originais sejam recuperados, evitando implementar uma
fonte fictícia.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QCheckBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ..integrations.launchbox import LaunchBoxIntegration
from ..integrations.launchbox_provider import LaunchBoxProvider
from ..sources.acquisition.no_intro_archive import NoIntroArchiveEntry, NoIntroArchiveProvider
from ..sources.acquisition.redump import RedumpEntry, RedumpProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _Row:
    """Representa um sistema exibido e seu objeto de aquisição."""
    name: str
    entry: object
    state: str


class _BatchWorker(QThread):
    """Executa downloads em lote fora da thread da interface."""
    progress = Signal(int, int, str)
    message = Signal(str)
    done = Signal(int, int)
    error = Signal(str)

    def __init__(self, operation, entries: list[_Row], parent=None) -> None:
        super().__init__(parent)
        self.operation = operation
        self.entries = entries

    def run(self) -> None:
        """Processa os sistemas selecionados e publica progresso incremental."""
        ok = 0
        failed = 0
        try:
            total = len(self.entries)
            for index, row in enumerate(self.entries, 1):
                self.progress.emit(index - 1, total, row.name)
                try:
                    self.operation(row.entry)
                    ok += 1
                    self.message.emit(f"OK | {row.name}")
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    self.message.emit(f"ERRO | {row.name} | {type(exc).__name__}: {exc}")
            self.progress.emit(total, total, "concluído")
            self.done.emit(ok, failed)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(f"{type(exc).__name__}: {exc}")


class DatSourceTab(QWidget):
    """Aba genérica com a mesma operação de seleção usada no gerenciamento de cores."""

    def __init__(self, title: str, loader, installer, status_checker, parent=None) -> None:
        super().__init__(parent)
        self.title = title
        self.loader = loader
        self.installer = installer
        self.status_checker = status_checker
        self.rows: list[_Row] = []
        self.worker: _BatchWorker | None = None
        self._checks: list[QCheckBox] = []
        self._build_ui()

    def _build_ui(self) -> None:
        """Monta busca, seleção, estado, progresso e log."""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.title))
        self.summary = QLabel("Nenhum sistema carregado")
        layout.addWidget(self.summary)
        actions = QHBoxLayout()
        self.search_button = QPushButton("BUSCAR DATS")
        self.search_button.clicked.connect(self.search)
        actions.addWidget(self.search_button)
        self.install_button = QPushButton("INSTALAR SELECIONADOS")
        self.install_button.clicked.connect(self.install_selected)
        actions.addWidget(self.install_button)
        self.update_button = QPushButton("VERIFICAR ATUALIZAÇÕES")
        self.update_button.clicked.connect(self.check_updates)
        actions.addWidget(self.update_button)
        select = QPushButton("SELECIONAR TODOS")
        select.clicked.connect(self.select_all)
        actions.addWidget(select)
        clear = QPushButton("LIMPAR SELEÇÃO")
        clear.clicked.connect(self.clear_selection)
        actions.addWidget(clear)
        actions.addStretch()
        layout.addLayout(actions)
        self.progress = QProgressBar(); self.progress.setRange(0, 100); layout.addWidget(self.progress)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True)
        self.container = QWidget(); self.rows_layout = QVBoxLayout(self.container); self.rows_layout.addStretch()
        self.scroll.setWidget(self.container); layout.addWidget(self.scroll, 1)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumBlockCount(2000); layout.addWidget(self.log, 1)
        self._set_busy(False)

    def _append(self, text: str) -> None:
        """Acrescenta uma mensagem no log visual e no logger."""
        self.log.appendPlainText(text); logger.info("[%s] %s", self.title, text)

    def search(self) -> None:
        """Consulta o backend, cruza com LaunchBox e cria uma lista marcada."""
        self._set_busy(True)
        try:
            entries = tuple(self.loader())
            self.rows = [_Row(self._entry_name(entry), entry, self._entry_state(entry)) for entry in entries]
            self._rebuild_rows()
            self.summary.setText(f"{len(self.rows)} sistemas encontrados")
            self._append(f"BUSCAR | sistemas={len(self.rows)}")
        except Exception as exc:  # noqa: BLE001
            self.rows = []; self._rebuild_rows(); self.summary.setText(f"Erro: {exc}"); self._append(f"ERRO | {type(exc).__name__}: {exc}")
        finally:
            self._set_busy(False)

    def _rebuild_rows(self) -> None:
        """Reconstrói os checkboxes a partir do catálogo atual."""
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._checks = []
        for row in self.rows:
            check = QCheckBox(f"{self._status_prefix(row.state)} {row.name}")
            check.setChecked(False)
            check.setProperty("entry_name", row.name)
            self._checks.append(check); self.rows_layout.addWidget(check)
        self.rows_layout.addStretch()

    @staticmethod
    def _status_prefix(state: str) -> str:
        """Converte estado lógico em marcador textual."""
        return {"current": "[OK]", "missing": "[AUSENTE]", "outdated": "[ATUALIZAR]", "unknown": "[?]"}.get(state, "[?]")

    @staticmethod
    def _entry_name(entry: object) -> str:
        """Extrai nome comum dos modelos No-Intro/Redump."""
        return str(getattr(entry, "name", entry))

    def _entry_state(self, entry: object) -> str:
        """Consulta o estado local do DAT sem baixar seu conteúdo."""
        try:
            status = self.status_checker(entry)
            return str(getattr(status, "state", status))
        except Exception:
            return "unknown"

    def _selected(self) -> list[_Row]:
        """Retorna as linhas correspondentes aos checkboxes marcados."""
        names = {check.property("entry_name") for check in self._checks if check.isChecked()}
        return [row for row in self.rows if row.name in names]

    def select_all(self) -> None:
        """Marca todos os sistemas exibidos."""
        for check in self._checks: check.setChecked(True)

    def clear_selection(self) -> None:
        """Desmarca todos os sistemas exibidos."""
        for check in self._checks: check.setChecked(False)

    def install_selected(self) -> None:
        """Instala todos os DATs marcados usando o worker em lote."""
        selected = self._selected()
        if not selected:
            QMessageBox.information(self, self.title, "Selecione pelo menos um sistema."); return
        self._start_worker(selected, self.installer)

    def check_updates(self) -> None:
        """Atualiza estados locais e marca somente os sistemas não atuais."""
        if not self.rows:
            self.search()
            if not self.rows: return
        updated: list[_Row] = []
        for row in self.rows:
            state = self._entry_state(row.entry)
            updated.append(_Row(row.name, row.entry, state))
        self.rows = updated
        self._rebuild_rows()
        for check, row in zip(self._checks, self.rows):
            check.setChecked(row.state in {"missing", "outdated", "unknown"})
        pending = sum(row.state in {"missing", "outdated", "unknown"} for row in self.rows)
        self.summary.setText(f"{len(self.rows)} sistemas | {pending} precisam de instalação/atualização")
        self._append(f"ATUALIZAÇÕES | candidatos={pending}")

    def _start_worker(self, selected: list[_Row], operation) -> None:
        """Inicia o lote e bloqueia controles enquanto a operação executa."""
        if self.worker and self.worker.isRunning(): return
        self._set_busy(True)
        self.worker = _BatchWorker(operation, selected, self)
        self.worker.progress.connect(lambda done, total, name: self._worker_progress(done, total, name))
        self.worker.message.connect(self._append)
        self.worker.done.connect(self._worker_done)
        self.worker.error.connect(lambda message: self._append(f"ERRO WORKER | {message}"))
        self.worker.finished.connect(lambda: self._set_busy(False))
        self.worker.start()

    def _worker_progress(self, done: int, total: int, name: str) -> None:
        """Atualiza barra e status do lote."""
        self.progress.setValue(int(done * 100 / total) if total else 100)
        self.summary.setText(f"Processando {done}/{total} | {name}")

    def _worker_done(self, ok: int, failed: int) -> None:
        """Atualiza a interface após o lote."""
        self.progress.setValue(100); self._append(f"CONCLUÍDO | OK={ok} | FALHAS={failed}"); self.search()

    def _set_busy(self, busy: bool) -> None:
        """Habilita/desabilita os comandos durante uma operação."""
        for button in (self.search_button, self.install_button, self.update_button): button.setEnabled(not busy)


class DatScraperPage(QWidget):
    """Container único para No-Intro, Redump e sessões de DAT adicionais."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.launchbox = LaunchBoxIntegration()
        self.launchbox_provider = LaunchBoxProvider(self.launchbox)
        self.no_intro = NoIntroArchiveProvider()
        self.redump = RedumpProvider()
        self._build_ui()

    def _build_ui(self) -> None:
        """Cria as seis sessões solicitadas em uma única guia."""
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._no_intro_tab(), "No-Intro")
        tabs.addTab(self._redump_tab(), "Redump")
        tabs.addTab(self._unavailable_tab("WHLOADER", "Backend histórico não está presente no código-fonte atual; não será simulado."), "WHLOADER")
        tabs.addTab(self._unavailable_tab("ExoDOS", "Backend histórico não está presente no código-fonte atual; não será simulado."), "ExoDOS")
        tabs.addTab(self._unavailable_tab("C64", "Backend histórico não está presente no código-fonte atual; não será simulado."), "C64")
        tabs.addTab(self._unavailable_tab("MAME", "Backend histórico específico desta sessão não está presente no código-fonte atual; não será simulado."), "MAME")
        layout.addWidget(tabs)

    def _no_intro_tab(self) -> DatSourceTab:
        """Cria a sessão No-Intro com o provider de arquivo bulk atual."""
        def load():
            entries = self.no_intro.fetch_catalog()
            names = tuple(platform.name for platform in self.launchbox_provider.iter_platforms())
            return self.no_intro.match(names, entries)
        return DatSourceTab("No-Intro — DATs", load, self.no_intro.download, self.no_intro.status, self)

    def _redump_tab(self) -> DatSourceTab:
        """Cria a sessão Redump com endpoint direto e catálogo atual."""
        def load():
            entries = self.redump.fetch_catalog()
            names = tuple(platform.name for platform in self.launchbox_provider.iter_platforms())
            return self.redump.match(names, entries)
        return DatSourceTab("Redump — DATs", load, self.redump.download, self.redump.status, self)

    @staticmethod
    def _unavailable_tab(name: str, message: str) -> QWidget:
        """Representa uma sessão cujo backend original não está recuperável no HEAD."""
        page = QWidget(); layout = QVBoxLayout(page)
        layout.addWidget(QLabel(name)); label = QLabel(message); label.setWordWrap(True); layout.addWidget(label)
        for text in ("BUSCAR DATS", "INSTALAR SELECIONADOS", "VERIFICAR ATUALIZAÇÕES", "SELECIONAR TODOS", "LIMPAR SELEÇÃO"):
            button = QPushButton(text); button.setEnabled(False); layout.addWidget(button)
        layout.addStretch(); return page


__all__ = ["DatScraperPage", "DatSourceTab"]
