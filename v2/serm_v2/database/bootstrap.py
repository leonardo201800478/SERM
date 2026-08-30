"""Bootstrap das migrations SQLite da V2."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..runtime.paths import database_path


class DatabaseBootstrapError(RuntimeError):
    """Erro ao inicializar o schema local da V2."""


# Tables introduced by the MAME catalog migration and the columns that make
# each table compatible with that schema. Older V2 development databases may
# already contain tables with these names but with an incompatible shape.
_MAME_CATALOG_REQUIRED_COLUMNS: dict[str, set[str]] = {
    "mame_listxml_import": {"id", "emulator_id", "source_hash", "machine_count", "parser_version"},
    "mame_xml_node": {"id", "import_id", "element_name", "xml_path", "attributes_json"},
    "mame_machine": {"id", "import_id", "name", "sourcefile", "isdevice", "runnable", "cloneof", "romof", "sampleof", "description", "year", "manufacturer", "xml_node_id"},
    "mame_rom": {"id", "machine_id", "name", "bios", "size", "crc", "sha1", "md5", "merge", "region", "offset", "status", "optional", "dispose"},
    "mame_disk": {"id", "machine_id", "name", "md5", "sha1", "merge", "region", "index_value", "writable", "status", "optional"},
    "mame_display": {"id", "machine_id", "tag", "type", "rotate", "width", "height", "refresh_hz", "refresh_raw", "pixclock", "htotal", "hbend", "hbstart", "vtotal", "vbend", "vbstart", "hsync", "vsync", "xaspect", "yaspect", "orientation_raw", "source", "confidence", "xml_node_id"},
    "mame_input": {"id", "machine_id", "players", "buttons", "coins", "service", "tilt", "control_type", "ways", "minimum", "maximum", "sensitivity", "keydelta", "reverse"},
}


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    """Return the existing column names for a SQLite table."""
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def _next_legacy_name(connection: sqlite3.Connection, table: str) -> str:
    """Return a collision-free name for an incompatible legacy table."""
    base = f"{table}_legacy"
    candidate = base
    suffix = 2
    while connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (candidate,)
    ).fetchone():
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def _prepare_mame_catalog_compatibility(connection: sqlite3.Connection) -> list[str]:
    """Quarantine incompatible old MAME tables without deleting their data.

    ``CREATE TABLE IF NOT EXISTS`` cannot change the shape of a table that was
    created by an earlier development build. In particular, the previous
    schema could have a ``mame_machine`` table without ``import_id``; the new
    migration then fails while creating its index. We rename only incompatible
    tables, preserving all rows and allowing migration 003 to create the
    authoritative V2 schema under the original names.
    """
    renamed: list[str] = []
    for table, required in _MAME_CATALOG_REQUIRED_COLUMNS.items():
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            continue
        columns = _table_columns(connection, table)
        if required.issubset(columns):
            continue
        legacy_name = _next_legacy_name(connection, table)
        connection.execute(f'ALTER TABLE "{table}" RENAME TO "{legacy_name}"')
        renamed.append(f"{table} -> {legacy_name}")
    return renamed


def apply_migrations(db_path: Path | None = None) -> list[str]:
    """Aplica migrations SQL pendentes sem tocar no banco da V1.

    A função é idempotente: uma migration identificada em ``schema_migrations``
    não é executada novamente. Bancos V2 de desenvolvimento que contenham uma
    tabela MAME antiga incompatível são preservados por renomeação automática.
    """
    target = db_path or database_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    migration_root = Path(__file__).resolve().parent / "migrations"
    migrations = sorted(migration_root.glob("[0-9][0-9][0-9]_*.sql"))
    if not migrations:
        return []

    applied: list[str] = []
    with sqlite3.connect(target) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        for migration in migrations:
            version = migration.stem
            exists = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version=?", (version,)
            ).fetchone()
            if exists:
                continue
            try:
                if version == "003_mame_catalog_schema":
                    _prepare_mame_catalog_compatibility(connection)
                connection.executescript(migration.read_text(encoding="utf-8"))
            except sqlite3.DatabaseError as exc:
                connection.rollback()
                raise DatabaseBootstrapError(
                    f"Falha ao aplicar migration {version}: {exc}"
                ) from exc
            applied.append(version)
        connection.commit()
    return applied


__all__ = ["DatabaseBootstrapError", "apply_migrations"]
