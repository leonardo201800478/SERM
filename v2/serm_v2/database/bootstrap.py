"""Bootstrap das migrations SQLite da V2."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..runtime.paths import database_path


class DatabaseBootstrapError(RuntimeError):
    """Erro ao inicializar o schema local da V2."""


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    """Retorna as colunas existentes de uma tabela SQLite."""
    return {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}


def _next_legacy_name(connection: sqlite3.Connection, table: str) -> str:
    """Gera nome livre para uma tabela incompatível antiga."""
    base = f"{table}_legacy"
    candidate = base
    suffix = 2
    while connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (candidate,)).fetchone():
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def _prepare_legacy_catalog(connection: sqlite3.Connection) -> list[str]:
    """Isola tabelas MAME antigas que conflitem com o novo schema base.

    O catálogo normalizado antigo não é apagado: é renomeado. A Etapa 1
    utiliza apenas as tabelas lossless e pode então começar em estado limpo.
    """
    required = {
        "mame_listxml_import": {"id", "emulator_id", "source_hash", "machine_count", "parser_version"},
        "mame_listxml_document": {"id", "import_id", "source_hash", "xml_text", "byte_length"},
    }
    renamed: list[str] = []
    for table, columns_required in required.items():
        row = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        if not row:
            continue
        if columns_required.issubset(_table_columns(connection, table)):
            continue
        legacy = _next_legacy_name(connection, table)
        connection.execute(f'ALTER TABLE "{table}" RENAME TO "{legacy}"')
        renamed.append(f"{table}->{legacy}")
    return renamed


def _remove_failed_new_database(target: Path, created_by_bootstrap: bool) -> None:
    """Remove banco e sidecars somente quando o arquivo nasceu nesta execução."""
    if not created_by_bootstrap:
        return
    for path in (target, Path(f"{target}-wal"), Path(f"{target}-shm")):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def apply_migrations(db_path: Path | None = None) -> list[str]:
    """Aplica migrations de forma idempotente e segura para a base V2."""
    target = (db_path or database_path()).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    migration_root = Path(__file__).resolve().parent / "migrations"
    migrations = sorted(migration_root.glob("[0-9][0-9][0-9]_*.sql"))
    if not migrations:
        return []

    created_by_bootstrap = not target.exists()
    applied: list[str] = []
    try:
        with sqlite3.connect(target, timeout=60.0) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
            for migration in migrations:
                version = migration.stem
                if connection.execute("SELECT 1 FROM schema_migrations WHERE version=?", (version,)).fetchone():
                    continue
                try:
                    if version == "003_mame_catalog_schema":
                        renamed = _prepare_legacy_catalog(connection)
                        if renamed:
                            # Informação útil para diagnóstico sem depender de logging global.
                            connection.execute("PRAGMA user_version = 3")
                    connection.executescript(migration.read_text(encoding="utf-8"))
                except sqlite3.DatabaseError as exc:
                    connection.rollback()
                    raise DatabaseBootstrapError(f"Falha ao aplicar migration {version}: {exc}") from exc
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
