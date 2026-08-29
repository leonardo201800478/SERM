"""Read-only structural audit helpers for the LaunchBox provider."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from .launchbox_provider import LaunchBoxProvider


@dataclass(frozen=True, slots=True)
class ColumnInfo:
    """Describe one SQLite column exposed by the external LaunchBox database."""

    table: str
    name: str
    data_type: str
    not_null: bool
    primary_key: bool
    default_value: Any


@dataclass(frozen=True, slots=True)
class TableAudit:
    """Summarize one LaunchBox table without copying its records into SERM."""

    name: str
    row_count: int
    columns: tuple[ColumnInfo, ...]


class LaunchBoxAudit:
    """Inspect LaunchBox database and XML structure without modifying either source."""

    def __init__(self, provider: LaunchBoxProvider | None = None) -> None:
        self.provider = provider or LaunchBoxProvider()

    def tables(self) -> tuple[TableAudit, ...]:
        """Return table names, column metadata and row counts for the LaunchBox DB."""
        database = self.provider.metadata_database()
        if database is None:
            raise FileNotFoundError("LaunchBox.Metadata.db não foi localizado.")

        uri = f"file:{database.as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            tables = connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            ).fetchall()

            result: list[TableAudit] = []
            for (table_name,) in tables:
                quoted = table_name.replace('"', '""')
                columns = tuple(
                    ColumnInfo(
                        table=table_name,
                        name=row[1],
                        data_type=row[2],
                        not_null=bool(row[3]),
                        primary_key=bool(row[5]),
                        default_value=row[4],
                    )
                    for row in connection.execute(f'PRAGMA table_info("{quoted}")')
                )
                row_count = int(
                    connection.execute(f'SELECT COUNT(*) FROM "{quoted}"').fetchone()[0]
                )
                result.append(TableAudit(table_name, row_count, columns))

        return tuple(result)

    def platform_count(self) -> int:
        """Count platform records exposed by LaunchBox Platforms.xml."""
        return sum(1 for _ in self.provider.iter_platforms())

    def emulated_platform_count(self) -> int:
        """Count LaunchBox platforms marked as emulated."""
        return sum(1 for platform in self.provider.iter_platforms() if platform.emulated is True)

    def game_sample(self, limit: int = 10):
        """Return a small deterministic game sample for manual inspection."""
        if limit < 1:
            raise ValueError("limit deve ser maior que zero.")
        return tuple(self.provider.iter_games(limit=limit))
