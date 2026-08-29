"""Read-only LaunchBox metadata provider for SERM V2.

LaunchBox is treated as an external provider. This module never writes to the
LaunchBox database or XML files and does not make them part of SERM's source
of truth.
"""
from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .launchbox import LaunchBoxIntegration


@dataclass(frozen=True, slots=True)
class LaunchBoxGame:
    """Minimal normalized representation of a LaunchBox game record."""

    database_id: int
    name: str
    platform: str
    release_date: str | None = None
    release_year: int | None = None
    overview: str | None = None
    developer: str | None = None
    publisher: str | None = None
    genres: str | None = None


@dataclass(frozen=True, slots=True)
class LaunchBoxPlatform:
    """Normalized platform metadata from LaunchBox Platforms.xml."""

    name: str
    emulated: bool | None = None
    category: str | None = None
    manufacturer: str | None = None
    developer: str | None = None
    cpu: str | None = None
    memory: str | None = None
    graphics: str | None = None
    sound: str | None = None
    display: str | None = None
    media: str | None = None
    max_controllers: str | None = None
    notes: str | None = None


class LaunchBoxProvider:
    """Expose LaunchBox data through a strictly read-only provider API."""

    def __init__(self, integration: LaunchBoxIntegration | None = None) -> None:
        self.integration = integration or LaunchBoxIntegration()

    def metadata_database(self) -> Path | None:
        """Return the configured LaunchBox metadata database, if available."""
        return self.integration.metadata_database()

    def platforms_xml(self) -> Path | None:
        """Return the configured LaunchBox Platforms.xml, if available."""
        return self.integration.platforms_xml()

    def database_tables(self) -> tuple[str, ...]:
        """List user tables exposed by the LaunchBox metadata database."""
        database = self._require_database()
        with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            ).fetchall()
        return tuple(row[0] for row in rows)

    def table_columns(self, table: str) -> tuple[str, ...]:
        """Return column names for a validated LaunchBox table in read-only mode."""
        if not table or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for character in table):
            raise ValueError("Nome de tabela inválido.")
        database = self._require_database()
        with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as connection:
            rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        if not rows:
            raise ValueError(f"Tabela LaunchBox não encontrada: {table}")
        return tuple(row[1] for row in rows)

    def iter_games(self, limit: int | None = None) -> Iterator[LaunchBoxGame]:
        """Stream normalized game records without importing them into SERM."""
        database = self._require_database()
        columns = set(self.table_columns("Games"))
        required = {"DatabaseID", "Name", "Platform"}
        missing = required - columns
        if missing:
            raise RuntimeError(f"Tabela Games do LaunchBox sem colunas obrigatórias: {sorted(missing)}")

        optional_columns = (
            "ReleaseDate",
            "ReleaseYear",
            "Overview",
            "Developer",
            "Publisher",
            "Genres",
        )
        selected = ["DatabaseID", "Name", "Platform", *(column for column in optional_columns if column in columns)]
        query = f'SELECT {", ".join(fchr for fchr in (f'"{column}"' for column in selected))} FROM "Games" ORDER BY "DatabaseID"'
        parameters: tuple[Any, ...] = ()
        if limit is not None:
            if limit < 1:
                return
            query += " LIMIT ?"
            parameters = (limit,)

        with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as connection:
            for row in connection.execute(query, parameters):
                values = dict(zip(selected, row, strict=True))
                yield LaunchBoxGame(
                    database_id=int(values["DatabaseID"]),
                    name=str(values["Name"]),
                    platform=str(values["Platform"]),
                    release_date=values.get("ReleaseDate"),
                    release_year=values.get("ReleaseYear"),
                    overview=values.get("Overview"),
                    developer=values.get("Developer"),
                    publisher=values.get("Publisher"),
                    genres=values.get("Genres"),
                )

    def iter_platforms(self) -> Iterator[LaunchBoxPlatform]:
        """Stream normalized platform records from LaunchBox Platforms.xml."""
        xml_path = self._require_platforms_xml()
        for element in self._platform_elements(xml_path):
            values = {child.tag.rsplit("}", 1)[-1]: (child.text or "").strip() for child in element}
            name = values.get("Name", "").strip()
            if not name:
                continue
            yield LaunchBoxPlatform(
                name=name,
                emulated=self._parse_bool(values.get("Emulated")),
                category=values.get("Category") or None,
                manufacturer=values.get("Manufacturer") or None,
                developer=values.get("Developer") or None,
                cpu=values.get("Cpu") or None,
                memory=values.get("Memory") or None,
                graphics=values.get("Graphics") or None,
                sound=values.get("Sound") or None,
                display=values.get("Display") or None,
                media=values.get("Media") or None,
                max_controllers=values.get("MaxControllers") or None,
                notes=values.get("Notes") or None,
            )

    def _require_database(self) -> Path:
        """Return the database path or raise a clear configuration error."""
        database = self.metadata_database()
        if database is None:
            raise FileNotFoundError("LaunchBox.Metadata.db não foi localizado.")
        return database

    def _require_platforms_xml(self) -> Path:
        """Return Platforms.xml or raise a clear configuration error."""
        xml_path = self.platforms_xml()
        if xml_path is None:
            raise FileNotFoundError("LaunchBox Platforms.xml não foi localizado.")
        return xml_path

    @staticmethod
    def _platform_elements(xml_path: Path) -> Iterator[ET.Element]:
        """Yield platform elements while tolerating an XML namespace."""
        root = ET.parse(xml_path).getroot()
        for element in root.iter():
            tag = element.tag.rsplit("}", 1)[-1]
            if tag.casefold() == "platform":
                yield element

    @staticmethod
    def _parse_bool(value: str | None) -> bool | None:
        """Convert common LaunchBox boolean text to Python bool."""
        if value is None or not value:
            return None
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
        return None
