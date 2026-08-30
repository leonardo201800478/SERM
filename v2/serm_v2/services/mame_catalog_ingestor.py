"""Ingestor oficial do catálogo MAME para o banco V2."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .mame_display_pipeline import MameDisplayPipeline
from ..runtime.paths import database_path


class MameCatalogIngestor:
    """Orquestra ListXML, armazenamento lossless e geração do display profile."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or database_path()
        self.pipeline = MameDisplayPipeline(self.db_path)

    def ingest(self, executable: str | Path, **kwargs) -> dict[str, object]:
        """Importa o MAME real e grava também o XML exato dentro do SQLite."""
        result = self.pipeline.run(executable, **kwargs)
        xml_path = Path(str(result["xml_path"]))
        xml_text = xml_path.read_text(encoding="utf-8")
        with sqlite3.connect(self.db_path) as db:
            db.execute("PRAGMA foreign_keys=ON")
            migration = Path(__file__).resolve().parents[1] / "database" / "migrations" / "004_mame_raw_document.sql"
            db.executescript(migration.read_text(encoding="utf-8"))
            import_id = db.execute(
                "SELECT id FROM mame_listxml_import WHERE source_hash=?",
                (str(result["source_hash"]),),
            ).fetchone()[0]
            db.execute(
                """INSERT INTO mame_listxml_document
                (import_id,source_hash,encoding,xml_text,byte_length,stored_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(import_id) DO UPDATE SET
                    source_hash=excluded.source_hash,
                    encoding=excluded.encoding,
                    xml_text=excluded.xml_text,
                    byte_length=excluded.byte_length,
                    stored_at=excluded.stored_at""",
                (
                    import_id,
                    str(result["source_hash"]),
                    "utf-8",
                    xml_text,
                    len(xml_text.encode("utf-8")),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            db.commit()
        result["raw_xml_stored_in_database"] = True
        result["raw_xml_bytes"] = len(xml_text.encode("utf-8"))
        return result


__all__ = ["MameCatalogIngestor"]
