"""Small SQLite typing/runtime helpers shared by V2 services."""

from __future__ import annotations


def require_lastrowid(value: int | None) -> int:
    """Return a valid SQLite row id or fail explicitly after an INSERT."""
    if value is None:
        raise RuntimeError("SQLite não retornou lastrowid após INSERT.")
    return value
