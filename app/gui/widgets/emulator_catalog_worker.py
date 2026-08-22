"""Worker Qt para geração/publicação de catálogos multi-emulador."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.core.services.emulator_catalog_build_service import (
    CatalogBuildContext,
    EmulatorCatalogBuildService,
)
from app.core.services.emulator_catalog_repository import EmulatorCatalogRepository
from app.core.services.emulator_catalog_service import EmulatorCatalogService
from app.database.database import Database

logger = logging.getLogger(__name__)


class EmulatorCatalogWorker(QObject):
    """Executa a geração dos catálogos fora da thread principal da GUI.

    A conexão SQLite da janela principal nunca é compartilhada com esta
    thread. O worker recebe somente o caminho do banco e cria sua própria
    instância ``Database`` dentro da thread que irá utilizá-la.
    """

    progress = Signal(int, int)
    log_message = Signal(str)
    catalog_finished = Signal(str, int, int, str)
    failed = Signal(str, str)
    finished = Signal()

    def __init__(self, database, context: CatalogBuildContext, emulator: str) -> None:
        super().__init__()
        self.db_path = Path(database.db_path)
        self.context = context
        self.emulator = emulator

    @Slot()
    def run(self) -> None:
        """Gera um catálogo e publica o resultado no SQLite."""
        database = None
        try:
            # sqlite3.Connection pertence à thread que a criou. Portanto,
            # jamais reutilizamos ``database.conn`` da MainWindow aqui.
            database = Database(self.db_path)
            database.connect()

            service = EmulatorCatalogService()
            repository = EmulatorCatalogRepository(database)
            builder = EmulatorCatalogBuildService(service, repository)

            self.log_message.emit(
                f"CATÁLOGO | iniciando | emulator={self.emulator} | db={self.db_path}"
            )
            jobs = {
                "mame": lambda: builder.build_mame(self.context),
                "fbneo": lambda: builder.build_fbneo(self.context),
                "supermodel": lambda: builder.build_supermodel(self.context),
                "flycast": lambda: builder.build_flycast(self.context),
            }
            result = jobs[self.emulator]()
            self.catalog_finished.emit(
                result.emulator,
                result.machine_count,
                result.rom_count,
                result.version or "unknown",
            )
            self.log_message.emit(
                f"CATÁLOGO | publicado | emulator={result.emulator} | "
                f"machines={result.machine_count} | roms={result.rom_count} | "
                f"version={result.version or 'unknown'}"
            )
        except Exception as exc:
            logger.exception("Falha na geração do catálogo: %s", self.emulator)
            self.failed.emit(self.emulator, f"{type(exc).__name__}: {exc}")
        finally:
            if database is not None:
                database.close()
            self.finished.emit()


class EmulatorCatalogBatchWorker(QObject):
    """Executa todos os catálogos em sequência, preservando falhas individuais.

    A conexão SQLite é criada dentro da própria thread e fechada ao final.
    """

    log_message = Signal(str)
    catalog_finished = Signal(str, int, int, str)
    failed = Signal(str, str)
    finished = Signal()

    def __init__(self, database, context: CatalogBuildContext) -> None:
        super().__init__()
        self.db_path = Path(database.db_path)
        self.context = context

    @Slot()
    def run(self) -> None:
        """Gera MAME, FBNeo, Supermodel e Flycast em sequência."""
        database = None
        try:
            database = Database(self.db_path)
            database.connect()

            service = EmulatorCatalogService()
            repository = EmulatorCatalogRepository(database)
            builder = EmulatorCatalogBuildService(service, repository)
            for emulator, job in (
                ("mame", lambda: builder.build_mame(self.context)),
                ("fbneo", lambda: builder.build_fbneo(self.context)),
                ("supermodel", lambda: builder.build_supermodel(self.context)),
                ("flycast", lambda: builder.build_flycast(self.context)),
            ):
                self.log_message.emit(f"CATÁLOGO | iniciando | emulator={emulator}")
                try:
                    result = job()
                    self.catalog_finished.emit(
                        result.emulator,
                        result.machine_count,
                        result.rom_count,
                        result.version or "unknown",
                    )
                    self.log_message.emit(
                        f"CATÁLOGO | publicado | emulator={result.emulator} | "
                        f"machines={result.machine_count} | roms={result.rom_count}"
                    )
                except Exception as exc:
                    logger.exception("Falha no catálogo %s", emulator)
                    self.failed.emit(emulator, f"{type(exc).__name__}: {exc}")
        finally:
            if database is not None:
                database.close()
            self.finished.emit()
