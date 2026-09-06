"""V2 settings kept independent from legacy configuration."""

from __future__ import annotations

from dataclasses import dataclass

from ..runtime.paths import database_path


@dataclass(frozen=True)
class Settings:
    """Immutable application settings for the V2 bootstrap."""

    database: str = str(database_path())
