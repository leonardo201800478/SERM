"""Bootstrap das migrations SQLite da V2."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..runtime.paths import database_path


class DatabaseBootstrapError(RuntimeError):
    """Erro ao inicializar o schema local da V2."""


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
    """Quarantine incompatible old MAME tables without deleting their data."""
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


def _remove_failed_new_database(target: Path, created_by_bootstrap: bool) -> None:
    """Remove only a database file created by this bootstrap attempt.

    This is deliberately limited to a previously non-existent file. An existing
    V2 database is never deleted automatically when a later migration fails.
    SQLite may also create ``-wal`` and ``-shm`` sidecars, so those are removed
    together with the newly created database when present.
    """
    if not created_by_bootstrap:
        return
    for path in (target, Path(f"{target}-wal"), Path(f"{target}-shm")):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # The original bootstrap exception is more useful to the caller.
            pass


def apply_migrations(db_path: Path | None = None) -> list[str]:
    """Aplica migrations SQLite e remove banco somente se sua criação falhar.

    Se ``target`` não existia antes da execução e uma migration falhar, o arquivo
    incompleto é removido para que a próxima execução faça uma criação limpa.
    Se o banco já existia, ele é preservado integralmente em caso de falha.
    """
    target = (db_path or database_path()).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    migration_root = Path(__file__).resolve().parent / "migrations"
    migrations = sorted(migration_root.glob("[0-9][0-9][0-9]_*.sql"))
    if not migrations:
        return []

    created_by_bootstrap = not target.exists()
    applied: list[str] = []
    try:
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
    except DatabaseBootstrapError:
        _remove_failed_new_database(target, created_by_bootstrap)
        raise
    except (OSError, sqlite3.Error) as exc:
        _remove_failed_new_database(target, created_by_bootstrap)
        raise DatabaseBootstrapError(f"Falha ao inicializar banco V2: {exc}") from exc
    return applied


__all__ = ["DatabaseBootstrapError", "apply_migrations"]
