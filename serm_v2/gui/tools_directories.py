"""Executáveis auxiliares usados pelo SERM V2."""

from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..integrations.launchbox import LaunchBoxIntegration
from ..runtime.paths import integrations_root
from ..services.emulator_manager import EmulatorManager
from ..services.retrobios_pack_service import (
    RetroBiosPack,
    RetroBiosPackError,
    RetroBiosPackService,
)


class _RetroBiosPackWorker(QThread):
    listed = Signal(object)
    progress = Signal(int, int)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: str, pack: RetroBiosPack | None = None, destination: Path | None = None, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.pack = pack
        self.destination = destination
        self.cancel_requested = False

    def run(self) -> None:
        try:
            if self.operation == "list":
                self.listed.emit(RetroBiosPackService.list_available())
            elif self.operation == "download" and self.pack is not None:
                target = RetroBiosPackService.download_and_extract(
                    self.pack,
                    destination=self.destination,
                    progress_callback=self.progress.emit,
                    cancel_callback=lambda: self.cancel_requested,
                )
                self.completed.emit(target)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def cancel(self) -> None:
        self.cancel_requested = True


class ToolsDirectoriesPage(QWidget):
    """Centraliza somente executáveis externos auxiliares do SERM."""

    CONFIG_PATH = integrations_root() / "tools.json"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.launchbox = LaunchBoxIntegration()
        self._pack_worker: _RetroBiosPackWorker | None = None
        self._packs: tuple[RetroBiosPack, ...] = ()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        intro = QLabel("Ferramentas auxiliares")
        intro.setProperty("role", "title")
        layout.addWidget(intro)
        hint = QLabel(
            "Aponte aqui executáveis externos que o SERM utiliza para tarefas de apoio. "
            "Pastas dos emuladores permanecem em Diretórios."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        group = QGroupBox("LaunchBox")
        form = QFormLayout(group)
        form.setContentsMargins(10, 8, 10, 9)
        form.setVerticalSpacing(6)
        form.setHorizontalSpacing(10)
        self.launchbox_edit = QLineEdit()
        self.launchbox_edit.setReadOnly(True)
        browse = QPushButton("Selecionar .exe")
        browse.setMaximumWidth(130)
        browse.clicked.connect(self.select_launchbox)
        launch = QPushButton("Abrir")
        launch.setMaximumWidth(90)
        launch.clicked.connect(self.launch_launchbox)
        row = QHBoxLayout()
        row.setSpacing(5)
        row.addWidget(self.launchbox_edit, 1)
        row.addWidget(browse, 0)
        row.addWidget(launch, 0)
        form.addRow("Executável:", row)
        self.launchbox_status = QLabel()
        form.addRow("Status:", self.launchbox_status)
        layout.addWidget(group)

        group7 = QGroupBox("7-Zip")
        form7 = QFormLayout(group7)
        form7.setContentsMargins(10, 8, 10, 9)
        form7.setVerticalSpacing(6)
        form7.setHorizontalSpacing(10)
        self.sevenzip_edit = QLineEdit()
        self.sevenzip_edit.setReadOnly(True)
        browse7 = QPushButton("Selecionar .exe")
        browse7.setMaximumWidth(130)
        browse7.clicked.connect(self.select_7zip)
        row7 = QHBoxLayout()
        row7.setSpacing(5)
        row7.addWidget(self.sevenzip_edit, 1)
        row7.addWidget(browse7, 0)
        form7.addRow("Executável:", row7)
        self.sevenzip_status = QLabel()
        form7.addRow("Status:", self.sevenzip_status)
        layout.addWidget(group7)

        pack_group = QGroupBox("Packs de BIOS RetroBIOS")
        pack_form = QFormLayout(pack_group)
        pack_form.setContentsMargins(10, 8, 10, 9)
        pack_form.setVerticalSpacing(6)
        pack_form.setHorizontalSpacing(10)

        self.retrobios_directory_edit = QLineEdit()
        self.retrobios_directory_edit.setReadOnly(True)
        choose_pack_dir = QPushButton("Selecionar…")
        choose_pack_dir.setMaximumWidth(100)
        choose_pack_dir.clicked.connect(self.select_retrobios_directory)
        open_pack_dir = QPushButton("Abrir")
        open_pack_dir.setMaximumWidth(75)
        open_pack_dir.clicked.connect(self.open_retrobios_directory)
        pack_dir_row = QHBoxLayout()
        pack_dir_row.setSpacing(5)
        pack_dir_row.addWidget(self.retrobios_directory_edit, 1)
        pack_dir_row.addWidget(choose_pack_dir)
        pack_dir_row.addWidget(open_pack_dir)
        pack_form.addRow("Diretório base:", pack_dir_row)

        self.retrobios_pack_combo = QComboBox()
        self.retrobios_pack_combo.setMinimumWidth(280)
        refresh_packs = QPushButton("Atualizar lista")
        refresh_packs.setMaximumWidth(105)
        refresh_packs.clicked.connect(self.refresh_retrobios_packs)
        download_pack = QPushButton("Baixar e extrair")
        download_pack.setMaximumWidth(125)
        download_pack.clicked.connect(self.download_retrobios_pack)
        pack_row = QHBoxLayout()
        pack_row.setSpacing(5)
        pack_row.addWidget(self.retrobios_pack_combo, 1)
        pack_row.addWidget(refresh_packs)
        pack_row.addWidget(download_pack)
        pack_form.addRow("Pack disponível:", pack_row)

        self.retrobios_pack_status = QLabel("Lista de packs ainda não carregada.")
        self.retrobios_pack_status.setWordWrap(True)
        pack_form.addRow("Status:", self.retrobios_pack_status)
        self.retrobios_pack_progress = QProgressBar()
        self.retrobios_pack_progress.setRange(0, 1)
        self.retrobios_pack_progress.setValue(0)
        pack_form.addRow("Progresso:", self.retrobios_pack_progress)
        layout.addWidget(pack_group)

        actions = QHBoxLayout()
        actions.setSpacing(5)
        refresh = QPushButton("Redetectar")
        refresh.setMaximumWidth(110)
        refresh.clicked.connect(self.refresh)
        save = QPushButton("Salvar")
        save.setMaximumWidth(100)
        save.clicked.connect(self.save)
        actions.addWidget(refresh)
        actions.addWidget(save)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addStretch()
        self.setStyleSheet(
            "QPushButton{min-height:25px;padding:3px 10px;} "
            "QLineEdit{min-height:25px;padding:2px 7px;} "
            "QGroupBox{margin-top:8px;padding-top:8px;}"
        )

    def _load_tools(self) -> dict:
        if not self.CONFIG_PATH.is_file():
            return {}
        try:
            data = json.loads(self.CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return data if isinstance(data, dict) else {}

    def refresh(self) -> None:
        configured = self._load_tools()
        pack_directory = configured.get("retrobios_packs_directory")
        pack_path = (
            Path(str(pack_directory)).expanduser().resolve()
            if isinstance(pack_directory, str) and pack_directory.strip()
            else RetroBiosPackService.default_directory().resolve()
        )
        pack_path.mkdir(parents=True, exist_ok=True)
        self.retrobios_directory_edit.setText(str(pack_path))
        launchbox = self.launchbox.discover()
        launchbox_path = str(launchbox or configured.get("launchbox") or "")
        self.launchbox_edit.setText(launchbox_path)
        found = bool(launchbox_path) and Path(launchbox_path).is_file()
        self.launchbox_status.setText("● Encontrado" if found else "● Não encontrado")
        sevenzip = configured.get("sevenzip")
        detected = (
            Path(sevenzip)
            if sevenzip and Path(sevenzip).is_file()
            else EmulatorManager.find_7zip()
        )
        self.sevenzip_edit.setText(str(detected or ""))
        self.sevenzip_status.setText(
            "● Encontrado" if detected and Path(detected).is_file() else "● Não encontrado"
        )

    def select_launchbox(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar LaunchBox.exe",
            self._initial_launchbox_directory(),
            "LaunchBox (LaunchBox.exe);;Executáveis (*.exe)",
        )
        if not path:
            return
        try:
            self.launchbox.set_executable(Path(path))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "LaunchBox", str(exc))
            return
        self.refresh()

    def _initial_launchbox_directory(self) -> str:
        executable = self.launchbox.executable
        if executable is not None and executable.parent.is_dir():
            return str(executable.parent)
        configured = self._load_tools().get("launchbox")
        if configured and Path(str(configured)).parent.is_dir():
            return str(Path(str(configured)).parent)
        return str(Path.home())

    def launch_launchbox(self) -> None:
        try:
            self.launchbox.launch()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "LaunchBox", str(exc))

    def select_retrobios_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Selecionar diretório dos packs RetroBIOS",
            self.retrobios_directory_edit.text() or str(Path.home()),
        )
        if not path:
            return
        self.retrobios_directory_edit.setText(str(Path(path).expanduser().resolve()))
        self.save()

    def open_retrobios_directory(self) -> None:
        directory = Path(self.retrobios_directory_edit.text()).expanduser()
        try:
            directory.mkdir(parents=True, exist_ok=True)
            if hasattr(os, "startfile"):
                os.startfile(directory)  # type: ignore[attr-defined]
            else:
                raise OSError("A abertura automática da pasta não é suportada neste sistema.")
        except OSError as exc:
            QMessageBox.warning(self, "Packs RetroBIOS", str(exc))

    def refresh_retrobios_packs(self) -> None:
        if self._pack_worker is not None:
            return
        self.retrobios_pack_status.setText("Consultando a release oficial do RetroBIOS…")
        self._set_pack_controls(False)
        self._pack_worker = _RetroBiosPackWorker("list", parent=self)
        self._pack_worker.listed.connect(self._retrobios_packs_loaded)
        self._pack_worker.failed.connect(self._retrobios_pack_failed)
        self._pack_worker.finished.connect(self._retrobios_pack_worker_finished)
        self._pack_worker.start()

    def _retrobios_packs_loaded(self, payload: object) -> None:
        packs = tuple(payload) if isinstance(payload, tuple) else ()
        self._packs = tuple(pack for pack in packs if isinstance(pack, RetroBiosPack))
        self.retrobios_pack_combo.clear()
        for pack in self._packs:
            size_gb = pack.size / (1024 ** 3)
            suffix = f"{size_gb:.2f} GiB" if size_gb >= 1 else f"{pack.size / (1024 ** 2):.0f} MiB"
            self.retrobios_pack_combo.addItem(
                f"{pack.platform} — {suffix}{' — multipart' if pack.multipart else ''}"
            )
        self.retrobios_pack_status.setText(
            f"{len(self._packs)} pack(s) disponível(is) na release oficial do RetroBIOS."
            if self._packs
            else "Nenhum pack de BIOS foi encontrado na release atual."
        )

    def download_retrobios_pack(self) -> None:
        if self._pack_worker is not None:
            return
        index = self.retrobios_pack_combo.currentIndex()
        if index < 0 or index >= len(self._packs):
            QMessageBox.information(self, "Packs RetroBIOS", "Atualize a lista e selecione um pack.")
            return
        pack = self._packs[index]
        destination = Path(self.retrobios_directory_edit.text()).expanduser().resolve()
        answer = QMessageBox.question(
            self,
            "Baixar pack RetroBIOS",
            f"Baixar e extrair o pack {pack.platform} em:\n{destination}?\n\n"
            "O SERM valida o SHA-256 de cada volume antes da extração.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        destination.mkdir(parents=True, exist_ok=True)
        self.retrobios_pack_progress.setRange(0, max(pack.size, 1))
        self.retrobios_pack_progress.setValue(0)
        self.retrobios_pack_status.setText(f"Baixando {pack.platform}…")
        self._set_pack_controls(False)
        self._pack_worker = _RetroBiosPackWorker(
            "download", pack=pack, destination=destination, parent=self
        )
        self._pack_worker.progress.connect(self._retrobios_pack_progress)
        self._pack_worker.completed.connect(self._retrobios_pack_completed)
        self._pack_worker.failed.connect(self._retrobios_pack_failed)
        self._pack_worker.finished.connect(self._retrobios_pack_worker_finished)
        self._pack_worker.start()

    def _retrobios_pack_progress(self, done: int, total: int) -> None:
        self.retrobios_pack_progress.setMaximum(max(total, 1))
        self.retrobios_pack_progress.setValue(min(done, max(total, 1)))

    def _retrobios_pack_completed(self, payload: object) -> None:
        self.retrobios_pack_status.setText(
            f"Pack extraído em {payload}. Ele passa a ser a fonte padrão dos scans RetroBIOS."
        )
        self.retrobios_pack_progress.setValue(self.retrobios_pack_progress.maximum())

    def _retrobios_pack_failed(self, message: str) -> None:
        self.retrobios_pack_status.setText(f"Falha: {message}")
        QMessageBox.warning(self, "Packs RetroBIOS", message)

    def _retrobios_pack_worker_finished(self) -> None:
        self._pack_worker = None
        self._set_pack_controls(True)

    def _set_pack_controls(self, enabled: bool) -> None:
        self.retrobios_pack_combo.setEnabled(enabled)
        self.retrobios_pack_progress.setEnabled(enabled)
        self.retrobios_pack_progress.setEnabled(True)

    def select_7zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar 7z.exe",
            str(Path.home()),
            "7-Zip (7z.exe);;Executáveis (*.exe)",
        )
        if path:
            self.sevenzip_edit.setText(path)
            self.save()

    def save(self) -> None:
        payload = self._load_tools()
        payload["launchbox"] = self.launchbox_edit.text().strip() or None
        payload["sevenzip"] = self.sevenzip_edit.text().strip() or None
        payload["retrobios_packs_directory"] = (
            self.retrobios_directory_edit.text().strip()
            or str(RetroBiosPackService.default_directory())
        )
        self.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.CONFIG_PATH.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.refresh()


__all__ = ["ToolsDirectoriesPage"]
