"""Persistência normalizada das instalações e configurações dos emuladores.

Este módulo é a fronteira entre a descoberta e o banco. Ele não executa
emuladores, não gera configurações e não modifica arquivos do usuário.
Recebe somente os resultados produzidos pelo ``EmulatorDiscoveryService``.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime, timezone

from app.core.services.emulator_discovery_service import EmulatorInstallation
from app.database.database import Database

logger = logging.getLogger(__name__)


class EmulatorPersistenceService:
    """Persiste estado de descoberta de forma idempotente."""

    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()

    def ensure_schema(self) -> None:
        """Cria as tabelas específicas da descoberta sem alterar dados MAME."""
        self.database.connect()
        self.database.executescript(
            """
            CREATE TABLE IF NOT EXISTS emulator_installation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emulator TEXT NOT NULL UNIQUE,
                executable_path TEXT,
                root_path TEXT,
                version TEXT,
                detected_at TEXT NOT NULL,
                last_status TEXT NOT NULL DEFAULT 'unknown'
            );

            CREATE TABLE IF NOT EXISTS emulator_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                installation_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                status TEXT NOT NULL,
                generated INTEGER NOT NULL DEFAULT 0,
                backup_path TEXT,
                checked_at TEXT NOT NULL,
                UNIQUE(installation_id, name),
                FOREIGN KEY(installation_id)
                    REFERENCES emulator_installation(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_emulator_config_installation
                ON emulator_config(installation_id);
            """
        )
        self.database.conn.commit()  # type: ignore[union-attr]

    def persist(self, installations: Iterable[EmulatorInstallation]) -> int:
        """Grava uma descoberta completa e retorna o número de emuladores.

        A operação é um único lote transacional: se uma gravação falhar,
        nenhuma instalação parcialmente atualizada fica visível no banco.
        """
        self.ensure_schema()
        conn = self.database.conn
        if conn is None:
            raise RuntimeError("Banco não conectado.")

        now = datetime.now(timezone.utc).isoformat()
        rows = list(installations)

        try:
            conn.execute("BEGIN")
            for item in rows:
                statuses = [cfg.status for cfg in item.configs]
                status = self._installation_status(item, statuses)

                conn.execute(
                    """
                    INSERT INTO emulator_installation
                        (emulator, executable_path, root_path, version,
                         detected_at, last_status)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(emulator) DO UPDATE SET
                        executable_path=excluded.executable_path,
                        root_path=excluded.root_path,
                        version=excluded.version,
                        detected_at=excluded.detected_at,
                        last_status=excluded.last_status
                    """ ,
                    (
                        item.emulator,
                        str(item.executable) if item.executable else None,
                        str(item.root) if item.root else None,
                        item.version,
                        now,
                        status,
                    ),
                )

                installation = conn.execute(
                    "SELECT id FROM emulator_installation WHERE emulator = ?",
                    (item.emulator,),
                ).fetchone()
                if installation is None:
                    raise RuntimeError(
                        f"Instalação não encontrada após upsert: {item.emulator}"
                    )
                installation_id = int(installation[0])

                for config in item.configs:
                    conn.execute(
                        """
                        INSERT INTO emulator_config
                            (installation_id, name, path, status, generated,
                             backup_path, checked_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(installation_id, name) DO UPDATE SET
                            path=excluded.path,
                            status=excluded.status,
                            generated=excluded.generated,
                            backup_path=excluded.backup_path,
                            checked_at=excluded.checked_at
                        """,
                        (
                            installation_id,
                            config.name,
                            str(config.path),
                            config.status,
                            int(config.generated),
                            str(config.backup) if config.backup else None,
                            now,
                        ),
                    )

            conn.commit()
            logger.info("Descoberta persistida: %d emulador(es).", len(rows))
            return len(rows)
        except Exception:
            conn.rollback()
            logger.exception("Falha ao persistir descoberta dos emuladores.")
            raise

    @staticmethod
    def _installation_status(
        installation: EmulatorInstallation,
        statuses: list[str],
    ) -> str:
        """Calcula o estado agregado sem ocultar problemas de configuração."""
        if installation.executable is None:
            return "not_found"
        if any(status == "error" for status in statuses):
            return "error"
        if any(status.startswith("corrupt") for status in statuses):
            return "configuration_corrupt"
        if any(status.startswith("missing") for status in statuses):
            return "configuration_missing"
        if any(status.startswith("generated") for status in statuses):
            return "ready_generated"
        return "ready"
