"""Persistência do catálogo RetroArch derivado dos arquivos .info locais."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.core.services.retroarch_info_service import RetroArchInfoCore
from app.database.database import Database

logger = logging.getLogger(__name__)


class RetroArchCatalogDatabaseService:
    """Mantém no SQLite a fotografia mais recente dos .info do RetroArch."""

    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()

    def ensure_schema(self) -> None:
        """Cria as tabelas normalizadas do catálogo sem alterar o dataset MAME."""
        self.database.connect()
        self.database.executescript(
            """
            CREATE TABLE IF NOT EXISTS retroarch_core (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                info_path TEXT NOT NULL,
                display_name TEXT NOT NULL,
                corename TEXT NOT NULL,
                display_version TEXT,
                manufacturer TEXT,
                categories TEXT,
                supported_extensions TEXT,
                system_name TEXT,
                system_id TEXT,
                databases TEXT,
                license TEXT,
                permissions TEXT,
                description TEXT,
                features_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS retroarch_system (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS retroarch_core_system (
                core_id INTEGER NOT NULL,
                system_id INTEGER NOT NULL,
                PRIMARY KEY(core_id, system_id),
                FOREIGN KEY(core_id) REFERENCES retroarch_core(id) ON DELETE CASCADE,
                FOREIGN KEY(system_id) REFERENCES retroarch_system(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS retroarch_core_database (
                core_id INTEGER NOT NULL,
                database_name TEXT NOT NULL,
                PRIMARY KEY(core_id, database_name),
                FOREIGN KEY(core_id) REFERENCES retroarch_core(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS retroarch_firmware (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                core_id INTEGER NOT NULL,
                firmware_index INTEGER NOT NULL,
                description TEXT NOT NULL,
                path TEXT NOT NULL,
                optional INTEGER NOT NULL DEFAULT 0,
                md5 TEXT,
                UNIQUE(core_id, firmware_index),
                FOREIGN KEY(core_id) REFERENCES retroarch_core(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_retroarch_core_corename ON retroarch_core(corename);
            CREATE INDEX IF NOT EXISTS idx_retroarch_core_system_id ON retroarch_core(system_id);
            CREATE INDEX IF NOT EXISTS idx_retroarch_firmware_core ON retroarch_firmware(core_id);
            CREATE INDEX IF NOT EXISTS idx_retroarch_firmware_path ON retroarch_firmware(path);
            """
        )
        if self.database.conn is None:
            raise RuntimeError("Banco não conectado.")
        self.database.conn.commit()

    def replace_catalog(self, cores: list[RetroArchInfoCore]) -> int:
        """Substitui atomicamente a fotografia anterior pelos .info encontrados."""
        self.ensure_schema()
        conn = self.database.conn
        if conn is None:
            raise RuntimeError("Banco não conectado.")
        now = datetime.now(timezone.utc).isoformat()
        try:
            conn.execute("BEGIN")
            for table in ("retroarch_core_system", "retroarch_core_database", "retroarch_firmware", "retroarch_core", "retroarch_system"):
                conn.execute(f"DELETE FROM {table}")
            system_ids: dict[str, int] = {}
            for core in cores:
                cursor = conn.execute(
                    """
                    INSERT INTO retroarch_core
                    (filename, info_path, display_name, corename, display_version,
                     manufacturer, categories, supported_extensions, system_name,
                     system_id, databases, license, permissions, description,
                     features_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (core.filename, str(core.info_path), core.display_name, core.corename,
                     core.display_version, core.manufacturer, "|".join(core.categories),
                     "|".join(core.supported_extensions), core.system_name, core.system_id,
                     "|".join(core.databases), core.license, core.permissions, core.description,
                     self._json(core.features), now),
                )
                core_id = int(cursor.lastrowid)
                if core.system_id:
                    system_id = core.system_id.strip()
                    system_name = (core.system_name or system_id).strip()
                    conn.execute("INSERT OR IGNORE INTO retroarch_system(system_id, name) VALUES (?, ?)", (system_id, system_name))
                    row = conn.execute("SELECT id FROM retroarch_system WHERE system_id = ?", (system_id,)).fetchone()
                    if row is None:
                        raise RuntimeError(f"Sistema não encontrado após inserção: {system_id}")
                    system_ids[system_id] = int(row[0])
                    conn.execute("INSERT OR IGNORE INTO retroarch_core_system(core_id, system_id) VALUES (?, ?)", (core_id, system_ids[system_id]))
                for database in core.databases:
                    conn.execute("INSERT OR IGNORE INTO retroarch_core_database(core_id, database_name) VALUES (?, ?)", (core_id, database))
                for firmware in core.firmware:
                    conn.execute(
                        "INSERT INTO retroarch_firmware(core_id, firmware_index, description, path, optional, md5) VALUES (?, ?, ?, ?, ?, ?)",
                        (core_id, firmware.index, firmware.description, firmware.path, int(firmware.optional), firmware.md5),
                    )
            conn.commit()
            logger.info("RetroArch catalog database atualizado: cores=%d | sistemas=%d", len(cores), len(system_ids))
            return len(cores)
        except Exception:
            conn.rollback()
            logger.exception("Falha ao atualizar catálogo RetroArch no SQLite.")
            raise

    @staticmethod
    def _json(value: dict[str, str]) -> str:
        """Serializa features para armazenamento no SQLite."""
        import json
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def count(self) -> tuple[int, int, int]:
        """Retorna quantidades de cores, sistemas e firmwares catalogados."""
        self.ensure_schema()
        conn = self.database.conn
        if conn is None:
            raise RuntimeError("Banco não conectado.")
        return tuple(int(conn.execute(sql).fetchone()[0]) for sql in (
            "SELECT COUNT(*) FROM retroarch_core",
            "SELECT COUNT(*) FROM retroarch_system",
            "SELECT COUNT(*) FROM retroarch_firmware",
        ))  # type: ignore[return-value]


__all__ = ["RetroArchCatalogDatabaseService"]
