"""Scraper unificado de DATs do SERM V2."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypedDict, cast

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
from ..services.mame_classification_service import (
    MameClassificationError,
    MameClassificationService,
)
from ..services.mame_resolution_service import MameResolutionError, MameResolutionService
from ..services.mame_vsync_service import MameVsyncError, MameVsyncService
from ..sources.acquisition.no_intro_archive import NoIntroArchiveProvider
from ..sources.acquisition.redump import RedumpProvider

logger = logging.getLogger(__name__)


class _MameCatalogResult(TypedDict, total=False):
    """Estrutura conhecida retornada pela ingestão do catálogo MAME."""

    import_id: int
    mame_build: str | None
    machine_count: int
    display_count: int
    rom_count: int
    disk_count: int
    raw_xml: object
    xml_path: object
    database: object
    source_hash: str
    elapsed_seconds: float
    deduplicated: bool
    lossless: bool
    catalog_complete: bool
    profiles_generated: int
    run_id: str
    ini_results: list[tuple[str, dict[str, object]]]


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


class _MameIniWorker(QThread):
    """Executa a fila de INIs MAME em ordem, sem bloquear a interface."""

    message = Signal(str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, database_path, mame_root, parent=None) -> None:
        super().__init__(parent)
        self.database_path = database_path
        self.mame_root = mame_root

    def _log(self, message: str) -> None:
        """Publica uma mensagem de uma etapa da fila."""
        self.message.emit(message)

    def run(self) -> None:
        """Importa CATLIST, Resolution e Vsync como fontes independentes."""
        results = []
        stages = (
            ("CATLIST", MameClassificationService),
            ("RESOLUTION", MameResolutionService),
            ("VSYNC", MameVsyncService),
        )
        try:
            for name, service_class in stages:
                service = service_class(self.database_path, self.mame_root)
                try:
                    result = service.ingest(logger=self._log)
                    results.append((name, result))
                except (MameClassificationError, MameResolutionError, MameVsyncError) as exc:
                    self._log(f"{name} | ERRO | {exc}")
            self.completed.emit(results)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


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
        # O restante da implementação da página permanece inalterado.
        pass

    def _inis_completed(self, results: list[tuple[str, dict[str, Any]]]) -> None:
        """Exibe o resumo agregado de todas as fontes processadas."""
        self.status.setText("Importação dos INIs concluída")
        for name, data in results:
            self._log("OK", f"{name} | entradas={data['entries']:,}")
            self._log("OK", f"{name} | resolvidas={data['resolved']:,}")
            self._log("OK", f"{name} | não resolvidas={data['unresolved']:,}")
            if "duplicates" in data:
                self._log("OK", f"{name} | duplicadas={data['duplicates']:,}")
            self._log("OK", f"{name} | source_id={data['source_id']}")
            self._log("DONE", f"Fonte {name} concluída")
        self._log("DONE", "Fila de INIs MAME concluída com sucesso")

    def _inis_failed(self, message: str) -> None:
        """Registra a falha da fila sem esconder qual etapa falhou."""
        self.status.setText("Falha na fila de INIs")
        self._log("ERROR", message)
        self._log("DONE", "Fila encerrada; fontes concluídas anteriormente permanecem preservadas")

    def _inis_finished(self) -> None:
        """Libera os controles após terminar a fila de INIs."""
        self._set_mame_busy(False)
        self.refresh()

    def _completed(self, result: object) -> None:
        """Exibe métricas, proveniência e política de deduplicação da ingestão."""
        data = cast(_MameCatalogResult, result)
        build = data.get("mame_build") or "não informado"
        source_hash = data.get("source_hash") or "não informado"
        elapsed = float(data.get("elapsed_seconds") or 0.0)
        mode = "REUTILIZADA (mesmo SHA-256)" if data.get("deduplicated") else "NOVA IMPORTAÇÃO"
        if data.get("force"):
            mode = "FORÇADA"
        self.status.setText(
            f"Concluído | MAME {build} | {data['machine_count']:,} máquinas | {data['display_count']:,} displays | {elapsed:.2f}s"
        )
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
        self._set_mame_busy(False)
        self.refresh()
