"""Scanner de ROMs com índice persistente para busca alternativa.

A busca alternativa do :class:`RomScanner` original construía um índice
completo em memória na primeira ROM ausente. Em fullsets grandes isso causava
uma pausa perceptível no pós-scan.

Esta implementação mantém o JSONL do scan como auditoria, mas usa SQLite
somente para o índice de consulta ``(CRC, tamanho)``. O índice é persistente
e pode ser reutilizado em execuções futuras. O conteúdo do ZIP continua sendo
consultado apenas no diretório central; ROMs não são descompactadas durante a
indexação.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import zipfile
from pathlib import Path
from typing import Any, Iterable

from app.mame.rom_scanner import RomScanner, _as_int, _get_value, _normalize_hash, _normalize_name
from app.core.models.scan_result import RomScanResult, ScanStatus

logger = logging.getLogger(__name__)


class PersistentRomScanner(RomScanner):
    """RomScanner que usa índice SQLite persistente para busca alternativa.

    O índice é invalidado por arquivo quando o caminho, tamanho ou mtime do
    ZIP muda. Arquivos removidos deixam de participar das consultas.
    """

    def __init__(
        self,
        rom_paths: Iterable[str | Path],
        *,
        index_path: str | Path | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(rom_paths, **kwargs)
        self.index_path = Path(index_path or "data/database/scan/rom_source_index.sqlite3")
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_lock = threading.RLock()
        self._index_ready = False
        self._prepare_database()

    def _connect(self) -> sqlite3.Connection:
        """Abre a conexão SQLite configurada para consultas concorrentes."""
        connection = sqlite3.connect(self.index_path, timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA temp_store=MEMORY")
        return connection

    def _prepare_database(self) -> None:
        """Cria a estrutura persistente do índice sem varrer o HDD."""
        with self._db_lock, self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS archive_files (
                    path TEXT PRIMARY KEY,
                    size INTEGER NOT NULL,
                    mtime_ns INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rom_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL,
                    member_name TEXT NOT NULL,
                    crc TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    UNIQUE(path, member_name)
                );
                CREATE INDEX IF NOT EXISTS idx_rom_entries_crc_size
                    ON rom_entries(crc, size);
                CREATE INDEX IF NOT EXISTS idx_rom_entries_path
                    ON rom_entries(path);
                """
            )

    def build_archive_index(self, force: bool = False) -> int:
        """Atualiza o índice SQLite somente para ZIPs novos ou modificados.

        Diferentemente do índice anterior, uma execução futura não precisa
        reabrir todos os ZIPs: somente arquivos cujo tamanho/mtime mudou são
        reindexados. O método retorna o total de membros atualmente indexados.
        """
        with self._db_lock:
            self._prepare_database()
            indexed_now = 0
            seen: set[str] = set()

            with self._connect() as db:
                for base in self.rom_paths:
                    if self.cancelled or not base.exists() or not base.is_dir():
                        continue
                    try:
                        candidates = base.rglob("*.zip")
                    except OSError as exc:
                        self._log("Erro enumerando ZIPs em %s: %s", base, exc, level=logging.WARNING)
                        continue

                    for zip_path in candidates:
                        if self.cancelled:
                            break
                        key = os.path.normcase(os.path.abspath(str(zip_path)))
                        if key in seen:
                            continue
                        seen.add(key)
                        try:
                            stat = zip_path.stat()
                            size = int(stat.st_size)
                            mtime_ns = int(stat.st_mtime_ns)
                        except OSError:
                            continue

                        row = db.execute(
                            "SELECT size, mtime_ns FROM archive_files WHERE path = ?",
                            (key,),
                        ).fetchone()
                        if not force and row == (size, mtime_ns):
                            continue

                        db.execute("DELETE FROM rom_entries WHERE path = ?", (key,))
                        try:
                            with zipfile.ZipFile(zip_path, "r") as archive:
                                rows = []
                                for info in archive.infolist():
                                    if info.is_dir():
                                        continue
                                    rows.append((
                                        key,
                                        info.filename,
                                        f"{info.CRC & 0xffffffff:08x}",
                                        int(info.file_size),
                                    ))
                                db.executemany(
                                    "INSERT OR REPLACE INTO rom_entries(path, member_name, crc, size) VALUES (?, ?, ?, ?)",
                                    rows,
                                )
                                indexed_now += len(rows)
                            db.execute(
                                "INSERT OR REPLACE INTO archive_files(path, size, mtime_ns) VALUES (?, ?, ?)",
                                (key, size, mtime_ns),
                            )
                        except (zipfile.BadZipFile, OSError) as exc:
                            self._log("ZIP ignorado no índice: %s | %s", zip_path, exc, level=logging.WARNING)

                # Remove entradas de ZIPs que já não existem nas origens.
                if seen:
                    placeholders = ",".join("?" for _ in seen)
                    db.execute(f"DELETE FROM rom_entries WHERE path NOT IN ({placeholders})", tuple(seen))
                    db.execute(f"DELETE FROM archive_files WHERE path NOT IN ({placeholders})", tuple(seen))
                db.commit()

                total = int(db.execute("SELECT COUNT(*) FROM rom_entries").fetchone()[0])

            self._index_ready = True
            self._log(
                "Índice persistente concluído: %d membros atuais; %d membros reindexados.",
                total,
                indexed_now,
            )
            return total

    def _find_indexed_zip_rom(self, machine_name: str, rom: Any) -> RomScanResult | None:
        """Consulta candidatos por CRC+tamanho sem varrer o índice em memória."""
        expected_crc = _normalize_hash(_get_value(rom, "crc", ""))
        expected_size = _as_int(_get_value(rom, "size", 0))
        rom_name = _normalize_name(_get_value(rom, "name", ""))
        if not expected_crc or expected_size <= 0:
            return None

        if not self._index_ready:
            self.build_archive_index()

        with self._db_lock, self._connect() as db:
            candidates = db.execute(
                "SELECT path, member_name FROM rom_entries WHERE crc = ? AND size = ? ORDER BY path, member_name",
                (expected_crc, expected_size),
            ).fetchall()

        for path_value, member_name in candidates:
            if self.cancelled:
                return None
            zip_path = Path(path_value)
            result = self._scan_zip_entry(zip_path, machine_name, rom, member_name)
            if result is not None and result.status == ScanStatus.VALID:
                result.message = "ROM encontrada e válida em ZIP alternativo (índice persistente)."
                return result

        return None

    def clear_archive_index(self) -> None:
        """Remove o índice persistente para forçar reconstrução na próxima consulta."""
        with self._db_lock:
            if self.index_path.exists():
                try:
                    self.index_path.unlink()
                except OSError as exc:
                    logger.warning("Não foi possível remover índice persistente: %s", exc)
            self._index_ready = False
            super().clear_archive_index()
