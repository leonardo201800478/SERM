"""Quantitative, read-only audit of LaunchBox metadata content.

This audit measures how fields are populated and how values are distributed.
It deliberately produces statistics instead of importing LaunchBox records.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .launchbox_audit import LaunchBoxAudit
from .launchbox_provider import LaunchBoxProvider


@dataclass(frozen=True, slots=True)
class ColumnProfile:
    """Population profile for one SQLite column."""

    table: str
    column: str
    total_rows: int
    non_null_rows: int
    blank_rows: int
    distinct_non_null: int

    @property
    def population_percent(self) -> float:
        """Return the percentage of rows containing a non-null value."""
        if self.total_rows == 0:
            return 0.0
        return round(self.non_null_rows * 100 / self.total_rows, 2)


@dataclass(frozen=True, slots=True)
class ValueCount:
    """Count of one representative value in a column."""

    value: str
    count: int


class LaunchBoxContentAudit:
    """Generate quantitative statistics from the real LaunchBox database."""

    def __init__(self, provider: LaunchBoxProvider) -> None:
        self.provider = provider
        self.structure = LaunchBoxAudit(provider)

    def column_profiles(self) -> tuple[ColumnProfile, ...]:
        """Profile every user-table column using aggregate SQLite queries."""
        database = self._require_database()
        profiles: list[ColumnProfile] = []
        with self._connect(database) as connection:
            for table in self.structure.tables():
                table_identifier = self._identifier(table.name)
                for column in table.columns:
                    identifier = self._identifier(column.name)
                    row = connection.execute(
                        f"SELECT COUNT(*), COUNT({identifier}), "
                        f"COUNT(CASE WHEN CAST({identifier} AS TEXT) = ? THEN 1 END), "
                        f"COUNT(DISTINCT {identifier}) FROM {table_identifier}",
                        ("",),
                    ).fetchone()
                    profiles.append(
                        ColumnProfile(
                            table=table.name,
                            column=column.name,
                            total_rows=int(row[0]),
                            non_null_rows=int(row[1]),
                            blank_rows=int(row[2]),
                            distinct_non_null=int(row[3]),
                        )
                    )
        return tuple(profiles)

    def top_values(self, table: str, column: str, limit: int = 20) -> tuple[ValueCount, ...]:
        """Return the most frequent non-null/non-blank values from a column."""
        if limit < 1:
            return ()
        self._validate_identifier(table)
        self._validate_identifier(column)
        if column not in self.provider.table_columns(table):
            raise ValueError(f"Coluna não encontrada: {table}.{column}")
        database = self._require_database()
        with self._connect(database) as connection:
            rows = connection.execute(
                f'SELECT CAST("{column}" AS TEXT), COUNT(*) FROM "{table}" '
                f'WHERE "{column}" IS NOT NULL AND TRIM(CAST("{column}" AS TEXT)) <> ? '
                f'GROUP BY "{column}" ORDER BY COUNT(*) DESC, CAST("{column}" AS TEXT) LIMIT ?',
                ("", limit),
            ).fetchall()
        return tuple(ValueCount(value=str(row[0]), count=int(row[1])) for row in rows)

    def summary(self) -> dict[str, Any]:
        """Return a JSON-serializable content-audit summary."""
        profiles = self.column_profiles()
        return {
            "database": str(self._require_database()),
            "tables": [
                {
                    "table": profile.table,
                    "column": profile.column,
                    "total_rows": profile.total_rows,
                    "non_null_rows": profile.non_null_rows,
                    "blank_rows": profile.blank_rows,
                    "distinct_non_null": profile.distinct_non_null,
                    "population_percent": profile.population_percent,
                }
                for profile in profiles
            ],
            "top_values": {
                table: {
                    column: [
                        {"value": item.value, "count": item.count}
                        for item in self.top_values(table, column)
                    ]
                    for table, column in (
                        ("Games", "Platform"),
                        ("Games", "Genres"),
                        ("Games", "Developer"),
                        ("Games", "Publisher"),
                        ("GameImages", "Type"),
                        ("GameImages", "Region"),
                        ("GameAlternateTitles", "Region"),
                        ("Emulators", "Name"),
                        ("EmulatorPlatforms", "Emulator"),
                        ("EmulatorPlatforms", "Platform"),
                    )
                    if self._column_exists(table, column)
                }
            },
        }

    def _column_exists(self, table: str, column: str) -> bool:
        """Return whether a table contains the requested column."""
        try:
            return column in self.provider.table_columns(table)
        except ValueError:
            return False

    def _require_database(self) -> Path:
        """Return the configured LaunchBox database or raise an explicit error."""
        database = self.provider.metadata_database()
        if database is None:
            raise FileNotFoundError("LaunchBox.Metadata.db não foi localizado.")
        return database

    @staticmethod
    def _connect(database: Path) -> sqlite3.Connection:
        """Open the LaunchBox database in read-only mode."""
        return sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)

    @staticmethod
    def _validate_identifier(identifier: str) -> None:
        """Reject identifiers that cannot safely be used in generated SQL."""
        if not identifier or not identifier.replace("_", "").isalnum():
            raise ValueError(f"Identificador SQL inválido: {identifier}")

    @classmethod
    def _identifier(cls, identifier: str) -> str:
        """Validate and quote an SQLite identifier."""
        cls._validate_identifier(identifier)
        return f'"{identifier}"'
