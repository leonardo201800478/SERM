"""Ingestão do catálogo produzido pelo executável MAME configurado no SERM."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..emulation.mame_dat_scraper import MameDatError, scrape_mame_dat
from ..runtime.paths import data_root


class MameCatalogError(RuntimeError):
    """Erro de configuração, extração ou persistência do catálogo MAME."""


class MameCatalogService:
    """Conecta o executável MAME configurado à primeira camada de dados da V2."""

    PATHS_FILE = data_root() / "emulator_paths.json"
    DB_FILE = data_root() / "mame_catalog.sqlite3"
    RAW_FILE = data_root() / "mame" / "metadata" / "listxml.xml"

    def configured_executable(self) -> Path:
        """Retorna o mame.exe explicitamente escolhido na guia Diretórios."""
        try:
            data = json.loads(self.PATHS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise MameCatalogError("Não foi possível ler emulator_paths.json.") from exc
        raw = data.get("mame_executable")
        if not isinstance(raw, str) or not raw.strip():
            raise MameCatalogError(
                "Nenhum executável MAME foi configurado em Diretórios. "
                "Selecione o mame.exe que deve produzir o catálogo."
            )
        executable = Path(raw).expanduser().resolve()
        if not executable.is_file():
            raise MameCatalogError(f"Executável MAME configurado não encontrado: {executable}")
        return executable

    def ingest(self, *, timeout: float = 120.0) -> dict[str, object]:
        """Executa ``mame.exe -listxml`` e faz a primeira ingestão no SQLite.

        O XML bruto é preservado separadamente. A tabela de máquinas contém
        somente campos que podem ser extraídos sem alterar a semântica do XML;
        dados de timing/geometria serão enriquecidos na próxima etapa.
        """
        executable = self.configured_executable()
        try:
            dat = scrape_mame_dat(executable, timeout=timeout)
        except MameDatError as exc:
            raise MameCatalogError(str(exc)) from exc

        self.RAW_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.RAW_FILE.write_text(dat.xml_text, encoding="utf-8", newline="\n")
        self._initialize_database()

        import xml.etree.ElementTree as ET

        root = ET.fromstring(dat.xml_text)
        machines = []
        for machine in root.findall("machine"):
            name = machine.attrib.get("name", "").strip()
            if not name:
                continue
            machines.append(
                (
                    name,
                    machine.attrib.get("sourcefile"),
                    machine.attrib.get("isbios"),
                    machine.attrib.get("isdevice"),
                    machine.attrib.get("runnable"),
                    machine.findtext("description"),
                    machine.findtext("year"),
                    machine.findtext("manufacturer"),
                )
            )

        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.DB_FILE) as connection:
            connection.execute("DELETE FROM mame_machine")
            connection.executemany(
                """INSERT INTO mame_machine
                (name, sourcefile, isbios, isdevice, runnable, description, year, manufacturer, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(*row, now) for row in machines],
            )
            connection.execute(
                """INSERT INTO mame_catalog_run
                (executable, machine_count, raw_xml, ingested_at)
                VALUES (?, ?, ?, ?)""",
                (str(executable), len(machines), str(self.RAW_FILE), now),
            )
            connection.commit()

        return {
            "executable": executable,
            "machine_count": len(machines),
            "raw_xml": self.RAW_FILE,
            "database": self.DB_FILE,
        }

    def _initialize_database(self) -> None:
        """Cria apenas as tabelas pertencentes à camada de catálogo MAME da V2."""
        self.DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.DB_FILE) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS mame_catalog_run (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    executable TEXT NOT NULL,
                    machine_count INTEGER NOT NULL,
                    raw_xml TEXT NOT NULL,
                    ingested_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mame_machine (
                    name TEXT PRIMARY KEY,
                    sourcefile TEXT,
                    isbios TEXT,
                    isdevice TEXT,
                    runnable TEXT,
                    description TEXT,
                    year TEXT,
                    manufacturer TEXT,
                    ingested_at TEXT NOT NULL
                );
                """
            )
            connection.commit()


__all__ = ["MameCatalogError", "MameCatalogService"]
