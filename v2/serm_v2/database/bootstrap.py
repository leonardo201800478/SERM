"""Bootstrap das migrations SQLite da V2."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..runtime.paths import database_path


class DatabaseBootstrapError(RuntimeError):
    """Erro ao inicializar o schema local da V2."""


def apply_migrations(db_path: Path | None = None) -> list[str]:
    """Aplica migrations SQL pendentes sem tocar no banco da V1.

    A função é idempotente: uma migration identificada em ``schema_migrations``
    não é executada novamente. O SQLite permanece como fonte local única da V2.
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
