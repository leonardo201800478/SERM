"""Persistência dos resultados do Scan ROMs no SQLite.

O repositório mantém o modelo de domínio ``ScanResult`` separado da camada
SQLite. Cada execução recebe um registro de sessão, cada máquina um registro
agregado e cada ROM/CHD um registro individual.

A tabela é criada de forma idempotente para também funcionar com bancos já
existentes enquanto a migração formal do schema é incorporada ao bootstrap do
Database.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.models.scan_result import (
    MachineScanResult,
    RomScanResult,
    ScanItemType,
    ScanResult,
    ScanStatus,
)
from app.database.database import Database


class ScanRepository:
    """Persistir, consultar e reconstruir resultados completos de scans."""

    SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS scan_session (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        xml_path TEXT,
        started_at TEXT,
        finished_at TEXT,
        cancelled INTEGER NOT NULL DEFAULT 0,
        error TEXT,
        machine_count INTEGER NOT NULL DEFAULT 0,
        total INTEGER NOT NULL DEFAULT 0,
        found INTEGER NOT NULL DEFAULT 0,
        valid INTEGER NOT NULL DEFAULT 0,
        missing INTEGER NOT NULL DEFAULT 0,
        invalid INTEGER NOT NULL DEFAULT 0,
        error_count INTEGER NOT NULL DEFAULT 0,
        expected_size INTEGER NOT NULL DEFAULT 0,
        actual_size INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS scan_machine (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id INTEGER NOT NULL,
        machine_name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        cloneof TEXT,
        started INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL,
        total INTEGER NOT NULL DEFAULT 0,
        found INTEGER NOT NULL DEFAULT 0,
        valid INTEGER NOT NULL DEFAULT 0,
        missing INTEGER NOT NULL DEFAULT 0,
        invalid INTEGER NOT NULL DEFAULT 0,
        error_count INTEGER NOT NULL DEFAULT 0,
        expected_size INTEGER NOT NULL DEFAULT 0,
        actual_size INTEGER NOT NULL DEFAULT 0,
        error_message TEXT,
        FOREIGN KEY (scan_id) REFERENCES scan_session(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS scan_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_machine_id INTEGER NOT NULL,
        machine_name TEXT NOT NULL,
        item_name TEXT NOT NULL,
        item_type TEXT NOT NULL,
        status TEXT NOT NULL,
        expected_size INTEGER NOT NULL DEFAULT 0,
        actual_size INTEGER NOT NULL DEFAULT 0,
        expected_crc TEXT,
        actual_crc TEXT,
        expected_sha1 TEXT,
        actual_sha1 TEXT,
        path TEXT,
        archive_path TEXT,
        archive_member TEXT,
        merge_name TEXT,
        optional INTEGER NOT NULL DEFAULT 0,
        message TEXT NOT NULL DEFAULT '',
        error TEXT,
        FOREIGN KEY (scan_machine_id) REFERENCES scan_machine(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_scan_session_created_at ON scan_session(created_at);
    CREATE INDEX IF NOT EXISTS idx_scan_machine_scan_id ON scan_machine(scan_id);
    CREATE INDEX IF NOT EXISTS idx_scan_item_machine_id ON scan_item(scan_machine_id);
    CREATE INDEX IF NOT EXISTS idx_scan_item_status ON scan_item(status);
    CREATE INDEX IF NOT EXISTS idx_scan_item_name ON scan_item(item_name);
    """

    def __init__(self, database: Database) -> None:
        """Inicializa o repositório sobre uma instância ``Database``."""
        self.db = database
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Cria as tabelas de persistência do scanner de forma idempotente."""
        self.db.executescript(self.SCHEMA_SQL)
        self.db.commit()

    @staticmethod
    def _iso(value: Any) -> str | None:
        """Serializa datas e valores textuais para armazenamento SQLite."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _datetime(value: str | None) -> datetime | None:
        """Reconstrói uma data ISO armazenada no SQLite."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def save(self, result: ScanResult) -> int:
        """Persiste uma execução completa e retorna o ID da sessão.

        A gravação ocorre em uma única transação. Se qualquer máquina ou item
        falhar, nenhuma parte do scan é mantida no banco.
        """
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO scan_session (
                    xml_path, started_at, finished_at, cancelled, error,
                    machine_count, total, found, valid, missing, invalid,
                    error_count, expected_size, actual_size
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(result.xml_path) if result.xml_path else None,
                    self._iso(result.started_at),
                    self._iso(result.finished_at),
                    int(result.cancelled),
                    result.error,
                    result.machine_count,
                    result.total,
                    result.found,
                    result.valid,
                    result.missing,
                    result.bad,
                    result.error_count,
                    result.expected_size,
                    result.actual_size,
                ),
            )
            scan_id = int(cursor.lastrowid)

            for machine in result.machines:
                machine_cursor = conn.execute(
                    """
                    INSERT INTO scan_machine (
                        scan_id, machine_name, description, cloneof, started,
                        status, total, found, valid, missing, invalid,
                        error_count, expected_size, actual_size, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        scan_id,
                        machine.machine_name,
                        machine.description,
                        machine.cloneof,
                        int(machine.started),
                        machine.status.value,
                        machine.total,
                        machine.found,
                        machine.valid,
                        machine.missing,
                        machine.bad,
                        machine.error_count,
                        machine.expected_size,
                        machine.actual_size,
                        machine.error,
                    ),
                )
                machine_id = int(machine_cursor.lastrowid)

                conn.executemany(
                    """
                    INSERT INTO scan_item (
                        scan_machine_id, machine_name, item_name, item_type,
                        status, expected_size, actual_size, expected_crc,
                        actual_crc, expected_sha1, actual_sha1, path,
                        archive_path, archive_member, merge_name, optional,
                        message, error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            machine_id,
                            item.machine_name,
                            item.rom_name,
                            item.item_type.value,
                            item.status.value,
                            item.expected_size,
                            item.actual_size,
                            item.expected_crc or None,
                            item.actual_crc or None,
                            item.expected_sha1 or None,
                            item.actual_sha1 or None,
                            str(item.path) if item.path else None,
                            str(item.archive_path) if item.archive_path else None,
                            item.archive_member,
                            item.merge,
                            int(item.optional),
                            item.message,
                            item.error,
                        )
                        for item in machine.roms
                    ],
                )

        return scan_id

    def load(self, scan_id: int) -> ScanResult | None:
        """Reconstrói uma execução completa pelo ID persistido."""
        session = self.db.fetchone(
            "SELECT * FROM scan_session WHERE id = ?",
            (scan_id,),
        )
        if session is None:
            return None

        result = ScanResult(
            xml_path=Path(session["xml_path"]) if session["xml_path"] else None,
            started_at=self._datetime(session["started_at"]),
            finished_at=self._datetime(session["finished_at"]),
            cancelled=bool(session["cancelled"]),
            error=session["error"],
        )

        machines = self.db.fetchall(
            "SELECT * FROM scan_machine WHERE scan_id = ? ORDER BY id",
            (scan_id,),
        )
        for machine_row in machines:
            machine = MachineScanResult(
                machine_name=machine_row["machine_name"],
                description=machine_row["description"] or "",
                cloneof=machine_row["cloneof"],
                started=bool(machine_row["started"]),
                error=machine_row["error_message"],
            )
            items = self.db.fetchall(
                "SELECT * FROM scan_item WHERE scan_machine_id = ? ORDER BY id",
                (machine_row["id"],),
            )
            for row in items:
                machine.add_result(
                    RomScanResult(
                        machine_name=row["machine_name"],
                        rom_name=row["item_name"],
                        status=ScanStatus(row["status"]),
                        expected_size=row["expected_size"],
                        actual_size=row["actual_size"],
                        expected_crc=row["expected_crc"] or "",
                        actual_crc=row["actual_crc"] or "",
                        expected_sha1=row["expected_sha1"] or "",
                        actual_sha1=row["actual_sha1"] or "",
                        path=Path(row["path"]) if row["path"] else None,
                        archive_path=Path(row["archive_path"]) if row["archive_path"] else None,
                        archive_member=row["archive_member"],
                        item_type=ScanItemType(row["item_type"]),
                        merge=row["merge_name"],
                        optional=bool(row["optional"]),
                        message=row["message"] or "",
                        error=row["error"],
                    )
                )
            result.add_machine(machine)

        return result

    def latest_id(self) -> int | None:
        """Retorna o ID do scan mais recente, ou ``None`` quando vazio."""
        value = self.db.fetch_value(
            "SELECT id FROM scan_session ORDER BY id DESC LIMIT 1"
        )
        return int(value) if value is not None else None

    def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        """Lista sessões recentes sem carregar todos os itens do scan."""
        limit = max(1, min(int(limit), 500))
        rows = self.db.fetchall(
            """
            SELECT id, xml_path, started_at, finished_at, cancelled, error,
                   machine_count, total, valid, missing, invalid, error_count,
                   expected_size, actual_size, created_at
            FROM scan_session
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in rows]

    def delete(self, scan_id: int) -> bool:
        """Remove uma sessão e seus resultados associados."""
        cursor = self.db.execute(
            "DELETE FROM scan_session WHERE id = ?",
            (scan_id,),
        )
        self.db.commit()
        return cursor.rowcount > 0


__all__ = ["ScanRepository"]
