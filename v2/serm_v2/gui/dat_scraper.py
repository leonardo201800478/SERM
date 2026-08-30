"""Scraper unificado de DATs do SERM V2."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..integrations.launchbox import LaunchBoxIntegration
from ..integrations.launchbox_provider import LaunchBoxProvider
from ..services.mame_catalog_service import MameCatalogError, MameCatalogService
from ..services.mame_classification_service import MameClassificationError, MameClassificationService
from ..sources.acquisition.no_intro_archive import NoIntroArchiveProvider
from ..sources.acquisition.redump import RedumpProvider

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
        ok = failed = 0
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


class _MameCatalogWorker(QThread):
    """Executa a ingestão do ListXML pelo MAME configurado sem bloquear o Qt."""
    completed = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        """Executa ``mame.exe -listxml`` e persiste o catálogo na V2."""
        try:
            self.completed.emit(MameCatalogService().ingest())
        except MameCatalogError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class _MameCatlistWorker(QThread):
    """Importa o CATLIST em background para manter a interface responsiva."""
    message = Signal(str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, database_path, mame_root, parent=None) -> None:
        super().__init__(parent)
        self.database_path = database_path
        self.mame_root = mame_root

    def run(self) -> None:
        """Executa a Etapa 2 e encaminha cada evento para o log da GUI."""
        try:
            service = MameClassificationService(self.database_path, self.mame_root)
            result = service.ingest(logger=self.message.emit)
            self.completed.emit(result)
        except MameClassificationError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class DatSourceTab(QWidget):
    """Aba genérica com seleção individual de sistemas e operações em lote."""
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
        """Monta busca, seleção, atualização, progresso e log."""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self.title))
        self.summary = QLabel("Nenhum sistema carregado")
        layout.addWidget(self.summary)
        actions = QHBoxLayout()
        actions_config = (("BUSCAR DATS", self.search, "search_button"), ("INSTALAR SELECIONADOS", self.install_selected, "install_button"), ("VERIFICAR ATUALIZAÇÕES", self.check_updates, "update_button"), ("SELECIONAR TODOS", self.select_all, "select_button"), ("LIMPAR SELEÇÃO", self.clear_selection, "clear_button"))
        for text, slot, attr in actions_config:
            button = QPushButton(text)
            button.clicked.connect(slot)
            setattr(self, attr, button)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.rows_layout = QVBoxLayout(self.container)
        self.rows_layout.addStretch()
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, 1)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        layout.addWidget(self.log, 1)

    def _append(self, text: str) -> None:
        """Registra uma mensagem na interface e no logger."""
        self.log.appendPlainText(text)
        logger.info("[%s] %s", self.title, text)

    @staticmethod
    def _entry_name(entry) -> str:
        """Obtém o nome do sistema de qualquer modelo de catálogo."""
        return str(getattr(entry, "name", entry))

    def _entry_state(self, entry) -> str:
        """Consulta o estado local do DAT."""
        try:
            return str(getattr(self.status_checker(entry), "state", "unknown"))
        except Exception:  # noqa: BLE001
            return "unknown"

    def search(self) -> None:
        """Busca o catálogo e cruza seus sistemas com as plataformas do LaunchBox."""
        self._set_busy(True)
        try:
            entries = tuple(self.loader())
            self.rows = [_Row(self._entry_name(entry), entry, self._entry_state(entry)) for entry in entries]
            self._rebuild_rows()
            self.summary.setText(f"{len(self.rows)} sistemas encontrados")
            self._append(f"BUSCAR | sistemas={len(self.rows)}")
        except Exception as exc:  # noqa: BLE001
            self.rows = []
            self._rebuild_rows()
            self.summary.setText(f"Erro: {exc}")
            self._append(f"ERRO | {type(exc).__name__}: {exc}")
        finally:
            self._set_busy(False)

    def _rebuild_rows(self) -> None:
        """Reconstrói a lista de sistemas com um check por sistema."""
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._checks = []
        for row in self.rows:
            check = QCheckBox(f"{self._prefix(row.state)} {row.name}")
            check.setProperty("entry_name", row.name)
            self._checks.append(check)
            self.rows_layout.addWidget(check)
        self.rows_layout.addStretch()

    @staticmethod
    def _prefix(state: str) -> str:
        """Formata o estado do DAT na lista."""
        return {"current": "[OK]", "missing": "[AUSENTE]", "outdated": "[ATUALIZAR]", "unknown": "[?]"}.get(state, "[?]")

    def _selected(self) -> list[_Row]:
        """Retorna somente os sistemas marcados."""
        names = {check.property("entry_name") for check in self._checks if check.isChecked()}
        return [row for row in self.rows if row.name in names]

    def select_all(self) -> None:
        """Marca todos os sistemas."""
        for check in self._checks:
            check.setChecked(True)

    def clear_selection(self) -> None:
        """Limpa toda a seleção."""
        for check in self._checks:
            check.setChecked(False)

    def install_selected(self) -> None:
        """Instala os DATs selecionados em lote."""
        selected = self._selected()
        if not selected:
            QMessageBox.information(self, self.title, "Selecione pelo menos um sistema.")
            return
        self._start_worker(selected, self.installer)

    def check_updates(self) -> None:
        """Recalcula os estados locais e seleciona os que requerem ação."""
        if not self.rows:
            self.search()
        if not self.rows:
            return
        self.rows = [_Row(row.name, row.entry, self._entry_state(row.entry)) for row in self.rows]
        self._rebuild_rows()
        for check, row in zip(self._checks, self.rows, strict=True):
            check.setChecked(row.state in {"missing", "outdated", "unknown"})
        pending = sum(row.state in {"missing", "outdated", "unknown"} for row in self.rows)
        self.summary.setText(f"{len(self.rows)} sistemas | {pending} precisam de instalação/atualização")
        self._append(f"ATUALIZAÇÕES | candidatos={pending}")

    def _start_worker(self, selected, operation) -> None:
        """Executa a operação em background para não bloquear o Qt."""
        if self.worker and self.worker.isRunning():
            return
        self._set_busy(True)
        self.worker = _BatchWorker(operation, selected, self)
        self.worker.progress.connect(self._progress)
        self.worker.message.connect(self._append)
        self.worker.done.connect(self._done)
        self.worker.error.connect(lambda msg: self._append(f"ERRO WORKER | {msg}"))
        self.worker.finished.connect(lambda: self._set_busy(False))
        self.worker.start()

    def _progress(self, done: int, total: int, name: str) -> None:
        """Atualiza progresso e descrição do lote."""
        self.progress.setValue(int(done * 100 / total) if total else 100)
        self.summary.setText(f"Processando {done}/{total} | {name}")

    def _done(self, ok: int, failed: int) -> None:
        """Atualiza o catálogo após terminar o lote."""
        self.progress.setValue(100)
        self._append(f"CONCLUÍDO | OK={ok} | FALHAS={failed}")
        self.search()

    def _set_busy(self, busy: bool) -> None:
        """Bloqueia ações conflitantes durante uma operação."""
        for button in (self.search_button, self.install_button, self.update_button, self.select_button, self.clear_button):
            button.setEnabled(not busy)


class _MameTab(QWidget):
    """Sessão MAME do Scraper de DATs; ListXML e CATLIST são etapas separadas."""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.service = MameCatalogService()
        self.worker: _MameCatalogWorker | None = None
        self.catlist_worker: _MameCatlistWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        """Monta a sessão MAME com operações independentes e log operacional."""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("MAME — DAT / Catálogo"))
        self.executable = QLabel("Executável configurado: —")
        layout.addWidget(self.executable)
        self.status = QLabel("Nenhuma operação executada.")
        layout.addWidget(self.status)

        actions = QHBoxLayout()
        self.run_button = QPushButton("OBTER LISTXML (-listxml)")
        self.run_button.clicked.connect(self.ingest)
        actions.addWidget(self.run_button)
        self.catlist_button = QPushButton("IMPORTAR CATLIST")
        self.catlist_button.setToolTip("Importa folders\\catlist.ini; usa cat32en\\catlist.ini somente como fallback.")
        self.catlist_button.clicked.connect(self.ingest_catlist)
        actions.addWidget(self.catlist_button)
        self.refresh_button = QPushButton("ATUALIZAR EXECUTÁVEL")
        self.refresh_button.clicked.connect(self.refresh)
        actions.addWidget(self.refresh_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(3000)
        layout.addWidget(self.log, 1)
        self.refresh()

    def _log(self, level: str, message: str) -> None:
        """Adiciona uma entrada operacional padronizada com timestamp UTC."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        line = f"{timestamp} | {level:<7} | {message}"
        self.log.appendPlainText(line)
        logger.info("[MAME Scraper] %s", line)

    def refresh(self) -> None:
        """Mostra o executável MAME atualmente selecionado em Diretórios."""
        try:
            executable = self.service.configured_executable()
            self.executable.setText(f"Executável configurado: {executable}")
            self.run_button.setEnabled(True)
            self._log("INFO", f"Executável validado: {executable}")
        except MameCatalogError as exc:
            self.executable.setText("Executável configurado: não definido")
            self.status.setText(str(exc))
            self.run_button.setEnabled(False)
            self.catlist_button.setEnabled(False)
            self._log("WARN", str(exc))

    def ingest(self) -> None:
        """Inicia a ingestão do ListXML usando o executável configurado."""
        if self.worker and self.worker.isRunning():
            return
        self.refresh()
        if not self.run_button.isEnabled():
            return
        self.run_button.setEnabled(False)
        self.catlist_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.progress.setVisible(True)
        self.status.setText("Executando MAME -listxml…")
        self._log("START", "Iniciando captura do ListXML pelo executável configurado")
        self.worker = _MameCatalogWorker(self)
        self.worker.completed.connect(self._completed)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def ingest_catlist(self) -> None:
        """Inicia a importação do CATLIST sem bloquear a interface."""
        if self.catlist_worker and self.catlist_worker.isRunning():
            return
        try:
            executable = self.service.configured_executable()
        except MameCatalogError as exc:
            self._log("ERROR", str(exc))
            return
        database_path = self.service.DB_FILE
        mame_root = executable.parent
        self.run_button.setEnabled(False)
        self.catlist_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.progress.setVisible(True)
        self.status.setText("Importando CATLIST…")
        self._log("START", "Iniciando Etapa 2 — classificação CATLIST")
        self._log("INFO", f"Raiz MAME para fontes: {mame_root}")
        self.catlist_worker = _MameCatlistWorker(database_path, mame_root, self)
        self.catlist_worker.message.connect(lambda msg: self._log("INFO", msg))
        self.catlist_worker.completed.connect(self._catlist_completed)
        self.catlist_worker.failed.connect(self._catlist_failed)
        self.catlist_worker.finished.connect(self._catlist_finished)
        self.catlist_worker.start()

    def _catlist_completed(self, result: object) -> None:
        """Mostra o resumo da importação CATLIST."""
        data = result
        self.status.setText(f"CATLIST concluído | entradas={data['entries']:,} | resolvidas={data['resolved']:,} | não resolvidas={data['unresolved']:,}")
        self._log("OK", f"CATLIST | entradas={data['entries']:,}")
        self._log("OK", f"CATLIST | resolvidas={data['resolved']:,}")
        self._log("OK", f"CATLIST | não resolvidas={data['unresolved']:,}")
        self._log("OK", f"CATLIST | source_id={data['source_id']}")
        self._log("DONE", "Etapa 2 — classificação CATLIST concluída")

    def _catlist_failed(self, message: str) -> None:
        """Exibe falha do CATLIST preservando a causa."""
        self.status.setText("Falha na importação CATLIST")
        self._log("ERROR", message)
        self._log("DONE", "Etapa 2 encerrada com erro; dados anteriores preservados")

    def _catlist_finished(self) -> None:
        """Libera controles depois da thread CATLIST."""
        self.progress.setVisible(False)
        self.refresh_button.setEnabled(True)
        self.refresh()

    def _completed(self, result: object) -> None:
        """Exibe métricas, proveniência e política de deduplicação da ingestão."""
        data = result
        build = data.get("mame_build") or "não informado"
        source_hash = data.get("source_hash") or "não informado"
        elapsed = float(data.get("elapsed_seconds") or 0.0)
        mode = "REUTILIZADA (mesmo SHA-256)" if data.get("deduplicated") else "NOVA IMPORTAÇÃO"
        if data.get("force"):
            mode = "FORÇADA"
        self.status.setText(f"Concluído | MAME {build} | {data['machine_count']:,} máquinas | {data['display_count']:,} displays | {elapsed:.2f}s")
        self._log("OK", f"Versão/build: {build}")
        self._log("OK", f"Máquinas: {data['machine_count']:,}")
        self._log("OK", f"Displays normalizados: {data['display_count']:,}")
        self._log("OK", f"SHA-256 do ListXML: {source_hash}")
        self._log("OK", f"Política de importação: {mode}")
        self._log("OK", f"XML lossless: {data['xml_path']}")
        self._log("OK", f"Cópia compatível: {data['raw_xml']}")
        self._log("OK", f"Banco: {data['database']}")
        self._log("OK", f"Tempo total: {elapsed:.2f}s")
        self._log("DONE", "Ingestão finalizada com sucesso")

    def _failed(self, message: str) -> None:
        """Exibe a falha sem ocultar a causa original."""
        self.status.setText("Falha na ingestão")
        self._log("ERROR", message)
        self._log("DONE", "Ingestão encerrada com erro; dados anteriores foram preservados")

    def _finished(self) -> None:
        """Libera os controles após a thread terminar."""
        self.progress.setVisible(False)
        self.refresh_button.setEnabled(True)
        self.refresh()


