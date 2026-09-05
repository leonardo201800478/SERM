"""Home V2 com gestão completa de emuladores e RetroArch."""
from __future__ import annotations

import json
import logging
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root
from ..services.emulator_manager import EmulatorManager, RetroArchManager

logger = logging.getLogger(__name__)


class _Worker(QThread):
    """Executa uma operação bloqueante fora da thread da interface."""

    progress = Signal(int, int)
    log = Signal(str)
    done = Signal(object)
    error = Signal(str)

    def __init__(self, operation, parent=None) -> None:
        super().__init__(parent)
        self.operation = operation

    def run(self) -> None:
        """Executa a operação e publica resultado/erro."""
        try:
            self.done.emit(
                self.operation(
                    progress=lambda received, total: self.progress.emit(received, total),
                    log=lambda message: self.log.emit(str(message)),
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Operação Home falhou")
            self.error.emit(f"{type(exc).__name__}: {exc}")


class EmulatorHomePage(QWidget):
    """Home 16:9 para emuladores standalone e RetroArch."""

    EMULATORS = ("mame", "flycast", "supermodel", "fbneo")
    LABELS = EmulatorManager.LABELS
    SITES = {
        "mame": "https://github.com/mamedev/mame",
        "flycast": "https://github.com/flyinghead/flycast",
        "supermodel": "https://github.com/trzy/supermodel",
        "fbneo": "https://github.com/finalburnneo/FBNeo",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.manager = EmulatorManager(self._load_paths())
        self.retroarch = RetroArchManager(self.manager.roots.get("retroarch"))
        self.worker: _Worker | None = None
        self._pending_continuation = None
        self.cards: dict[str, tuple[QLabel, QLabel, QLabel, QProgressBar, QPushButton]] = {}
        self.core_items: dict[str, QListWidgetItem] = {}
        self._core_queue: list[str] = []
        self._retro_channel = "stable"
        self._build_ui()
        self.refresh()

    @property
    def paths_file(self) -> Path:
        """Retorna o registro compartilhado de diretórios."""
        return data_root() / "emulator_paths.json"

    def _load_paths(self) -> dict[str, Path | None]:
        """Carrega diretórios, executáveis, versões e canal do RetroArch."""
        try:
            data = json.loads(self.paths_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(k): Path(str(v)).expanduser() if v else None for k, v in data.items()}

    def _save_paths(self, paths: dict[str, Path | None]) -> None:
        """Persiste o registro central sem apagar chaves existentes."""
        self.paths_file.parent.mkdir(parents=True, exist_ok=True)
        self.paths_file.write_text(
            json.dumps(
                {k: str(v) if v is not None else None for k, v in paths.items()},
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _build_ui(self) -> None:
        """Constrói a Home em proporção visual 16:9."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        title = QLabel("SERM V2 — Home")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:25px;font-weight:700;")
        layout.addWidget(title)
        from PySide6.QtWidgets import QTabWidget

        self.home_tabs = QTabWidget()
        self.home_tabs.addTab(self._arcade_tab(), "Emuladores")
        self.home_tabs.addTab(self._retroarch_tab(), "RetroArch")
        layout.addWidget(self.home_tabs, 1)

    def _arcade_tab(self) -> QWidget:
        """Cria cards dos quatro emuladores com versão instalada."""
        page = QWidget()
        layout = QVBoxLayout(page)
        frame = QFrame()
        grid = QGridLayout(frame)
        frame.setStyleSheet("QFrame{background:#151515;border:1px solid #3d3d3d;border-radius:8px;}")
        for index, key in enumerate(self.EMULATORS):
            card = QFrame()
            box = QVBoxLayout(card)
            name = QLabel(self.LABELS[key])
            name.setStyleSheet("font-size:15px;font-weight:bold;")
            status = QLabel("● Verificando…")
            version = QLabel("Versão instalada: —")
            path = QLabel("Instalação: —")
            path.setWordWrap(True)
            progress = QProgressBar()
            progress.hide()
            install = QPushButton("⬇ Baixar / atualizar")
            install.clicked.connect(lambda _=False, k=key: self.install(k))
            configure = QPushButton("📁 Diretório")
            configure.clicked.connect(lambda _=False, k=key: self.configure(k))
            site = QPushButton("🌐 Repositório")
            site.clicked.connect(lambda _=False, k=key: webbrowser.open(self.SITES[k]))
            row = QHBoxLayout()
            row.addWidget(install)
            row.addWidget(configure)
            row.addWidget(site)
            for widget in (name, status, version, path, progress):
                box.addWidget(widget)
            box.addLayout(row)
            self.cards[key] = (status, version, path, progress, install)
            grid.addWidget(card, index // 2, index % 2)
        layout.addWidget(frame)

        actions = QHBoxLayout()
        update = QPushButton("🔄 Atualizar todos")
        update.clicked.connect(self.update_all)
        actions.addWidget(update)
        dirs = QPushButton("📁 Configurar diretórios")
        dirs.clicked.connect(self.open_emulator_directories)
        actions.addWidget(dirs)
        clear = QPushButton("🧹 Limpar log")
        clear.clicked.connect(self.clear_install_log)
        actions.addWidget(clear)
        self.seven_zip = QLabel()
        actions.addWidget(self.seven_zip, 1)
        layout.addLayout(actions)

        layout.addWidget(QLabel("Log detalhado da instalação"))
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(3000)
        self.log_view.setStyleSheet("QPlainTextEdit{background:#0b0b0b;color:#d7d7d7;font-family:Consolas;font-size:10px;}")
        layout.addWidget(self.log_view, 1)
        return page

    def _retroarch_tab(self) -> QWidget:
        """Cria a interface RetroArch com seleção Stable/Nightly e log."""
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("RetroArch — Windows x64")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:22px;font-weight:bold;")
        layout.addWidget(title)

        channel_box = QGroupBox("Canal de distribuição")
        channel_layout = QHBoxLayout(channel_box)
        self.retro_stable = QRadioButton("Estável (recomendado)")
        self.retro_nightly = QRadioButton("Nightly (Buildbot)")
        channel_layout.addWidget(self.retro_stable)
        channel_layout.addWidget(self.retro_nightly)
        channel_layout.addStretch()
        self.retro_stable.setChecked(True)
        self.retro_stable.toggled.connect(self._retro_channel_changed)
        self.retro_nightly.toggled.connect(self._retro_channel_changed)
        layout.addWidget(channel_box)

        self.retro_status = QLabel()
        self.retro_path = QLabel()
        self.retro_version = QLabel()
        self.retro_cores = QLabel()
        for label in (self.retro_status, self.retro_path, self.retro_version, self.retro_cores):
            label.setWordWrap(True)
            layout.addWidget(label)

        actions = QHBoxLayout()
        for text, slot in (
            ("⬇ Instalar / atualizar", self.install_retroarch),
            ("📁 Diretório", self.configure_retroarch),
            ("🔄 Buscar cores", self.refresh_cores),
            ("🔎 Verificar atualizações", self.verify_core_updates),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            actions.addWidget(button)
        layout.addLayout(actions)

        selection = QHBoxLayout()
        for text, slot in (
            ("☑ Selecionar todos", self.select_all_cores),
            ("☐ Limpar seleção", self.clear_core_selection),
            ("⬇ Instalar selecionados", self.install_selected_cores),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            selection.addWidget(button)
        selection.addStretch()
        self.core_summary = QLabel("0 selecionado(s)")
        selection.addWidget(self.core_summary)
        layout.addLayout(selection)

        self.core_list = QListWidget()
        self.core_list.itemChanged.connect(self._core_selection_changed)
        layout.addWidget(self.core_list, 1)
        self.retro_progress = QProgressBar()
        self.retro_progress.hide()
        layout.addWidget(self.retro_progress)
        layout.addWidget(QLabel("Log RetroArch"))
        self.retro_log = QPlainTextEdit()
        self.retro_log.setReadOnly(True)
        self.retro_log.setMaximumBlockCount(3000)
        self.retro_log.setStyleSheet("QPlainTextEdit{background:#071007;color:#8ee28e;font-family:Consolas;font-size:10px;}")
        layout.addWidget(self.retro_log, 1)
        return page

    def _retro_channel_changed(self, checked: bool) -> None:
        """Persiste o canal selecionado e atualiza o catálogo."""
        if not checked:
            return
        self._retro_channel = "nightly" if self.retro_nightly.isChecked() else "stable"
        paths = self._load_paths()
        paths["retroarch_channel"] = Path(self._retro_channel)
        self._save_paths(paths)
        self._append_retro_log(f"RETROARCH | canal selecionado={self._retro_channel}")
        self.refresh()

    def refresh(self) -> None:
        """Atualiza descoberta, versões instaladas e estado do RetroArch."""
        self.manager.roots = self._load_paths()
        self.retroarch = RetroArchManager(self.manager.roots.get("retroarch"))
        paths = self._load_paths()
        channel = paths.get("retroarch_channel")
        self._retro_channel = str(channel) if channel else "stable"
        if hasattr(self, "retro_stable"):
            self.retro_stable.blockSignals(True)
            self.retro_nightly.blockSignals(True)
            self.retro_stable.setChecked(self._retro_channel == "stable")
            self.retro_nightly.setChecked(self._retro_channel == "nightly")
            self.retro_stable.blockSignals(False)
            self.retro_nightly.blockSignals(False)

        for key, status in self.manager.discover().items():
            card = self.cards[key]
            if status.state == "ready":
                text, color = "● Pronto", "#55d66b"
            elif status.state == "configured":
                text, color = "● Diretório configurado; executável ausente", "#e5c454"
            else:
                text, color = "● Não configurado", "#999"
            card[0].setText(text)
            card[0].setStyleSheet(f"color:{color};font-weight:bold;")
            card[1].setText(f"Versão instalada: {status.version or 'não detectada'}")
            card[2].setText(f"Instalação: {status.root or 'não configurada'}")
            card[4].setEnabled(self.worker is None)

        self.seven_zip.setText(f"7-Zip: {self.manager.find_7zip() or 'não encontrado'}")
        executable, root, cores = self.retroarch.discover()
        version = self.retroarch.detect_version(executable)
        self.retro_status.setText("● Pronto" if executable else "● Não configurado")
        self.retro_status.setStyleSheet("color:#55d66b;font-weight:bold;" if executable else "color:#e5c454;font-weight:bold;")
        self.retro_path.setText(f"Instalação: {root or 'não configurada'}")
        self.retro_version.setText(f"Versão instalada: {version or 'não detectada'}")
        self.retro_cores.setText(f"Cores: {cores or 'não configurado'}")

    def configure(self, key: str) -> None:
        """Seleciona somente o diretório de instalação do emulador."""
        selected = QFileDialog.getExistingDirectory(self, f"Diretório do {self.LABELS[key]}", str(Path.home()))
        if not selected:
            return
        paths = self._load_paths()
        paths[key] = Path(selected).resolve()
        self._save_paths(paths)
        self.manager.roots = paths
        self.refresh()

    def install(self, key: str) -> None:
        """Instala/atualiza um emulador em background."""
        destination = self.manager.roots.get(key)
        if not destination:
            selected = QFileDialog.getExistingDirectory(self, f"Instalar {self.LABELS[key]} em", str(Path.home()))
            if not selected:
                return
            destination = Path(selected).resolve()
            paths = self._load_paths()
            paths[key] = destination
            self._save_paths(paths)
            self.manager.roots = paths
        self._start(lambda progress, log: self.manager.install(key, destination, progress=progress, log=log), key)

    def update_all(self) -> None:
        """Atualiza os quatro emuladores em sequência, inclusive após falhas."""
        if self.worker is not None:
            self._append_log("ATUALIZAR TODOS | já existe uma operação em execução")
            return

        self.manager.roots = self._load_paths()
        queue = list(self.EMULATORS)

        def next_one() -> None:
            if not queue:
                self._append_log("ATUALIZAR TODOS | operação concluída")
                self.refresh()
                return

            key = queue.pop(0)
            destination = self.manager.roots.get(key)
            if not destination:
                self._append_log(f"IGNORADO | {self.LABELS[key]} | diretório não configurado")
                next_one()
                return

            destination = Path(destination).resolve()
            self._append_log(f"ATUALIZAR TODOS | iniciando {self.LABELS[key]} | destino={destination}")
            self._start(
                lambda progress, log, k=key, d=destination: self.manager.install(
                    k, d, progress=progress, log=log
                ),
                key,
                next_one,
            )

        next_one()

    def _start(self, operation, key: str, continuation=None) -> None:
        """Executa operação standalone em worker e posterga a continuação."""
        if self.worker:
            return
        self._pending_continuation = continuation
        self.worker = _Worker(operation, self)
        self.worker.progress.connect(lambda received, total, k=key: self._progress(k, received, total))
        self.worker.log.connect(self._append_log)
        self.worker.done.connect(lambda result, k=key: self._done(k, result))
        self.worker.error.connect(lambda message, k=key: self._error(k, message))
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _progress(self, key: str, received: int, total: int) -> None:
        """Atualiza a barra de download do emulador."""
        bar = self.cards[key][3]
        bar.show()
        bar.setRange(0, 100 if total else 0)
        bar.setValue(min(100, int(received * 100 / total)) if total else 0)

    def _append_log(self, message: str) -> None:
        """Adiciona diagnóstico ao log da Home."""
        self.log_view.appendPlainText(str(message))
        logger.info("[HOME] %s", message)

    def clear_install_log(self) -> None:
        """Limpa o log dos emuladores."""
        self.log_view.clear()

    def _append_retro_log(self, message: str) -> None:
        """Adiciona diagnóstico ao log do RetroArch."""
        self.retro_log.appendPlainText(str(message))
        logger.info("[RETROARCH][HOME] %s", message)

    def _done(self, key: str, result) -> None:
        """Persiste diretório, executável e versão confirmada pelo release."""
        paths = self._load_paths()
        paths[key] = Path(result.executable).parent
        paths[f"{key}_exe"] = Path(result.executable).resolve()
        paths[f"{key}_version"] = Path(str(result.version))
        self._save_paths(paths)
        self._append_log(f"SUCESSO | {self.LABELS[key]} | versão={result.version} | exe={result.executable}")
        self.refresh()

    def _error(self, key: str, message: str) -> None:
        """Registra erro sem interromper uma atualização em lote."""
        self._append_log(f"ERRO | {self.LABELS[key]} | {message}")

    def _worker_finished(self) -> None:
        """Libera o worker e só então inicia a próxima operação da fila."""
        continuation = self._pending_continuation
        self._pending_continuation = None
        self.worker = None
        self.retro_progress.hide()
        self.refresh()
        if continuation is not None:
            continuation()

    def open_emulator_directories(self) -> None:
        """Abre a página central de Diretórios pela navegação lateral."""
        window = self.window()
        navigation = getattr(window, "navigation", None)
        directories = getattr(window, "directories_tab", None)
        page_stack = getattr(window, "page_stack", None)
        if navigation is None or directories is None or page_stack is None:
            self._append_log("ERRO | Não foi possível localizar a página central de Diretórios")
            return

        for index in range(navigation.count()):
            item = navigation.item(index)
            if item is not None and item.text().casefold() == "diretórios":
                navigation.setCurrentRow(index)
                return

        index = page_stack.indexOf(directories)
        if index >= 0:
            page_stack.setCurrentIndex(index)
            directories.refresh()

    def configure_retroarch(self) -> None:
        """Seleciona e persiste a instalação do RetroArch."""
        selected = QFileDialog.getExistingDirectory(self, "Diretório do RetroArch", str(Path.home()))
        if not selected:
            return
        paths = self._load_paths()
        paths["retroarch"] = Path(selected).resolve()
        self._save_paths(paths)
        self.refresh()

    def install_retroarch(self) -> None:
        """Instala/atualiza RetroArch no canal Stable ou Nightly selecionado."""
        destination = self.manager.roots.get("retroarch")
        if not destination:
            selected = QFileDialog.getExistingDirectory(self, "Instalar RetroArch em", str(Path.home()))
            if not selected:
                return
            destination = Path(selected).resolve()
            paths = self._load_paths()
            paths["retroarch"] = destination
            self._save_paths(paths)
        self.retroarch = RetroArchManager(destination)
        self._start_retro(
            lambda progress, log: self.retroarch.install_core(
                "", destination, channel=self._retro_channel, progress=progress, log=log
            )
        )

    def refresh_cores(self) -> None:
        """Atualiza o índice oficial e mostra cores instalados, novos e CRC."""
        try:
            cores = self.retroarch.list_cores(self._retro_channel)
            _, _, destination = self.retroarch.discover()
            installed = self.retroarch.installed_cores(destination) if destination else ()
            comparisons = self.retroarch.compare_installed_cores(cores, destination) if destination and destination.is_dir() else []
            state_map = {path.name.casefold(): state for path, _, state in comparisons}
            self.core_list.blockSignals(True)
            self.core_list.clear()
            self.core_items.clear()
            installed_count = 0
            update_count = 0
            for core in cores:
                key = core.filename.removesuffix(".zip").casefold()
                state = state_map.get(key, "new")
                if key in {path.name.casefold() for path in installed}:
                    installed_count += 1
                if state == "update":
                    update_count += 1
                marker = "[ATUALIZADO]" if state == "current" else "[ATUALIZAÇÃO]" if state == "update" else "[NOVO]"
                item = QListWidgetItem(f"{marker} {core.core_name} | {core.date} | CRC {core.crc32}")
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setData(Qt.ItemDataRole.UserRole, core.filename)
                item.setData(Qt.ItemDataRole.UserRole + 1, state)
                self.core_list.addItem(item)
                self.core_items[core.filename] = item
            self.core_list.blockSignals(False)
            new_count = len(cores) - installed_count
            self.core_summary.setText(f"{len(cores)} publicados  •  {installed_count} instalados  •  {update_count} atualizações  •  {new_count} novos")
            self._update_core_summary()
            self._append_retro_log(f"CATÁLOGO | canal={self._retro_channel} | cores={len(cores)} | instalados={installed_count} | atualizações={update_count} | novos={new_count}")
        except Exception as exc:  # noqa: BLE001
            self._append_retro_log(f"ERRO CORES | {type(exc).__name__}: {exc}")
            QMessageBox.warning(self, "RetroArch", str(exc))

    def verify_core_updates(self) -> None:
        """Compara CRC dos cores instalados e seleciona somente os desatualizados."""
        try:
            _, _, destination = self.retroarch.discover()
            if destination is None or not destination.is_dir():
                self._append_retro_log("AVISO | diretório de cores do RetroArch não configurado ou inexistente.")
                return
            cores = self.retroarch.list_cores(self._retro_channel)
            comparisons = self.retroarch.compare_installed_cores(cores, destination)
            self.core_list.blockSignals(True)
            self.core_list.clear()
            self.core_items.clear()
            updates = current = unknown = 0
            for path, remote, state in comparisons:
                if remote is None:
                    unknown += 1
                    continue
                if state == "update":
                    updates += 1
                    text = f"[ATUALIZAÇÃO] {remote.core_name} | CRC local {self.retroarch.crc32(path)} → remoto {remote.crc32}"
                    checked = True
                else:
                    current += 1
                    text = f"[ATUALIZADO] {remote.core_name} | CRC {remote.crc32}"
                    checked = False
                item = QListWidgetItem(text)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                item.setData(Qt.ItemDataRole.UserRole, remote.filename)
                item.setData(Qt.ItemDataRole.UserRole + 1, state)
                self.core_list.addItem(item)
                self.core_items[remote.filename] = item
            self.core_list.blockSignals(False)
            self.core_summary.setText(f"{updates} atualizações disponíveis  •  {current} atualizados  • {unknown} sem correspondência")
            self._update_core_summary()
            self._append_retro_log(f"ATUALIZAÇÕES | instalados={len(comparisons)} | atualizações={updates} | atualizados={current} | sem correspondência={unknown}")
            if not updates:
                self._append_retro_log("ATUALIZAÇÕES | nenhum core instalado necessita de atualização.")
        except Exception as exc:  # noqa: BLE001
            self._append_retro_log(f"ERRO ATUALIZAÇÕES | {type(exc).__name__}: {exc}")
            QMessageBox.warning(self, "RetroArch", str(exc))

    def select_all_cores(self) -> None:
        """Seleciona todos os cores."""
        self.core_list.blockSignals(True)
        for i in range(self.core_list.count()):
            self.core_list.item(i).setCheckState(Qt.CheckState.Checked)
        self.core_list.blockSignals(False)
        self._update_core_summary()

    def clear_core_selection(self) -> None:
        """Limpa a seleção dos cores."""
        self.core_list.blockSignals(True)
        for i in range(self.core_list.count()):
            self.core_list.item(i).setCheckState(Qt.CheckState.Unchecked)
        self.core_list.blockSignals(False)
        self._update_core_summary()

    def _core_selection_changed(self, _item: QListWidgetItem) -> None:
        """Atualiza o contador de cores selecionados."""
        self._update_core_summary()

    def _update_core_summary(self) -> None:
        """Atualiza o resumo de seleção do catálogo."""
        selected = sum(
            self.core_list.item(i).checkState() == Qt.CheckState.Checked
            for i in range(self.core_list.count())
        )
        if self.core_list.count() == 0:
            self.core_summary.setText("0 selecionado(s)")
            return
        self.core_summary.setText(f"{selected} selecionado(s) de {self.core_list.count()}")

    def _start_retro(self, operation) -> None:
        """Executa uma operação RetroArch em worker."""
        if self.worker:
            return
        self.retro_progress.show()
        self.worker = _Worker(operation, self)
        self.worker.progress.connect(self._retro_progress)
        self.worker.log.connect(self._append_retro_log)
        self.worker.done.connect(self._retro_done)
        self.worker.error.connect(self._retro_error)
        self.worker.finished.connect(self._retro_worker_finished)
        self.worker.start()

    def _retro_progress(self, received: int, total: int) -> None:
        """Atualiza a barra de progresso do RetroArch."""
        self.retro_progress.setRange(0, 100 if total else 0)
        self.retro_progress.setValue(min(100, int(received * 100 / total)) if total else 0)

    def _retro_done(self, result) -> None:
        """Registra sucesso da operação RetroArch."""
        self._append_retro_log(f"OK | {result}")

    def _retro_error(self, message: str) -> None:
        """Registra a falha final da operação RetroArch."""
        self._append_retro_log(f"ERRO | {message}")

    def _retro_worker_finished(self) -> None:
        """Libera o worker RetroArch após terminar."""
        self.worker = None
        self.retro_progress.hide()
        self.refresh()


__all__ = ["EmulatorHomePage"]
