"""Home V2 com gestão completa de emuladores e RetroArch."""

from __future__ import annotations

import json
import logging
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING, cast

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
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import data_root
from ..services.emulator_manager import EmulatorManager, RetroArchManager
from .emulator_catalog import grouped_emulators

if TYPE_CHECKING:
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class _Worker(QThread):
    """Executa uma operação bloqueante fora da thread da interface."""

    progress = Signal(int, int)
    install_progress = Signal(int, int)
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
                    install_progress=lambda completed, total: self.install_progress.emit(
                        completed, total
                    ),
                    log=lambda message: self.log.emit(str(message)),
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Operação Home falhou")
            self.error.emit(f"{type(exc).__name__}: {exc}")


class EmulatorHomePage(QWidget):
    """Home 16:9 para emuladores standalone e RetroArch."""

    EMULATOR_GROUPS = grouped_emulators(EmulatorManager.LABELS, include_retroarch=False)

    EMULATORS = tuple(EmulatorManager.LABELS)
    LABELS = EmulatorManager.LABELS
    SITES = {
        "mame": "https://github.com/mamedev/mame",
        "flycast": "https://flyinghead.github.io/flycast-builds/",
        "supermodel": "https://github.com/trzy/supermodel",
        "fbneo": "https://github.com/finalburnneo/FBNeo",
        "ymir": "https://github.com/ymir-emu/Ymir/releases/latest-nightly",
        "duckstation": "https://github.com/stenzek/duckstation/releases/tag/latest",
        "pcsx2": "https://github.com/PCSX2/pcsx2/releases",
        "ppsspp": "https://www.ppsspp.org/devbuilds/",
        "dolphin": "https://br.dolphin-emu.org/download/#download-dev",
        "xemu": "https://github.com/xemu-project/xemu/releases/tag/pre-release",
        "azaharplus": "https://github.com/AzaharPlus/AzaharPlus/releases",
        "rpcs3": "https://github.com/RPCS3/rpcs3-binaries-win/releases",
        "xenia_canary": "https://github.com/xenia-canary/xenia-canary/releases",
        "cemu": "https://github.com/cemu-project/Cemu/releases",
        "melonds": "https://github.com/melonDS-emu/melonDS/releases",
        "mgba": "https://mgba.io/downloads.html",
        "shadps4": "https://github.com/shadps4-emu/shadPS4-qtlauncher/releases",
        "ares": "https://github.com/ares-emulator/ares/releases",
        "dosbox_staging": "https://github.com/dosbox-staging/dosbox-staging/releases",
        "scummvm": "https://www.scummvm.org/downloads/",
        "mesence": "https://github.com/nesdev-org/MesenCE/releases",
        "sameboy": "https://sameboy.github.io/downloads/",
        "ryujinx_nextendo": "https://github.com/NextendoNetwork/Ryujinx-Nextendo/releases",
        "super_zsnes": "https://www.zsnes.com/#downloads",
        "winuae": "https://www.winuae.net/download/",
        "vice": "https://vice-emu.sourceforge.io/",
        "xm6pro68k": "https://mijet.eludevisibility.org/XM6%20Pro-68k/XM6%20Pro-68k.html",
        "dosbox_x": "https://github.com/joncampbell123/dosbox-x/releases",
        "stella": "https://github.com/stella-emu/stella/releases/latest",
        "altirra": "https://www.virtualdub.org/altirra.html",
        "rmg": "https://github.com/Rosalie241/RMG/releases/latest",
        "bigpemu": "https://www.richwhitehouse.com/jaguar/index.php?content=download",
        "blastem": "https://www.rhope.retrodev.com/blastem/downloads.html",
        "bizhawk": "https://github.com/TASEmulators/BizHawk/releases/latest",
        "dosbox_pure": "https://github.com/schellingb/dosbox-pure-unleashed/releases/latest",
        "yabasanshiro": "https://www.emu-france.com/emulateurs/5-consoles-de-salon/50-sega-saturn/7869-yabasanshiro-2/",
        "amiberry": "https://github.com/BlitterStudio/amiberry/releases",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.manager = EmulatorManager(self._load_paths())
        self.retroarch = RetroArchManager(self.manager.roots.get("retroarch"))
        self.worker: _Worker | None = None
        self._pending_continuation = None
        self.cards: dict[
            str, tuple[QLabel, QLabel, QLabel, QProgressBar, QProgressBar, QPushButton]
        ] = {}
        self.core_items: dict[str, QListWidgetItem] = {}
        self._core_queue: list[str] = []
        self._retro_channel = "stable"
        self._core_total_count = 0
        self._core_completed_count = 0
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

    @staticmethod
    def _persist_version_marker(executable: Path, version: str, archive: str) -> None:
        """Persiste a versão e o pacote que originaram a instalação."""
        marker = executable.parent / ".serm-version"
        try:
            marker.write_text(
                f"version={version}\narchive={archive}\n",
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Não foi possível persistir marcador de versão em %s: %s", marker, exc)

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
        grouped_keys = {key for _title, keys in self.EMULATOR_GROUPS for key in keys}
        groups = (
            *self.EMULATOR_GROUPS,
            ("Outros", tuple(key for key in self.EMULATORS if key not in grouped_keys)),
        )
        for group_title, keys in groups:
            if keys:
                self.home_tabs.addTab(self._emulator_group_tab(keys), group_title)
        self.home_tabs.addTab(self._retroarch_tab(), "RetroArch")
        layout.addWidget(self.home_tabs, 3)

        actions = QHBoxLayout()
        update = QPushButton("🔄 Baixar / atualizar todos")
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
        self.log_view.setStyleSheet(
            "QPlainTextEdit{background:#0b0b0b;color:#d7d7d7;font-family:Consolas;font-size:10px;}"
        )
        layout.addWidget(self.log_view, 1)

    def _emulator_group_tab(self, keys: tuple[str, ...]) -> QWidget:
        """Cria a grade de cards para uma aba de categoria."""
        page = QWidget()
        layout = QVBoxLayout(page)
        frame = QFrame()
        grid = QGridLayout(frame)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        for index, key in enumerate(keys):
            card = QFrame()
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            card.setStyleSheet(
                "QFrame{background:#151515;border:1px solid #3d3d3d;border-radius:8px;}"
            )
            box = QVBoxLayout(card)
            name = QLabel(self.LABELS[key])
            name.setWordWrap(True)
            name.setStyleSheet("font-size:15px;font-weight:bold;")
            status = QLabel("● Verificando…")
            version = QLabel("Versão instalada: —")
            path = QLabel("Instalação: —")
            path.setWordWrap(True)
            progress = QProgressBar()
            progress.hide()
            install_progress = QProgressBar()
            install_progress.setFormat("Instalação: %p%")
            install_progress.hide()
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
            for widget in (name, status, version, path, progress, install_progress):
                box.addWidget(widget)
            box.addLayout(row)
            self.cards[key] = (status, version, path, progress, install_progress, install)
            grid.addWidget(card, index // 2, index % 2)
        cards_scroll = QScrollArea()
        cards_scroll.setWidgetResizable(True)
        cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        cards_scroll.setWidget(frame)
        layout.addWidget(cards_scroll, 1)
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
            ("⬇ Baixar / atualizar Stable", lambda: self.install_retroarch("stable")),
            ("⬇ Baixar / atualizar Nightly", lambda: self.install_retroarch("nightly")),
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
        self.retro_progress.setObjectName("retroCoreProgress")
        self.retro_progress.setFormat("Core atual: %p%")
        self.retro_progress.hide()
        layout.addWidget(self.retro_progress)
        self.core_queue_progress = QProgressBar()
        self.core_queue_progress.setObjectName("coreQueueProgress")
        self.core_queue_progress.setFormat("Progresso geral dos cores: %p%")
        self.core_queue_progress.hide()
        layout.addWidget(self.core_queue_progress)
        layout.addWidget(QLabel("Log RetroArch"))
        self.retro_log = QPlainTextEdit()
        self.retro_log.setReadOnly(True)
        self.retro_log.setMaximumBlockCount(3000)
        self.retro_log.setStyleSheet(
            "QPlainTextEdit{background:#071007;color:#8ee28e;font-family:Consolas;font-size:10px;}"
        )
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
        self._refresh_retro_channel_controls()
        self._refresh_emulator_cards()
        self.seven_zip.setText(f"7-Zip: {self.manager.find_7zip() or 'não encontrado'}")
        self._refresh_retroarch()

    def _refresh_retro_channel_controls(self) -> None:
        if not hasattr(self, "retro_stable"):
            return
        self.retro_stable.blockSignals(True)
        self.retro_nightly.blockSignals(True)
        self.retro_stable.setChecked(self._retro_channel == "stable")
        self.retro_nightly.setChecked(self._retro_channel == "nightly")
        self.retro_stable.blockSignals(False)
        self.retro_nightly.blockSignals(False)

    def _refresh_emulator_cards(self) -> None:
        for key, status in self.manager.discover().items():
            card = self.cards[key]
            stored_version = self.manager.roots.get(f"{key}_version")
            version = status.version or (str(stored_version) if stored_version else None)
            text, color = {
                "ready": ("● Pronto", "#55d66b"),
                "configured": ("● Diretório configurado; executável ausente", "#e5c454"),
            }.get(status.state, ("● Não configurado", "#999"))
            card[0].setText(text)
            card[0].setStyleSheet(f"color:{color};font-weight:bold;")
            if key == "fbneo" and version and str(version).casefold() == "latest":
                version = None
            version_label = "Versão do FBNeo" if key == "fbneo" else "Versão instalada"
            card[1].setText(f"{version_label}: {version or 'não detectada'}")
            card[2].setText(f"Instalação: {status.root or 'não configurada'}")
            card[5].setEnabled(self.worker is None)

    def _refresh_retroarch(self) -> None:
        executable, root, cores = self.retroarch.discover()
        version = self.retroarch.detect_version(executable)
        self.retro_status.setText("● Pronto" if executable else "● Não configurado")
        self.retro_status.setStyleSheet(
            "color:#55d66b;font-weight:bold;" if executable else "color:#e5c454;font-weight:bold;"
        )
        self.retro_path.setText(f"Instalação: {root or 'não configurada'}")
        self.retro_version.setText(f"Versão instalada: {version or 'não detectada'}")
        self.retro_cores.setText(f"Cores: {cores or 'não configurado'}")

    def configure(self, key: str) -> None:
        """Seleciona somente o diretório de instalação do emulador."""
        selected = QFileDialog.getExistingDirectory(
            self, f"Diretório do {self.LABELS[key]}", str(Path.home())
        )
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
            selected = QFileDialog.getExistingDirectory(
                self, f"Instalar {self.LABELS[key]} em", str(Path.home())
            )
            if not selected:
                return
            destination = Path(selected).resolve()
            paths = self._load_paths()
            paths[key] = destination
            self._save_paths(paths)
            self.manager.roots = paths
        self._start(
            lambda progress, install_progress, log: self.manager.install(
                key, destination, progress=progress, install_progress=install_progress, log=log
            ),
            key,
        )

    def update_all(self) -> None:
        """Atualiza em sequência os emuladores configurados, inclusive após falhas."""
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
            self._append_log(
                f"ATUALIZAR TODOS | iniciando {self.LABELS[key]} | destino={destination}"
            )
            self._start(
                lambda progress, install_progress, log, k=key, d=destination: self.manager.install(
                    k, d, progress=progress, install_progress=install_progress, log=log
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
        install_bar = self.cards[key][4]
        install_bar.setRange(0, 100)
        install_bar.setValue(0)
        install_bar.setFormat("Instalação: %p%")
        install_bar.show()
        self.worker = _Worker(operation, self)
        self.worker.progress.connect(
            lambda received, total, k=key: self._progress(k, received, total)
        )
        self.worker.install_progress.connect(
            lambda completed, total, k=key: self._installation_progress(k, completed, total)
        )
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

    def _installation_progress(self, key: str, completed: int, total: int) -> None:
        """Atualiza a barra separada de extração e cópia para o destino."""
        bar = self.cards[key][4]
        bar.show()
        bar.setRange(0, 100 if total else 0)
        if total:
            bar.setValue(min(100, int(completed * 100 / total)))

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
        """Persiste diretório, executável, versão e pacote confirmado pelo release."""
        paths = self._load_paths()
        executable = Path(result.executable).resolve()
        version = str(result.version).strip() or "unknown"
        archive = str(result.archive).strip()
        paths[key] = executable.parent
        paths[f"{key}_exe"] = executable
        paths[f"{key}_version"] = Path(version)
        paths[f"{key}_archive"] = Path(archive)
        self._save_paths(paths)
        self._persist_version_marker(executable, version, archive)
        self._append_log(
            f"SUCESSO | {self.LABELS[key]} | versão={version} | pacote={archive} | exe={executable}"
        )
        self.cards[key][4].setValue(100)
        self.refresh()

    def _error(self, key: str, message: str) -> None:
        """Registra erro sem interromper uma atualização em lote."""
        self._append_log(f"ERRO | {self.LABELS[key]} | {message}")
        self.cards[key][4].setFormat("Instalação: falhou")

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
        window = cast("MainWindow", self.window())
        navigation = getattr(window, "navigation", None)
        configuration = getattr(window, "configuration_page", None)
        directories = getattr(configuration, "directories_page", None)
        page_stack = getattr(window, "page_stack", None)
        if navigation is None or directories is None or page_stack is None:
            self._append_log("ERRO | Não foi possível localizar a página central de Diretórios")
            return
        if configuration is not None:
            configuration.navigation_list.setCurrentRow(0)
        navigation.setCurrentRow(window.pages.index(configuration))
        return

    def configure_retroarch(self) -> None:
        """Seleciona e persiste a instalação do RetroArch."""
        selected = QFileDialog.getExistingDirectory(
            self, "Diretório do RetroArch", str(Path.home())
        )
        if not selected:
            return
        paths = self._load_paths()
        paths["retroarch"] = Path(selected).resolve()
        self._save_paths(paths)
        self.refresh()

    def install_retroarch(self, channel: str | None = None) -> None:
        """Instala/atualiza o frontend RetroArch Stable ou Nightly."""
        channel = (channel or self._retro_channel).casefold()
        if channel not in {"stable", "nightly"}:
            raise ValueError(f"Canal RetroArch inválido: {channel!r}")
        if self.worker is not None:
            self._append_retro_log("AVISO | já existe uma operação do RetroArch em execução.")
            return
        destination = self.manager.roots.get("retroarch")
        if not destination:
            selected = QFileDialog.getExistingDirectory(
                self, f"Instalar RetroArch {channel.title()} em", str(Path.home())
            )
            if not selected:
                return
            destination = Path(selected).resolve()
        paths = self._load_paths()
        paths["retroarch"] = Path(destination).resolve()
        paths["retroarch_channel"] = Path(channel)
        self._save_paths(paths)
        self.manager.roots = paths
        self.retroarch = RetroArchManager(Path(destination))
        self._retro_channel = channel
        self._append_retro_log(
            f"DOWNLOAD | RetroArch | canal={channel} | destino={Path(destination).resolve()}"
        )
        self._start_retro(
            lambda progress, log, c=channel, d=Path(destination): self.retroarch.install_frontend(
                d, channel=c, progress=progress, log=log
            )
        )

    def refresh_cores(self) -> None:
        """Atualiza o índice oficial e mostra cores instalados, novos e CRC."""
        try:
            cores = self.retroarch.list_cores(self._retro_channel)
            _, _, destination = self.retroarch.discover()
            installed = self.retroarch.installed_cores(destination) if destination else ()
            comparisons = (
                self.retroarch.compare_installed_cores(cores, destination)
                if destination and destination.is_dir()
                else []
            )
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
                if state == "current":
                    marker = "[ATUALIZADO]"
                elif state == "update":
                    marker = "[ATUALIZAÇÃO]"
                else:
                    marker = "[NOVO]"
                item = QListWidgetItem(
                    f"{marker} {core.core_name} | {core.date} | CRC {core.crc32}"
                )
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setData(Qt.ItemDataRole.UserRole, core.filename)
                item.setData(Qt.ItemDataRole.UserRole + 1, state)
                self.core_list.addItem(item)
                self.core_items[core.filename] = item
            self.core_list.blockSignals(False)
            new_count = len(cores) - installed_count
            self.core_summary.setText(
                f"{len(cores)} publicados  •  {installed_count} instalados  •  {update_count} atualizações  •  {new_count} novos"
            )
            self._update_core_summary()
            self._append_retro_log(
                f"CATÁLOGO | canal={self._retro_channel} | cores={len(cores)} | instalados={installed_count} | atualizações={update_count} | novos={new_count}"
            )
        except Exception as exc:  # noqa: BLE001
            self._append_retro_log(f"ERRO CORES | {type(exc).__name__}: {exc}")
            QMessageBox.warning(self, "RetroArch", str(exc))

    def verify_core_updates(self) -> None:
        """Compara CRC dos cores instalados e seleciona somente os desatualizados."""
        try:
            _, _, destination = self.retroarch.discover()
            if destination is None or not destination.is_dir():
                self._append_retro_log(
                    "AVISO | diretório de cores do RetroArch não configurado ou inexistente."
                )
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
            self.core_summary.setText(
                f"{updates} atualizações disponíveis  •  {current} atualizados  • {unknown} sem correspondência"
            )
            self._update_core_summary()
            self._append_retro_log(
                f"ATUALIZAÇÕES | instalados={len(comparisons)} | atualizações={updates} | atualizados={current} | sem correspondência={unknown}"
            )
            if not updates:
                self._append_retro_log(
                    "ATUALIZAÇÕES | nenhum core instalado necessita de atualização."
                )
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

    def install_selected_cores(self) -> None:
        """Instala somente os cores marcados no catálogo atual."""
        if self.worker is not None:
            self._append_retro_log("AVISO | já existe uma operação do RetroArch em execução.")
            return

        selected = []
        for i in range(self.core_list.count()):
            item = self.core_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                filename = item.data(Qt.ItemDataRole.UserRole)
                if filename:
                    selected.append(str(filename))

        if not selected:
            self._append_retro_log("AVISO | nenhuma core selecionada para instalação.")
            return

        _, _, destination = self.retroarch.discover()
        if destination is None or not destination.is_dir():
            self._append_retro_log(
                "AVISO | diretório de cores do RetroArch não configurado ou inexistente."
            )
            return

        def install_all(progress, log):
            for filename in selected:
                self.retroarch.install_core(
                    filename, destination, channel=self._retro_channel, progress=progress, log=log
                )
            return f"{len(selected)} cores instalados em {destination}"

        self._append_retro_log(
            f"INSTALAÇÃO | iniciando {len(selected)} core(s) selecionado(s) no canal={self._retro_channel}"
        )
        self._start_retro(install_all)

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
        if self._core_total_count:
            current = min(100, int(received * 100 / total)) if total else 0
            progress = self._core_completed_count + current / 100
            overall = int(progress * 100 / self._core_total_count)
            self.core_queue_progress.setValue(min(100, overall))

    def _retro_done(self, result) -> None:
        """Registra sucesso da operação RetroArch e persiste a instalação."""
        executable = getattr(result, "executable", None)
        version = getattr(result, "version", None)
        archive = getattr(result, "archive", None)
        if executable and version:
            executable_path = Path(executable).resolve()
            paths = self._load_paths()
            paths["retroarch"] = executable_path.parent
            paths["retroarch_exe"] = executable_path
            paths["retroarch_version"] = Path(str(version))
            if archive:
                paths["retroarch_archive"] = Path(str(archive))
            self._save_paths(paths)
            self._persist_version_marker(executable_path, str(version), str(archive or ""))
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
