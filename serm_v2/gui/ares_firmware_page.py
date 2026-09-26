"""Scan and reconstruct ares firmware from the user's local collection."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..services.ares_firmware_service import (
    AresFirmwareEntry,
    AresFirmwareError,
    AresFirmwareMatch,
    AresFirmwareScan,
    AresFirmwareService,
)
from ..services.reconstruction_service import (
    ReconstructionError,
    ReconstructionPlan,
    ReconstructionService,
)
from .ares_directories_page import AresDirectoriesPage
from .directory_dialogs import get_existing_directory


class _AresFirmwareWorker(QThread):
    progress = Signal(int, int)
    catalog_ready = Signal(object)
    scanned = Signal(object)
    reconstructed = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: str, *, source="", catalog=None, plan=None, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.source = source
        self.catalog = catalog
        self.plan = plan
        self.cancel_requested = False

    def run(self) -> None:
        try:
            if self.operation == "catalog":
                self.catalog_ready.emit(AresFirmwareService.load_catalog(refresh=True))
            elif self.operation == "scan":
                catalog = self.catalog or AresFirmwareService.load_catalog()
                version, entries = catalog
                result = AresFirmwareService.scan(
                    self.source,
                    entries,
                    catalog_version=version,
                    progress_callback=self.progress.emit,
                    cancel_callback=lambda: self.cancel_requested,
                )
                self.scanned.emit((catalog, result))
            elif self.operation == "reconstruct" and self.plan is not None:
                result = ReconstructionService.execute(
                    self.plan,
                    progress_callback=self.progress.emit,
                    cancel_callback=lambda: self.cancel_requested,
                )
                if self.catalog is not None:
                    _version, entries = self.catalog
                    removed = AresFirmwareService.clean_invalid_files(
                        self.plan.destination, entries
                    )
                    result["invalid_removed"] = len(removed)
                    result["removed_paths"] = tuple(str(path) for path in removed)
                self.reconstructed.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def cancel(self) -> None:
        self.cancel_requested = True


class AresFirmwarePage(QWidget):
    """Hash-audit local ares firmware and rebuild selected files by expected name."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._catalog: tuple[str, tuple[AresFirmwareEntry, ...]] | None = None
        self._scan: AresFirmwareScan | None = None
        self._matches: dict[str, AresFirmwareMatch] = {}
        self._plan: ReconstructionPlan | None = None
        self._worker: _AresFirmwareWorker | None = None
        self._build_ui()
        self._load_configured_firmware_path()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        intro = QLabel(
            "Audite os arquivos locais do ares por SHA-256 e reconstrua os firmwares "
            "selecionados com os nomes esperados. O SERM não baixa arquivos de firmware."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        locations = QWidget()
        form = QFormLayout(locations)
        self.source = QLabel("Pasta de firmware não configurada")
        self.source.setWordWrap(True)
        source_row = QHBoxLayout()
        source_row.addWidget(self.source, 1)
        choose_source = QPushButton("Pasta de origem…")
        choose_source.setToolTip(
            "Escolhe a pasta local de firmware que será examinada por SHA-256."
        )
        choose_source.clicked.connect(self._choose_source)
        source_row.addWidget(choose_source)
        form.addRow("Origem do scan:", source_row)

        self.destination = QLabel("Pasta de destino não selecionada")
        self.destination.setWordWrap(True)
        destination_row = QHBoxLayout()
        destination_row.addWidget(self.destination, 1)
        choose_destination = QPushButton("Destino…")
        choose_destination.setToolTip(
            "Escolhe onde os firmwares selecionados serão reconstruídos. Ao final, "
            "arquivos com nomes do catálogo e hashes inválidos serão removidos."
        )
        choose_destination.clicked.connect(self._choose_destination)
        destination_row.addWidget(choose_destination)
        form.addRow("Destino da reconstrução:", destination_row)
        root.addWidget(locations)

        actions = QHBoxLayout()
        self.catalog_button = QPushButton("Atualizar catálogo RetroBIOS")
        self.catalog_button.setToolTip(
            "Baixa os metadados atuais do perfil ares e os armazena em cache; não baixa firmware."
        )
        self.catalog_button.clicked.connect(self._refresh_catalog)
        self.scan_button = QPushButton("Escanear firmware local")
        self.scan_button.setToolTip(
            "Calcula SHA-256 dos arquivos da origem, incluindo membros ZIP, e compara com o catálogo."
        )
        self.scan_button.setProperty("role", "primary")
        self.scan_button.clicked.connect(self._scan_local)
        self.plan_button = QPushButton("Gerar plano")
        self.plan_button.setToolTip(
            "Prepara a reconstrução dos itens encontrados que estiverem marcados na lista."
        )
        self.plan_button.clicked.connect(self._generate_plan)
        self.execute_button = QPushButton("Reconstruir selecionados")
        self.execute_button.setToolTip(
            "Extrai/copia os itens selecionados para o destino e remove arquivos inválidos "
            "com nomes reconhecidos pelo catálogo."
        )
        self.execute_button.clicked.connect(self._execute_plan)
        self.execute_button.setEnabled(False)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setToolTip("Solicita o cancelamento da operação em andamento.")
        self.cancel_button.clicked.connect(self._cancel)
        self.cancel_button.setEnabled(False)
        self.export_missing_button = QPushButton("Exportar não validados (.txt)")
        self.export_missing_button.setToolTip(
            "Lê o settings.bml do ares e exporta somente BIOS/firmwares sem arquivo "
            "válido atribuído pelo próprio emulador."
        )
        self.export_missing_button.clicked.connect(self._export_missing)
        self.export_missing_button.setEnabled(True)
        for button in (
            self.catalog_button,
            self.scan_button,
            self.plan_button,
            self.execute_button,
            self.cancel_button,
            self.export_missing_button,
        ):
            actions.addWidget(button)
        root.addLayout(actions)

        self.catalog_status = QLabel("Catálogo não carregado")
        root.addWidget(self.catalog_status)
        self.items = QListWidget()
        self.items.setMinimumHeight(160)
        root.addWidget(self.items, 1)
        self.summary = QLabel("Escaneie a pasta para listar firmwares encontrados e ausentes.")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        root.addWidget(self.progress)
        self.status = QLabel("Pronto.")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

    @staticmethod
    def _configured_firmware_path() -> Path | None:
        editor = AresDirectoriesPage.editor()
        if editor is None:
            return None
        values = editor.values("Paths.Firmware")
        raw = values[0].strip().strip('"') if values else ""
        return Path(raw).expanduser() if raw else None

    def _load_configured_firmware_path(self) -> None:
        old_source = self.source.text()
        if not old_source.startswith("Pasta de firmware não configurada"):
            return
        path = self._configured_firmware_path()
        if path is not None:
            self.source.setText(str(path))
            if (
                self.destination.text().startswith("Pasta de destino")
                or self.destination.text() == old_source
            ):
                self.destination.setText(str(path))

    def _choose_source(self) -> None:
        current = self.source.text()
        selected = get_existing_directory(
            self, "Selecionar pasta de firmware do ares", current if Path(current).is_dir() else ""
        )
        if selected:
            self.source.setText(str(Path(selected).resolve()))
            if self.destination.text().startswith("Pasta de destino"):
                self.destination.setText(str(Path(selected).resolve()))
            self._clear_scan()

    def _choose_destination(self) -> None:
        current = self.destination.text()
        selected = get_existing_directory(
            self, "Selecionar destino da reconstrução", current if Path(current).is_dir() else ""
        )
        if selected:
            self.destination.setText(str(Path(selected).resolve()))
            self._invalidate_plan()

    def _refresh_catalog(self) -> None:
        if self._worker is not None:
            return
        self._start_worker(_AresFirmwareWorker("catalog", parent=self))
        self.status.setText("Atualizando metadados do perfil ares no RetroBIOS…")

    def _scan_local(self) -> None:
        if self._worker is not None:
            return
        self._load_configured_firmware_path()
        source = Path(self.source.text()).expanduser()
        if not source.is_dir():
            QMessageBox.information(
                self,
                "Firmware ares",
                "Selecione uma pasta de origem válida ou configure Paths.Firmware no settings.bml.",
            )
            return
        self._clear_scan()
        worker = _AresFirmwareWorker("scan", source=str(source), catalog=self._catalog, parent=self)
        self._start_worker(worker)
        self.status.setText("Calculando SHA-256 dos arquivos locais…")

    def _generate_plan(self) -> None:
        if self._scan is None:
            QMessageBox.information(self, "Firmware ares", "Execute o scan antes de gerar o plano.")
            return
        destination = Path(self.destination.text()).expanduser().resolve()
        selected = tuple(
            match
            for name, match in self._matches.items()
            if self._is_checked(name)
        )
        if not selected:
            QMessageBox.information(
                self, "Firmware ares", "Marque ao menos um firmware encontrado para reconstruir."
            )
            return
        try:
            filter_path = AresFirmwareService.write_filter_file(self._scan, selected)
            self._plan = ReconstructionService.plan(filter_path, destination)
        except (OSError, ReconstructionError) as exc:
            QMessageBox.warning(self, "Firmware ares", str(exc))
            return
        self.execute_button.setEnabled(True)
        self.summary.setText(
            f"Plano pronto | encontrados selecionados={self._plan.item_count:,} | "
            f"arquivos de saída={self._plan.loose_count:,} | destino={destination}"
        )
        self.status.setText("Plano gerado pelo serviço de reconstrução do SERM.")

    def _execute_plan(self) -> None:
        if self._plan is None or self._worker is not None:
            return
        answer = QMessageBox.question(
            self,
            "Reconstruir firmware ares",
            f"Gravar {self._plan.item_count:,} arquivo(s) em:\n{self._plan.destination}?\n\n"
            "Após reconstruir, serão removidos desse destino os arquivos cujo nome conste "
            "no catálogo e cujo SHA-256 não corresponda a nenhuma versão catalogada. "
            "Arquivos com nomes desconhecidos serão preservados.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._start_worker(
            _AresFirmwareWorker(
                "reconstruct", plan=self._plan, catalog=self._catalog, parent=self
            )
        )
        self.status.setText("Reconstruindo os firmwares selecionados…")

    def _start_worker(self, worker: _AresFirmwareWorker) -> None:
        self._worker = worker
        worker.progress.connect(self._progress)
        worker.catalog_ready.connect(self._catalog_loaded)
        worker.scanned.connect(self._scan_finished)
        worker.reconstructed.connect(self._reconstruction_finished)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._worker_finished)
        self._set_busy(True)
        worker.start()

    def _catalog_loaded(self, result: object) -> None:
        if not isinstance(result, tuple) or len(result) != 2:
            self._failed("Formato de catálogo ares inválido.")
            return
        self._catalog = (str(result[0]), tuple(result[1]))
        self.catalog_status.setText(
            f"RetroBIOS ares {self._catalog[0]} | {len(self._catalog[1])} arquivos | "
            f"{sum(bool(entry.sha256) for entry in self._catalog[1])} com SHA-256"
        )
        self.status.setText("Catálogo atualizado e armazenado para uso offline.")

    def _scan_finished(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            self._failed("Resultado do scan ares inválido.")
            return
        catalog, result = payload
        self._catalog = catalog
        self._scan = result
        self._matches = {match.entry.name.casefold(): match for match in result.matches}
        self.items.clear()
        for entry in catalog[1]:
            name = entry.name.casefold()
            match = self._matches.get(name)
            if match:
                label = f"ENCONTRADO | {entry.name} | {entry.system} | SHA-256 verificado"
            elif not entry.sha256:
                label = f"SEM HASH | {entry.name} | {entry.system} | não verificável por conteúdo"
            else:
                label = f"AUSENTE | {entry.name} | {entry.system} | {'obrigatório' if entry.required else 'opcional'}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, name)
            if match:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                if match.archive_member:
                    item.setToolTip(f"{match.path} :: {match.archive_member}")
                else:
                    item.setToolTip(match.path)
            self.items.addItem(item)
        verifiable_missing = [entry for entry in result.missing if entry.sha256]
        required_missing = sum(entry.required for entry in verifiable_missing)
        optional_missing = len(verifiable_missing) - required_missing
        unhashed = sum(not entry.sha256 for entry in result.missing)
        self.summary.setText(
            f"Arquivos examinados={result.files_examined:,} | encontrados={len(result.matches):,} | "
            f"obrigatórios ausentes={required_missing:,} | opcionais ausentes={optional_missing:,} | "
            f"sem hash verificável={unhashed:,}"
        )
        self.catalog_status.setText(
            f"RetroBIOS ares {result.catalog_version} | {len(catalog[1])} arquivos catalogados | "
            f"{sum(bool(entry.sha256) for entry in catalog[1])} com hash"
        )
        self.export_missing_button.setEnabled(True)
        self._invalidate_plan()
        self.status.setText(f"Scan concluído em {result.source_directory}.")

    def _is_checked(self, name: str) -> bool:
        for index in range(self.items.count()):
            item = self.items.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == name:
                return item.checkState() == Qt.CheckState.Checked
        return False

    def _invalidate_plan(self) -> None:
        self._plan = None
        self.execute_button.setEnabled(False)

    def _clear_scan(self) -> None:
        self._scan = None
        self._matches.clear()
        self.items.clear()
        self._invalidate_plan()

    def _export_missing(self) -> None:
        editor = AresDirectoriesPage.editor()
        if editor is None:
            QMessageBox.warning(
                self,
                "Firmware ares",
                "Configure a instalação do ares em Diretórios para localizar o settings.bml.",
            )
            return
        try:
            missing = AresFirmwareService.read_unassigned_firmware(editor.path)
        except (AresFirmwareError, OSError) as exc:
            QMessageBox.warning(self, "Firmware ares", str(exc))
            return
        if not missing:
            QMessageBox.information(
                self,
                "Firmware ares",
                "O settings.bml indica que o ares tem um arquivo existente atribuído a cada firmware.",
            )
            return
        default_path = editor.path.parent / "ares_firmwares_nao_validados.txt"
        selected, _file_type = QFileDialog.getSaveFileName(
            self,
            "Exportar BIOS/firmwares não validados pelo ares",
            str(default_path),
            "Arquivo de texto (*.txt)",
        )
        if not selected:
            return
        output = Path(selected)
        if output.suffix.casefold() != ".txt":
            output = output.with_suffix(".txt")
        lines = [
            "BIOS/firmwares não validados pelo ares",
            f"settings.bml: {editor.path}",
            f"Itens sem arquivo existente atribuído: {len(missing)}",
            "",
            "Os termos de pesquisa abaixo usam o sistema, tipo e região exibidos pelo ares.",
            "",
        ]
        for index, entry in enumerate(missing, start=1):
            identity = f"{entry.firmware_type} {entry.region}".strip()
            lines.extend(
                (
                    f"{index}. {entry.emulator} | {identity}",
                    f"   Caminho atribuído: {entry.location or '(unset)'}",
                    f'   Pesquisa Google: ares "{entry.emulator}" "{identity}" BIOS firmware ROM',
                    "",
                )
            )
        try:
            output.write_text("\n".join(lines), encoding="utf-8-sig")
        except OSError as exc:
            QMessageBox.warning(self, "Firmware ares", f"Não foi possível salvar o arquivo.\n\n{exc}")
            return
        self.status.setText(f"Lista de BIOS/firmwares não validados exportada: {output}")

    def _progress(self, done: int, total: int) -> None:
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(done)
        self.status.setText(f"Processando {done:,}/{total:,}…")

    def _reconstruction_finished(self, result: object) -> None:
        created = result.get("created_count", 0) if isinstance(result, dict) else 0
        removed = result.get("invalid_removed", 0) if isinstance(result, dict) else 0
        self.status.setText(
            f"Reconstrução concluída: {created:,} arquivo(s) criado(s); "
            f"{removed:,} firmware(s) inválido(s) removido(s)."
        )

    def _failed(self, message: str) -> None:
        self.status.setText(f"Falha: {message}")

    def _cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.status.setText("Cancelamento solicitado…")

    def _worker_finished(self) -> None:
        self._worker = None
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        for button in (self.catalog_button, self.scan_button, self.plan_button):
            button.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        if not busy:
            self.execute_button.setEnabled(self._plan is not None)


__all__ = ["AresFirmwarePage"]