class DatScraperPage(QWidget):
    """Agrupa todas as sessões de DAT solicitadas pelo usuário."""
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.launchbox = LaunchBoxIntegration()
        self.launchbox_provider = LaunchBoxProvider(self.launchbox)
        self.no_intro = NoIntroArchiveProvider()
        self.redump = RedumpProvider()
        self._build_ui()

    def _build_ui(self) -> None:
        """Cria as sessões No-Intro, Redump e as sessões históricas."""
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._no_intro_tab(), "No-Intro")
        self.tabs.addTab(self._redump_tab(), "Redump")
        for name in ("WHLOADER", "ExoDOS", "C64"):
            self.tabs.addTab(self._historical_tab(name), name)
        self.tabs.addTab(_MameTab(self), "MAME")
        layout.addWidget(self.tabs)

    def _no_intro_tab(self) -> DatSourceTab:
        """Liga No-Intro ao arquivo bulk e ao matching LaunchBox."""
        def load():
            entries = self.no_intro.fetch_catalog()
            names = tuple(platform.name for platform in self.launchbox_provider.iter_platforms())
            return self.no_intro.match(names, entries)
        return DatSourceTab("No-Intro — DATs", load, self.no_intro.download, self.no_intro.status, self)

    def _redump_tab(self) -> DatSourceTab:
        """Liga Redump ao catálogo público e aos endpoints diretos."""
        def load():
            entries = self.redump.fetch_catalog()
            names = tuple(platform.name for platform in self.launchbox_provider.iter_platforms())
            return self.redump.match(names, entries)
        return DatSourceTab("Redump — DATs", load, self.redump.download, self.redump.status, self)

    @staticmethod
    def _historical_tab(name: str) -> QWidget:
        """Mantém a sessão histórica visível sem inventar backend ausente."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(name))
        detail = QLabel("A sessão está reservada para o backend original. O código-fonte atual não contém uma implementação recuperável desta fonte; por isso nenhum download fictício será executado.")
        detail.setWordWrap(True)
        layout.addWidget(detail)
        row = QHBoxLayout()
        for text in ("BUSCAR DATS", "INSTALAR SELECIONADOS", "VERIFICAR ATUALIZAÇÕES", "SELECIONAR TODOS", "LIMPAR SELEÇÃO"):
            button = QPushButton(text)
            button.setEnabled(False)
            row.addWidget(button)
        layout.addLayout(row)
        layout.addStretch()
        return page


__all__ = ["DatScraperPage", "DatSourceTab"]
