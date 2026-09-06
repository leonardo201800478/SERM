"""Fase 3: reconstrução de um arquivo filtrado em um destino escolhido."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..runtime.paths import scans_root
from ..services.reconstruction_service import (
    ReconstructionError,
    ReconstructionPlan,
    ReconstructionService,
)

_RECONSTRUCTION_TITLE = "Reconstrução"


class _ReconstructionWorker(QThread):
    progress = Signal(int, int)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, plan: ReconstructionPlan, parent=None) -> None:
        super().__init__(parent)
        self.plan = plan
        self.cancel_requested = False

    def run(self) -> None:
        try:
            result = ReconstructionService.execute(
                self.plan,
                progress_callback=self.progress.emit,
                cancel_callback=lambda: self.cancel_requested,
            )
            self.completed.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")

    def cancel(self) -> None:
        self.cancel_requested = True


class ReconstructionPage(QWidget):
    """Consome exclusivamente SERM-FILTER-V1 e monta o set físico."""

    def __init__(self, source_label: str = "MAME", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.source_label = QLabel(f"Fonte: {source_label}")
        self._filter_path: Path | None = None
        self._destination: Path | None = None
        self._plan: ReconstructionPlan | None = None
        self._worker: _ReconstructionWorker | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("RECONSTRUÇÃO — MONTAGEM DO SET")
        title.setProperty("role", "title")
        layout.addWidget(title)
        description = QLabel(
            "Entrada: arquivo filtrado. A reconstrução não consulta o DAT e não executa novo scan. "
            "Os itens selecionados são materializados no diretório de destino informado pelo usuário."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        context = QGroupBox("1. Arquivo filtrado")
        form = QFormLayout(context)
        form.addRow("Fonte:", self.source_label)
        self.filter_label = QLabel("Nenhum arquivo filtrado selecionado.")
        self.filter_label.setWordWrap(True)
        form.addRow("Entrada:", self.filter_label)
        choose = QPushButton("SELECIONAR ARQUIVO FILTRADO…")
        choose.clicked.connect(self.choose_filter)
        form.addRow("Arquivo:", choose)
        layout.addWidget(context)

        destination = QGroupBox("2. Diretório de destino")
        dest_layout = QHBoxLayout(destination)
        self.destination_label = QLabel("Nenhum destino selecionado.")
        self.destination_label.setWordWrap(True)
        dest_layout.addWidget(self.destination_label, 1)
        choose_dest = QPushButton("ESCOLHER DESTINO…")
        choose_dest.clicked.connect(self.choose_destination)
        dest_layout.addWidget(choose_dest)
        layout.addWidget(destination)

        plan_box = QGroupBox("3. Plano")
        plan_layout = QVBoxLayout(plan_box)
        self.summary = QLabel("Selecione o arquivo filtrado e o destino para gerar o plano.")
        self.summary.setWordWrap(True)
        plan_layout.addWidget(self.summary)
        self.plan_list = QListWidget()
        self.plan_list.setMinimumHeight(120)
        plan_layout.addWidget(self.plan_list)
        actions = QHBoxLayout()
        self.plan_button = QPushButton("GERAR PLANO")
        self.plan_button.clicked.connect(self.generate_plan)
        self.execute_button = QPushButton("EXECUTAR RECONSTRUÇÃO")
        self.execute_button.setEnabled(False)
        self.execute_button.clicked.connect(self.execute)
        self.cancel_button = QPushButton("CANCELAR")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel)
        actions.addWidget(self.plan_button)
        actions.addWidget(self.execute_button)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        plan_layout.addLayout(actions)
        layout.addWidget(plan_box, 1)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.status = QLabel("Pronto.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def refresh(self) -> None:
        # A lista é deliberadamente limitada aos arquivos FILTER gerados pela fase 2.
        # Não há descoberta de ROMs nem execução de scan nesta fase.
        self._refresh_latest_filter_hint()

    def _refresh_latest_filter_hint(self) -> None:
        root = scans_root() / "filtered"
        files = (
            sorted(root.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if root.is_dir()
            else []
        )
        if files:
            self.status.setText(f"Último arquivo filtrado encontrado: {files[0]}")

    def choose_filter(self) -> None:
        root = scans_root() / "filtered"
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar arquivo filtrado", str(root), "SERM Filter (*.json);;JSON (*.json)"
        )
        if not path:
            return
        try:
            payload = ReconstructionService.load_filter(path)
        except ReconstructionError as exc:
            QMessageBox.warning(self, _RECONSTRUCTION_TITLE, str(exc))
            return
        self._filter_path = Path(path).resolve()
        self.filter_label.setText(str(self._filter_path))
        self.source_label.setText(
            f"Fonte: {payload.get('source', '—')} › {payload.get('system', '—')}"
        )
        self.summary.setText(
            f"Filtro {payload.get('filter_run_id', '—')} | scan {payload.get('scan_id', '—')} | "
            f"catálogo {payload.get('catalog_label', '—')} | itens selecionados: {len(payload.get('evidence', [])):,}"
        )
        self._plan = None
        self.execute_button.setEnabled(False)
        self.plan_list.clear()
        self.status.setText("Arquivo filtrado validado. Escolha o destino e gere o plano.")

    def choose_destination(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Selecionar diretório de destino")
        if not path:
            return
        self._destination = Path(path).resolve()
        self.destination_label.setText(str(self._destination))
        self._plan = None
        self.execute_button.setEnabled(False)

    def generate_plan(self) -> None:
        if self._filter_path is None:
            QMessageBox.information(
                self, _RECONSTRUCTION_TITLE, "Selecione um arquivo filtrado primeiro."
            )
            return
        if self._destination is None:
            QMessageBox.information(
                self, _RECONSTRUCTION_TITLE, "Escolha o diretório de destino primeiro."
            )
            return
        try:
            self._plan = ReconstructionService.plan(self._filter_path, self._destination)
        except ReconstructionError as exc:
            QMessageBox.warning(self, _RECONSTRUCTION_TITLE, str(exc))
            return
        self.plan_list.clear()
        for item in self._plan.items[:500]:
            member = f" :: {item.archive_member}" if item.archive_member else ""
            self.plan_list.addItem(f"{item.kind.upper()} | {item.output_path}{member}")
        if len(self._plan.items) > 500:
            self.plan_list.addItem(f"… e mais {len(self._plan.items) - 500:,} itens")
        self.summary.setText(
            f"Plano pronto | itens={self._plan.item_count:,} | arquivos de origem={self._plan.archive_count:,} | "
            f"soltos={self._plan.loose_count:,} | CHD={self._plan.chd_count:,} | destino={self._plan.destination}"
        )
        self.execute_button.setEnabled(True)
        self.status.setText("Plano validado. A execução somente escreverá no destino escolhido.")

    def execute(self) -> None:
        if self._plan is None or (self._worker and self._worker.isRunning()):
            return
        answer = QMessageBox.question(
            self,
            "Confirmar reconstrução",
            f"Montar {self._plan.item_count:,} itens em:\n{self._plan.destination}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._worker = _ReconstructionWorker(self._plan, self)
        self._worker.progress.connect(self._progress)
        self._worker.completed.connect(self._completed)
        self._worker.failed.connect(self._failed)
        self._worker.finished.connect(self._finished)
        self.plan_button.setEnabled(False)
        self.execute_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setMaximum(max(1, self._plan.archive_count + self._plan.loose_count))
        self.progress.setValue(0)
        self.status.setText("Reconstrução em execução…")
        self._worker.start()

    def _progress(self, done: int, total: int) -> None:
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(done)
        self.status.setText(f"Reconstruindo {done:,}/{total:,} unidades…")

    def _completed(self, result: object) -> None:
        self.progress.setValue(self.progress.maximum())
        if isinstance(result, dict):
            self.status.setText(
                f"RECONSTRUÇÃO CONCLUÍDA | arquivos criados={int(result.get('created_count', 0)):,} | "
                f"destino={result.get('destination', '—')}"
            )
        else:
            self.status.setText("RECONSTRUÇÃO CONCLUÍDA")
        self.refresh()

    def _failed(self, message: str) -> None:
        self.status.setText(f"Falha na reconstrução: {message}")

    def _finished(self) -> None:
        self.plan_button.setEnabled(True)
        self.execute_button.setEnabled(self._plan is not None)
        self.cancel_button.setEnabled(False)

    def cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.status.setText("Cancelamento solicitado…")


__all__ = ["ReconstructionPage"]
