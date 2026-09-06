"""SQLite engine boundary for V2.

No V1 database or legacy service is imported here.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine  # type: ignore[import-not-found]


def create_sqlite_engine(database_path: Path) -> Engine:
    """Create a V2 SQLite engine and keep the database boundary explicit."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{database_path.as_posix()}", future=True)
