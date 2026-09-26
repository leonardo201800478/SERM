"""RetroBIOS scan and reconstruction controls for configured emulators."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
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

from ..runtime.paths import data_root
from ..services.ares_firmware_service import (
    AresFirmwareEntry,
    AresFirmwareMatch,
    AresFirmwareScan,
    AresFirmwareService,
)
from ..services.reconstruction_service import (
    ReconstructionError,
    ReconstructionPlan,
    ReconstructionService,
)
from ..services.retrobios_pack_service import RetroBiosPackService
from .directory_dialogs import get_existing_directory


class _RetroBiosWorker(QThread):
    progress = Signal(int, int)
    catalog_ready = Signal(object)
    scanned = Signal(object)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        operation: str,
        emulator: str,
        *,
        source: Path | None = None,
        catalog: tuple[str, tuple[AresFirmwareEntry, ...]] | None = None,
        plan: ReconstructionPlan | None = None,
        destination: Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.operation = operation
        self.emulator = emulator
        self.source = source
        self.catalog = catalog
        self.plan = plan
        self.destination = destination
        self.cancel_requested = False

    def run(self) -> None:
        try:
            if self.operation == "catalog":
                self.catalog_ready.emit(
                    AresFirmwareService.load_catalog(emulator=self.emulator, refresh=True)
                )
            elif self.operation == "scan" and self.source is not None:
                catalog = self.catalog or AresFirmwareService.load_catalog(emulator=self.emulator)
                version, entries = catalog
                scan = AresFirmwareService.scan(
                    self.source,
                    entries,
                    catalog_version=version,
                    emulator=self.emulator,
                    progress_callback=self.progress.emit,
                    cancel_callback=lambda: self.cancel_requested,
                )
                self.scanned.emit((catalog, scan))
            elif self.operation == "reconstruct" and self.plan is not None:
                result = ReconstructionService.execute(
                    self.plan,
                    progress_callback=lambda done, total: self.progress.emit(done, total),
                    cancel_callback=lambda: self.cancel_requested,
                )
                if self.destination is not None and self.catalog is not None:
                    _version, entries = self.catalog
                    removed = AresFirmwareService.clean_invalid_files(
                        self.destination, entries
                    )
                    result["invalid_removed"] = len(removed)
                self.completed.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def cancel(self) -> None:
        self.cancel_requested = True


class RetroBiosFirmwarePanel(QWidget):
    """Scan one configured emulator directory and reconstruct its RetroBIOS files."""

    PATHS_FILE = data_root() / "emulator_paths.json"

    def _source_key(self) -> str:
        return f"retro_bios_{self.emulator}_source"

    def _destination_key(self) -> str:
        return f"retro_bios_{self.emulator}_destination"

    def _save_paths(self) -> None:
        data: dict[str, object] = {}
        try:
            value = json.loads(self.PATHS_FILE.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                data = value
        except (OSError, ValueError, TypeError):
            pass
        if self._source is not None:
            data[self._source_key()] = str(self._source)
        if self._destination is not None:
            data[self._destination_key()] = str(self._destination)
        self.PATHS_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.PATHS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def __init__(self, emulator: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.emulator = emulator.casefold()
        self.label = label
        self._catalog: tuple[str, tuple[AresFirmwareEntry, ...]] | None = None
        self._scan: AresFirmwareScan | None = None
        self._matches: dict[str, AresFirmwareMatch] = {}
        self._plan: ReconstructionPlan | None = None
        self._worker: _RetroBiosWorker | None = None
        self._source: Path | None = None
        self._destination: Path | None = None
        self._source_selected = False
        self._destination_selected = False
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        intro = QLabel(
            "Compara o diretório configurado com o perfil RetroBIOS deste emulador; "
            "somente arquivos com checksum compatível podem ser reconstruídos."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        paths = QWidget()
        form = QFormLayout(paths)
        self.source_label = QLabel("Diretório não configurado")
        self.source_label.setWordWrap(True)
        source_row = QHBoxLayout()
        source_row.addWidget(self.source_label, 1)
        choose_source = QPushButton("Fonte alternativa…")
        choose_source.setToolTip("Usa uma pasta externa em vez do diretório local dos packs RetroBIOS.")
        choose_source.clicked.connect(self._choose_source)
        source_row.addWidget(choose_source)
        use_packs = QPushButton("Usar packs")
        use_packs.setToolTip("Restaura o diretório configurado em Ferramentas > Packs de BIOS RetroBIOS.")
        use_packs.clicked.connect(self._use_retrobios_packs)
        source_row.addWidget(use_packs)
        form.addRow("Fonte de aquisição:", source_row)

        self.destination_label = QLabel("Selecione o diretório de firmware do emulador")
        self.destination_label.setWordWrap(True)
        destination_row = QHBoxLayout()
        destination_row.addWidget(self.destination_label, 1)
        choose_destination = QPushButton("Destino…")
        choose_destination.setToolTip(
            "Escolhe a pasta de saída. Arquivos fora dos nomes do catálogo serão preservados."
        )
        choose_destination.clicked.connect(self._choose_destination)
        destination_row.addWidget(choose_destination)
        form.addRow("Reconstrução:", destination_row)
        root.addWidget(paths)

        actions = QHBoxLayout()
        self.catalog_button = QPushButton("ATUALIZAR RETROBIOS")
        self.catalog_button.clicked.connect(self.update_catalog)
        self.scan_button = QPushButton("ESCANEAR RETROBIOS")
        self.scan_button.clicked.connect(self.scan)
        self.reconstruct_button = QPushButton("RECONSTRUIR SELECIONADOS")
        self.reconstruct_button.setEnabled(False)
        self.reconstruct_button.clicked.connect(self.reconstruct)
        self.cancel_button = QPushButton("CANCELAR")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel)
        self.export_missing_button = QPushButton("EXPORTAR AUSENTES (.TXT)")
        self.export_missing_button.clicked.connect(self.export_missing_report)
        self.export_missing_button.setEnabled(False)
        actions.addWidget(self.catalog_button)
        actions.addWidget(self.scan_button)
        actions.addWidget(self.reconstruct_button)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.export_missing_button)
        actions.addStretch()
        root.addLayout(actions)

        self.catalog_status = QLabel("Catálogo RetroBIOS ainda não carregado")
        self.catalog_status.setWordWrap(True)
        root.addWidget(self.catalog_status)
        self.items = QListWidget()
        self.items.setMinimumHeight(110)
        root.addWidget(self.items)
        self.summary = QLabel("Execute o scan para listar arquivos verificados, ausentes e sem hash.")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        root.addWidget(self.progress)
        self.status = QLabel("Pronto.")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

    def refresh(self) -> None:
        paths: dict[str, object] = {}
        try:
            value = json.loads(self.PATHS_FILE.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                paths = value
        except (OSError, ValueError, TypeError):
            pass
        configured = paths.get(self.emulator)
        configured_source = paths.get(self._source_key())
        configured_destination = paths.get(self._destination_key())
        if (
            not self._source_selected
            and isinstance(configured_source, str)
            and configured_source.strip()
        ):
            self._source = Path(configured_source).expanduser()
        elif not self._source_selected and isinstance(configured, str) and configured.strip():
            self._source = Path(configured).expanduser()
        elif not self._source_selected:
            self._source = RetroBiosPackService.storage_directory()
        if (
            not self._destination_selected
            and isinstance(configured_destination, str)
            and configured_destination.strip()
        ):
            self._destination = Path(configured_destination).expanduser()
        elif not self._destination_selected and isinstance(configured, str) and configured.strip():
            self._destination = Path(configured).expanduser()
        elif (
            not self._destination_selected
            and self._source is not None
            and self._source.resolve() != RetroBiosPackService.storage_directory().resolve()
        ):
            self._destination = self._source
        if self._source and self._source.resolve() == RetroBiosPackService.storage_directory().resolve():
            self.source_label.setText(f"{self._source} (packs RetroBIOS — fonte padrão)")
        else:
            self.source_label.setText(str(self._source) if self._source else "Diretório não configurado")
        self.destination_label.setText(
            str(self._destination) if self._destination else "Selecione o diretório de firmware do emulador"
        )

    def _choose_source(self) -> None:
        selected = get_existing_directory(
            self,
            f"Selecionar origem de firmware do {self.label}",
            str(self._source) if self._source and self._source.is_dir() else str(Path.home()),
        )
        if selected:
            self._source = Path(selected).expanduser().resolve()
            self._source_selected = True
            if not self._destination_selected:
                self._destination = self._source
            self._save_paths()
            self._clear_scan()
            self.refresh()

    def _use_retrobios_packs(self) -> None:
        self._source = RetroBiosPackService.storage_directory()
        self._source_selected = False
        self._remove_saved_source()
        self._clear_scan()
        self.refresh()

    def _remove_saved_source(self) -> None:
        data: dict[str, object] = {}
        try:
            value = json.loads(self.PATHS_FILE.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                data = value
        except (OSError, ValueError, TypeError):
            pass
        data.pop(self._source_key(), None)
        self.PATHS_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.PATHS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def _choose_destination(self) -> None:
        selected = get_existing_directory(
            self,
            f"Selecionar destino de firmware do {self.label}",
            str(self._destination)
            if self._destination and self._destination.is_dir()
            else str(Path.home()),
        )
        if selected:
            self._destination = Path(selected).expanduser().resolve()
            self._destination_selected = True
            self._save_paths()
            self._plan = None
            self.reconstruct_button.setEnabled(bool(self._scan and self._matches))
            self.refresh()

    def scan(self) -> None:
        if self._worker is not None:
            return
        self.refresh()
        if self._source is None or not self._source.is_dir():
            QMessageBox.information(
                self,
                f"Firmware {self.label}",
                "Configure um diretório de instalação ou selecione uma origem válida.",
            )
            return
        self._clear_scan()
        self.status.setText(f"Carregando RetroBIOS e examinando {self._source}…")
        self._start_worker(
            _RetroBiosWorker(
                "scan", self.emulator, source=self._source, parent=self
            )
        )

    def update_catalog(self) -> None:
        if self._worker is not None:
            return
        self.status.setText(f"Atualizando o perfil RetroBIOS de {self.label}…")
        self._start_worker(_RetroBiosWorker("catalog", self.emulator, parent=self))

    def reconstruct(self) -> None:
        if self._scan is None or self._catalog is None or self._worker is not None:
            return
        if self._destination is None:
            QMessageBox.information(
                self, f"Firmware {self.label}", "Selecione o diretório de destino."
            )
            return
        selected = tuple(
            match
            for key, match in self._matches.items()
            if self._is_checked(key)
        )
        if not selected:
            QMessageBox.information(
                self,
                f"Firmware {self.label}",
                "Marque pelo menos um arquivo verificado para reconstruir.",
            )
            return
        try:
            filter_path = AresFirmwareService.write_filter_file(self._scan, selected)
            self._plan = ReconstructionService.plan(filter_path, self._destination)
        except (OSError, ReconstructionError) as exc:
            QMessageBox.warning(self, f"Firmware {self.label}", str(exc))
            return

        answer = QMessageBox.question(
            self,
            f"Reconstruir firmware {self.label}",
            f"Reconstruir {len(selected):,} arquivo(s) em:\n{self._destination}?\n\n"
            "Arquivos não identificados pelo catálogo serão preservados; arquivos com nomes do catálogo "
            "e hashes inválidos poderão ser removidos.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.status.setText(f"Reconstruindo firmware em {self._destination}…")
        self._start_worker(
            _RetroBiosWorker(
                "reconstruct",
                self.emulator,
                catalog=self._catalog,
                plan=self._plan,
                destination=self._destination,
                parent=self,
            )
        )

    def _start_worker(self, worker: _RetroBiosWorker) -> None:
        self._worker = worker
        worker.progress.connect(self._progress)
        worker.catalog_ready.connect(self._catalog_loaded)
        worker.scanned.connect(self._scan_finished)
        worker.completed.connect(self._reconstruction_finished)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._worker_finished)
        self.catalog_button.setEnabled(False)
        self.scan_button.setEnabled(False)
        self.reconstruct_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setValue(0)
        worker.start()

    def _catalog_loaded(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            self._failed("Resposta RetroBIOS inválida.")
            return
        version, entries = payload
        self._catalog = (str(version), tuple(entries))
        required = sum(entry.required for entry in self._catalog[1])
        optional = len(self._catalog[1]) - required
        verifiable = sum(entry.is_verifiable for entry in self._catalog[1])
        available = sum(entry.catalog_available for entry in self._catalog[1])
        self.catalog_status.setText(
            f"RetroBIOS {version} | {len(self._catalog[1]):,} arquivo(s) | "
            f"obrigatórios={required:,} | opcionais={optional:,} | "
            f"com checksum={verifiable:,} | disponíveis no acervo={available:,}"
        )
        self._populate_catalog_preview()
        self._clear_scan(preserve_catalog=True)
        self.status.setText(
            f"Perfil RetroBIOS de {self.label} atualizado: "
            f"{required:,} obrigatório(s) e {optional:,} opcional(is)."
        )

    def _scan_finished(self, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            self._failed("Resposta RetroBIOS inválida.")
            return
        catalog, scan = payload
        self._catalog = (str(catalog[0]), tuple(catalog[1]))
        self._scan = scan
        self._matches = {match.entry.key: match for match in scan.matches}
        self.items.clear()
        state_counts = {
            "VALIDADO": 0,
            "PRESENTE — HASH NÃO VERIFICÁVEL": 0,
            "AUSENTE — DISPONÍVEL": 0,
            "AUSENTE — NÃO DISPONÍVEL": 0,
            "HLE / OPCIONAL": 0,
        }
        for entry in self._catalog[1]:
            match = self._matches.get(entry.key)
            state = entry.panel_state(match is not None)
            state_detail = entry.panel_state_detail(match is not None)
            if state == "VALIDADO":
                background = Qt.GlobalColor.darkGreen
                foreground = Qt.GlobalColor.white
            elif state == "PRESENTE — HASH NÃO VERIFICÁVEL":
                background = Qt.GlobalColor.darkYellow
                foreground = Qt.GlobalColor.black
            elif state == "AUSENTE — DISPONÍVEL":
                background = Qt.GlobalColor.darkRed
                foreground = Qt.GlobalColor.white
            elif state == "AUSENTE — NÃO DISPONÍVEL":
                background = Qt.GlobalColor.black
                foreground = Qt.GlobalColor.white
            else:
                background = Qt.GlobalColor.darkBlue
                foreground = Qt.GlobalColor.white

            state_counts[state] += 1
            label = (
                f"{state} | {entry.output_path} | {entry.system} | "
                f"{entry.availability_label} | {entry.distribution_label}"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole + 1, state)
            item.setData(Qt.ItemDataRole.UserRole, entry.key)
            if match:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                item.setToolTip(
                    f"{match.path}"
                    + (f" :: {match.archive_member}" if match.archive_member else "")
                    + f"\n\nEstado: {state}\n{state_detail}"
                )
            else:
                item.setToolTip(
                    f"Estado: {state}\n{state_detail}\n"
                    f"Disponibilidade: {entry.availability_label}\n"
                    f"Distribuição: {entry.distribution_label}\n"
                    f"Cobertura: {entry.coverage_label}\n"
                    f"Lacuna: {entry.gap_reason or 'não informada'}"
                )
            item.setBackground(background)
            item.setForeground(foreground)
            self.items.addItem(item)
        verifiable = sum(entry.is_verifiable for entry in self._catalog[1])
        available = sum(entry.catalog_available for entry in self._catalog[1])
        self.catalog_status.setText(
            f"RetroBIOS {self._catalog[0]} | {len(self._catalog[1]):,} arquivo(s) catalogado(s) | "
            f"{verifiable:,} com identidade verificável | acervo={available:,}"
        )
        required = sum(entry.required for entry in self._catalog[1])
        optional = len(self._catalog[1]) - required
        self.summary.setText(
            f"Examinados={scan.files_examined:,} | "
            f"🟢 validados={state_counts['VALIDADO']:,} | "
            f"🟡 hash não verificável={state_counts['PRESENTE — HASH NÃO VERIFICÁVEL']:,} | "
            f"🔴 ausente/disponível={state_counts['AUSENTE — DISPONÍVEL']:,} | "
            f"⚫ ausente/não disponível={state_counts['AUSENTE — NÃO DISPONÍVEL']:,} | "
            f"🔵 HLE/opcional={state_counts['HLE / OPCIONAL']:,} | "
            f"catálogo: obrigatórios={required:,}, opcionais={optional:,}, sem hash={len(self._catalog[1]) - verifiable:,}"
        )
        self.reconstruct_button.setEnabled(bool(self._matches))
        self.export_missing_button.setEnabled(bool(scan.missing))
        self.status.setText(f"Scan concluído em {scan.source_directory}.")

    def export_missing_report(self) -> None:
        """Exporta BIOS/firmwares ausentes com metadados para pesquisa rápida."""
        if self._scan is None:
            QMessageBox.information(self, f"Firmware {self.label}", "Execute o scan antes de exportar.")
            return
        missing = tuple(self._scan.missing)
        if not missing:
            QMessageBox.information(self, f"Firmware {self.label}", "Nenhuma BIOS/firmware ausente foi encontrada.")
            return
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar BIOS/firmwares ausentes",
            str(Path.home() / f"bios_firmwares_ausentes_{self.emulator}.txt"),
            "Arquivo de texto (*.txt);;Todos os arquivos (*)",
        )
        if not selected:
            return
        output = Path(selected)
        if output.suffix.casefold() != ".txt":
            output = output.with_suffix(".txt")
        lines = [
            "SERM — BIOS / FIRMWARES AUSENTES",
            f"Emulador: {self.label} ({self.emulator})",
            f"Catálogo RetroBIOS: {self._scan.catalog_version}",
            f"Diretório examinado: {self._scan.source_directory}",
            f"Itens ausentes: {len(missing)}",
            "",
            "Pesquisa Google: use o hash como identificador principal quando disponível.",
            "",
        ]
        for index, entry in enumerate(missing, start=1):
            size = str(entry.size) if entry.size is not None else "não informado"
            hashes = []
            for algorithm in ("sha256", "sha1", "md5", "crc32"):
                value = getattr(entry, algorithm)
                if value:
                    hashes.append(f"{algorithm.upper()}={value}")
            hash_text = " | ".join(hashes) if hashes else "não informado"
            query_parts = [entry.name, entry.system]
            if entry.size is not None:
                query_parts.append(f"{entry.size} bytes")
            for value in (entry.sha256, entry.sha1, entry.md5, entry.crc32):
                if value:
                    query_parts.append(value)
                    break
            query = " ".join(f'"{part}"' for part in query_parts if part)
            required = "SIM" if entry.required else "NÃO"
            lines.extend((
                f"{index:03d}. {entry.name}",
                f"    Sistema: {entry.system}",
                f"    Caminho esperado: {entry.output_path or entry.name}",
                f"    Tamanho: {size} bytes",
                f"    Hash: {hash_text}",
                f"    Obrigatório: {required}",
                f"    Descrição: {entry.description or 'não informada'}",
                f"    Pesquisa Google: {query} BIOS firmware ROM",
                "",
            ))
        try:
            output.write_text("\n".join(lines), encoding="utf-8-sig")
        except OSError as exc:
            QMessageBox.warning(self, f"Firmware {self.label}", f"Não foi possível salvar o relatório.\n\n{exc}")
            return
        self.status.setText(f"Relatório de ausentes exportado: {output}")
        QMessageBox.information(self, f"Firmware {self.label}", f"Relatório salvo em:\n{output}")
    def _is_checked(self, key: str) -> bool:
        for index in range(self.items.count()):
            item = self.items.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == key:
                return item.checkState() == Qt.CheckState.Checked
        return False

    def _progress(self, done: int, total: int) -> None:
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(min(done, max(total, 1)))
        self.status.setText(f"Examinando {done:,}/{total:,}…")

    def _reconstruction_finished(self, result: object) -> None:
        created = int(result.get("created_count", 0)) if isinstance(result, dict) else 0
        removed = int(result.get("invalid_removed", 0)) if isinstance(result, dict) else 0
        self.status.setText(
            f"Reconstrução concluída: {created:,} arquivo(s) materializado(s); "
            f"{removed:,} arquivo(s) inválido(s) removido(s)."
        )

    def _failed(self, message: str) -> None:
        self.status.setText(f"Falha: {message}")
        QMessageBox.warning(self, f"Firmware {self.label}", message)

    def _cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.status.setText("Cancelamento solicitado…")

    def cancel(self) -> None:
        self._cancel()

    def _worker_finished(self) -> None:
        self._worker = None
        self.catalog_button.setEnabled(True)
        self.scan_button.setEnabled(True)
        self.reconstruct_button.setEnabled(bool(self._matches))
        self.cancel_button.setEnabled(False)

    def _populate_catalog_preview(self) -> None:
        """Mostra o catálogo com obrigatório/opcional antes do scan local."""
        self.items.clear()
        if self._catalog is None:
            return
        for entry in self._catalog[1]:
            required = "OBRIGATÓRIO" if entry.required else "OPCIONAL"
            hash_state = "com hash" if entry.is_verifiable else "sem hash"
            item = QListWidgetItem(
                f"{required} | {entry.output_path} | {entry.system} | {hash_state} | "
                f"{entry.availability_label} | {entry.coverage_label}"
            )
            item.setData(Qt.ItemDataRole.UserRole, entry.key)
            item.setData(Qt.ItemDataRole.UserRole + 1, "catalog")
            hash_label = "SIM" if entry.is_verifiable else "NÃO"
            item.setToolTip(
                f"Nome: {entry.name}\n"
                f"Destino: {entry.output_path}\n"
                f"Tipo: {required}\n"
                f"Hash verificável: {hash_label}\n"
                f"Disponibilidade: {entry.availability_label}\n"
                f"Distribuição: {entry.distribution_label}\n"
                f"Cobertura: {entry.coverage_label}\n"
                f"Repo path: {entry.repository_path or 'não informado'}\n"
                f"Release asset: {entry.release_asset or 'não informado'}\n"
                f"Lacuna: {entry.gap_reason or 'não informada'}\n"
                f"Descrição: {entry.description or 'não informada'}"
            )
            if entry.required:
                item.setBackground(Qt.GlobalColor.darkRed)
                item.setForeground(Qt.GlobalColor.white)
            else:
                item.setBackground(Qt.GlobalColor.darkYellow)
                item.setForeground(Qt.GlobalColor.black)
            self.items.addItem(item)

    def _clear_scan(self, *, preserve_catalog: bool = False) -> None:
        self._scan = None
        self._matches.clear()
        if preserve_catalog:
            self._populate_catalog_preview()
        else:
            self.items.clear()
        self._plan = None
        self.reconstruct_button.setEnabled(False)
        self.export_missing_button.setEnabled(False)


__all__ = ["RetroBiosFirmwarePanel"]
