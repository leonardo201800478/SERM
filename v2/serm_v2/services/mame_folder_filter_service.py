"""Importação e consulta dos filtros auxiliares ``folders/*.ini`` do MAME."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class MameFolderFilterService:
    """Persiste listas de machines dos INIs auxiliares sem substituir o ListXML."""

    EXCLUDED_SECTIONS = {"FOLDER_SETTINGS"}

    def __init__(self, database_path: Path, mame_root: Path) -> None:
        self.database_path = Path(database_path); self.mame_root = Path(mame_root); self.folders_path = self.mame_root / "folders"

    @staticmethod
    def _hash_file(path: Path) -> tuple[str, int]:
        digest = hashlib.sha256(); size = 0
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""): size += len(block); digest.update(block)
        return digest.hexdigest(), size

    @classmethod
    def _entries(cls, path: Path):
        section: str | None = None
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith((";", "#")): continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1].strip() or None; continue
                if section and section.upper() in cls.EXCLUDED_SECTIONS: continue
                machine_name = line.split("=", 1)[0].strip()
                if machine_name: yield section, machine_name, line

    def ingest(self, logger=None) -> dict[str, int | str]:
        """Importa todos os INIs; para cada nome de arquivo somente a revisão mais recente é ativa."""
        log = logger or (lambda _message: None)
        if not self.folders_path.is_dir(): return {"files": 0, "entries": 0, "status": "missing"}
        files = sorted(self.folders_path.glob("*.ini"), key=lambda path: path.name.casefold()); total_entries = 0; imported_files = 0
        connection = sqlite3.connect(self.database_path, timeout=120.0); connection.execute("PRAGMA foreign_keys=ON")
        try:
            for path in files:
                source_hash, byte_length = self._hash_file(path)
                existing = connection.execute("SELECT id FROM mame_folder_filter_source WHERE source_hash=? ORDER BY id DESC LIMIT 1", (source_hash,)).fetchone()
                if existing:
                    imported_files += 1; continue
                # Os filtros são versionados junto do diretório MAME atual. Ao
                # trocar de pacote, a versão anterior do mesmo arquivo não deve
                # continuar participando das consultas.
                old_ids = [int(row[0]) for row in connection.execute("SELECT id FROM mame_folder_filter_source WHERE lower(file_name)=lower(?)", (path.name,)).fetchall()]
                if old_ids:
                    connection.executemany("DELETE FROM mame_folder_filter_source WHERE id=?", [(source_id,) for source_id in old_ids])
                now = datetime.now(UTC).isoformat(); cursor = connection.execute("INSERT INTO mame_folder_filter_source (file_name,file_path,source_hash,byte_length,imported_at,status) VALUES(?,?,?,?,?,'captured')", (path.name, str(path), source_hash, byte_length, now)); source_id = int(cursor.lastrowid); entries = list(self._entries(path))
                connection.executemany("INSERT OR IGNORE INTO mame_folder_filter_entry (source_id,section,machine_name,raw_value) VALUES(?,?,?,?)", [(source_id, section, machine, raw) for section, machine, raw in entries]); connection.execute("UPDATE mame_folder_filter_source SET status='completed' WHERE id=?", (source_id,)); total_entries += len(entries); imported_files += 1; log(f"MAME | FOLDERS | {path.name} | entries={len(entries):,}")
            connection.commit()
        except Exception:
            connection.rollback(); raise
        finally: connection.close()
        return {"files": imported_files, "entries": total_entries, "status": "completed"}

    @classmethod
    def machine_names_for_files(cls, database_path: Path, file_names: tuple[str, ...], machine_names: set[str] | None = None) -> set[str]:
        db_path = Path(database_path)
        if not db_path.is_file(): return set()
        connection = sqlite3.connect(db_path, timeout=30.0)
        try:
            lowered = {name.casefold() for name in file_names}; ids = [int(row[0]) for row in connection.execute("SELECT id FROM mame_folder_filter_source WHERE lower(file_name) IN ({})".format(",".join("?") for _ in lowered)), tuple(sorted(lowered)))] if lowered else []
            if not ids: return set()
            placeholders = ",".join("?" for _ in ids); values = {str(row[0]) for row in connection.execute(f"SELECT DISTINCT machine_name FROM mame_folder_filter_entry WHERE source_id IN ({placeholders})", ids) if row[0]}
            if machine_names is not None: values.intersection_update(machine_names)
            return values
        finally: connection.close()

    @classmethod
    def sections(cls, database_path: Path, file_name: str, machine_names: set[str] | None = None) -> list[dict[str, object]]:
        db_path = Path(database_path)
        if not db_path.is_file(): return []
        connection = sqlite3.connect(db_path, timeout=30.0)
        try:
            source = connection.execute("SELECT id FROM mame_folder_filter_source WHERE lower(file_name)=lower(?) ORDER BY id DESC LIMIT 1", (file_name,)).fetchone()
            if source is None: return []
            source_id = int(source[0])
            if machine_names is None:
                rows = connection.execute("SELECT section,COUNT(DISTINCT machine_name) FROM mame_folder_filter_entry WHERE source_id=? GROUP BY section ORDER BY section COLLATE NOCASE", (source_id,)).fetchall()
                return [{"section": str(row[0] or ""), "machines": int(row[1] or 0)} for row in rows]
            valid = set(machine_names)
            if not valid: return []
            placeholders = ",".join("?" for _ in valid)
            rows = connection.execute(f"SELECT section,COUNT(DISTINCT machine_name) FROM mame_folder_filter_entry WHERE source_id=? AND machine_name IN ({placeholders}) GROUP BY section ORDER BY section COLLATE NOCASE", (source_id, *sorted(valid))).fetchall()
            return [{"section": str(row[0] or ""), "machines": int(row[1] or 0)} for row in rows]
        finally: connection.close()


__all__ = ["MameFolderFilterService"]
