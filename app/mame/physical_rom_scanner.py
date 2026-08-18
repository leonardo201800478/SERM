"""Scanner físico orientado a conteúdo para ROMs MAME.

O scanner trabalha sobre a origem em modo somente leitura. ZIPs são abertos
uma única vez e cada membro é descompactado/lido em streaming. A identidade
do conteúdo é determinada por tamanho + CRC32 + SHA1 calculados sobre os
bytes reais; o CRC armazenado no cabeçalho do ZIP nunca é usado sozinho.

O scanner é deliberadamente independente do nome do arquivo. Um conteúdo
físico pode corresponder a várias entradas do LISTXML (por exemplo, ROMs
compartilhadas por parent/clone) e todas as relações são registradas no
índice ``rom_source_match``.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import time
import zlib
import zipfile
from pathlib import Path
from typing import Callable, Iterable

logger = logging.getLogger(__name__)


class PhysicalRomScanner:
    """Indexa e valida fisicamente ROMs sem modificar a origem."""

    CHUNK_SIZE = 1024 * 1024
    COMMIT_EVERY = 250

    _SCAN_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS rom_scan_run (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dataset_run_id INTEGER,
        source_count INTEGER NOT NULL DEFAULT 0,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        finished_at TIMESTAMP,
        status TEXT NOT NULL,
        archive_count INTEGER NOT NULL DEFAULT 0,
        member_count INTEGER NOT NULL DEFAULT 0,
        loose_file_count INTEGER NOT NULL DEFAULT 0,
        bytes_read INTEGER NOT NULL DEFAULT 0,
        valid_match_count INTEGER NOT NULL DEFAULT 0,
        unmatched_count INTEGER NOT NULL DEFAULT 0,
        error TEXT
    );

    CREATE TABLE IF NOT EXISTS rom_source_match (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dataset_run_id INTEGER,
        rom_id INTEGER,
        source_path TEXT NOT NULL,
        archive_member TEXT,
        source_kind TEXT NOT NULL,
        actual_size INTEGER NOT NULL,
        actual_crc TEXT NOT NULL,
        actual_sha1 TEXT,
        validation_status TEXT NOT NULL,
        bytes_read INTEGER NOT NULL DEFAULT 0,
        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        error TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_rom_source_match_run
        ON rom_source_match(dataset_run_id);
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_rom
        ON rom_source_match(rom_id);
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_hash
        ON rom_source_match(actual_crc, actual_size);
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_sha1
        ON rom_source_match(actual_sha1);
    """

    def __init__(
        self,
        db,
        source_dirs: Iterable[Path | str],
    ) -> None:
        """Inicializa o scanner.

        Args:
            db: instância do ``Database`` da aplicação.
            source_dirs: diretórios físicos que serão lidos somente para
                leitura.
        """
        self.db = db
        self.source_dirs = [Path(path) for path in source_dirs]

    # ------------------------------------------------------------------
    # API PÚBLICA
    # ------------------------------------------------------------------

    def scan(
        self,
        run_id: int | None = None,
        progress: Callable[[int, str], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> dict:
        """Executa o inventário físico completo.

        Cada arquivo é lido em streaming. ZIPs são abertos uma única vez e
        cada membro é efetivamente descompactado. O scanner nunca extrai
        arquivos para disco e nunca escreve na origem.

        ``run_id`` é o identificador do dataset lógico que originou o
        catálogo. Ele é opcional para permitir testes e scans independentes.

        Returns:
            Dicionário com estatísticas verificáveis do scan.
        """
        conn = self._connection()
        self._ensure_scan_tables(conn)

        expected = self._build_expected_index()
        started = time.monotonic()

        conn.execute(
            """
            INSERT INTO rom_scan_run
                (dataset_run_id, source_count, status)
            VALUES (?, ?, 'running')
            """,
            (run_id, len(self.source_dirs)),
        )
        scan_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.commit()

        stats = {
            "scan_id": scan_id,
            "dataset_run_id": run_id,
            "archives": 0,
            "members": 0,
            "loose": 0,
            "bytes_read": 0,
            "valid": 0,
            "sha1_mismatch": 0,
            "unmatched": 0,
            "read_errors": 0,
            "seconds": 0.0,
        }
        pending = 0

        logger.info(
            "Scan físico iniciado: %d ROMs esperadas, %d origem(ns).",
            len(expected),
            len(self.source_dirs),
        )

        try:
            for root in self.source_dirs:
                self._check_cancelled(cancelled)

                if not root.is_dir():
                    logger.warning("Origem física inexistente: %s", root)
                    continue

                logger.info("Origem física: %s", root)

                for path in root.rglob("*"):
                    self._check_cancelled(cancelled)

                    if not path.is_file():
                        continue

                    suffix = path.suffix.lower()

                    if suffix == ".zip":
                        result = self._scan_zip(
                            path,
                            expected,
                            scan_id,
                            cancelled,
                        )
                        stats["archives"] += 1
                    elif suffix == ".chd":
                        # CHDs pertencem ao scanner específico de CHD.
                        continue
                    else:
                        result = self._scan_loose(
                            path,
                            expected,
                            scan_id,
                            cancelled,
                        )
                        stats["loose"] += 1

                    stats["members"] += result["members"]
                    stats["bytes_read"] += result["bytes_read"]
                    stats["valid"] += result["valid"]
                    stats["sha1_mismatch"] += result["sha1_mismatch"]
                    stats["unmatched"] += result["unmatched"]
                    stats["read_errors"] += result["read_errors"]
                    pending += result["records"]

                    if pending >= self.COMMIT_EVERY:
                        conn.commit()
                        pending = 0

                    if progress:
                        progress(
                            stats["members"] + stats["loose"],
                            self._progress_message(stats),
                        )

            conn.commit()

            stats["seconds"] = round(time.monotonic() - started, 2)
            stats["status"] = "completed"

            conn.execute(
                """
                UPDATE rom_scan_run
                   SET finished_at=CURRENT_TIMESTAMP,
                       status='completed',
                       archive_count=?,
                       member_count=?,
                       loose_file_count=?,
                       bytes_read=?,
                       valid_match_count=?,
                       unmatched_count=?,
                       error=NULL
                 WHERE id=?
                """,
                (
                    stats["archives"],
                    stats["members"],
                    stats["loose"],
                    stats["bytes_read"],
                    stats["valid"],
                    stats["unmatched"] + stats["sha1_mismatch"] + stats["read_errors"],
                    scan_id,
                ),
            )
            conn.commit()

            logger.info(
                "Scan físico concluído: archives=%d members=%d loose=%d "
                "bytes=%d valid=%d sha1_mismatch=%d unmatched=%d errors=%d "
                "tempo=%.2fs",
                stats["archives"],
                stats["members"],
                stats["loose"],
                stats["bytes_read"],
                stats["valid"],
                stats["sha1_mismatch"],
                stats["unmatched"],
                stats["read_errors"],
                stats["seconds"],
            )

            return stats

        except Exception as exc:
            conn.rollback()
            stats["seconds"] = round(time.monotonic() - started, 2)
            stats["status"] = "cancelled" if str(exc) == "Operação cancelada." else "failed"

            conn.execute(
                """
                UPDATE rom_scan_run
                   SET finished_at=CURRENT_TIMESTAMP,
                       status=?,
                       archive_count=?,
                       member_count=?,
                       loose_file_count=?,
                       bytes_read=?,
                       valid_match_count=?,
                       unmatched_count=?,
                       error=?
                 WHERE id=?
                """,
                (
                    stats["status"],
                    stats["archives"],
                    stats["members"],
                    stats["loose"],
                    stats["bytes_read"],
                    stats["valid"],
                    stats["unmatched"] + stats["sha1_mismatch"] + stats["read_errors"],
                    str(exc),
                    scan_id,
                ),
            )
            conn.commit()
            logger.exception("Falha no scan físico.")
            raise

    # ------------------------------------------------------------------
    # CATÁLOGO ESPERADO
    # ------------------------------------------------------------------

    def _build_expected_index(self) -> dict[tuple[str, int], list[dict]]:
        """Constrói índice ``(CRC, tamanho) -> ROMs esperadas``.

        O índice é mantido em memória somente como metadado: IDs, hashes e
        nomes. O conteúdo das ROMs nunca é carregado para RAM.
        """
        index: dict[tuple[str, int], list[dict]] = {}

        rows = self.db.fetchall(
            """
            SELECT id, machine_id, name, size, crc, sha1
              FROM rom
             WHERE crc IS NOT NULL
               AND TRIM(crc) <> ''
               AND size IS NOT NULL
               AND size >= 0
            """
        )

        for row in rows:
            crc = str(row["crc"]).strip().lower()
            sha1 = str(row["sha1"] or "").strip().lower()
            size = int(row["size"] or 0)

            index.setdefault((crc, size), []).append(
                {
                    "rom_id": int(row["id"]),
                    "machine_id": int(row["machine_id"]),
                    "name": str(row["name"]),
                    "sha1": sha1,
                }
            )

        return index

    # ------------------------------------------------------------------
    # ZIP
    # ------------------------------------------------------------------

    def _scan_zip(
        self,
        path: Path,
        expected: dict[tuple[str, int], list[dict]],
        scan_id: int,
        cancelled: Callable[[], bool] | None,
    ) -> dict:
        """Lê todos os membros de um ZIP uma única vez.

        ``zipfile`` verifica o CRC armazenado no próprio ZIP enquanto o
        membro é lido. Independentemente disso, calculamos novamente CRC32,
        SHA1 e tamanho sobre os bytes descompactados.
        """
        result = self._empty_result()

        try:
            with zipfile.ZipFile(path, "r") as archive:
                for info in archive.infolist():
                    self._check_cancelled(cancelled)

                    if info.is_dir():
                        continue

                    result["members"] += 1

                    try:
                        with archive.open(info, "r") as stream:
                            size, crc, sha1 = self._hash_stream(stream)
                    except (OSError, EOFError, RuntimeError, zipfile.BadZipFile) as exc:
                        result["read_errors"] += 1
                        self._record(
                            scan_id=scan_id,
                            rom_id=None,
                            source_path=path,
                            archive_member=info.filename,
                            source_kind="zip",
                            size=0,
                            crc="",
                            sha1="",
                            status="read_error",
                            bytes_read=0,
                            error=str(exc),
                        )
                        result["records"] += 1
                        continue

                    result["bytes_read"] += size
                    result["records"] += self._record_matches(
                        scan_id,
                        path,
                        info.filename,
                        "zip",
                        size,
                        crc,
                        sha1,
                        expected.get((crc, size), []),
                        result,
                    )

        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            logger.warning("ZIP ilegível: %s: %s", path, exc)
            result["read_errors"] += 1
            self._record(
                scan_id=scan_id,
                rom_id=None,
                source_path=path,
                archive_member=None,
                source_kind="zip",
                size=0,
                crc="",
                sha1="",
                status="archive_error",
                bytes_read=0,
                error=str(exc),
            )
            result["records"] += 1

        return result

    # ------------------------------------------------------------------
    # ARQUIVOS SOLTOS
    # ------------------------------------------------------------------

    def _scan_loose(
        self,
        path: Path,
        expected: dict[tuple[str, int], list[dict]],
        scan_id: int,
        cancelled: Callable[[], bool] | None,
    ) -> dict:
        """Lê um arquivo solto integralmente em streaming."""
        result = self._empty_result()
        self._check_cancelled(cancelled)

        try:
            size, crc, sha1 = self._hash_file(path, cancelled)
        except (OSError, RuntimeError) as exc:
            result["read_errors"] = 1
            self._record(
                scan_id=scan_id,
                rom_id=None,
                source_path=path,
                archive_member=None,
                source_kind="loose",
                size=0,
                crc="",
                sha1="",
                status="read_error",
                bytes_read=0,
                error=str(exc),
            )
            result["records"] = 1
            return result

        result["members"] = 1
        result["bytes_read"] = size
        result["records"] = self._record_matches(
            scan_id,
            path,
            None,
            "loose",
            size,
            crc,
            sha1,
            expected.get((crc, size), []),
            result,
        )
        return result

    # ------------------------------------------------------------------
    # HASH
    # ------------------------------------------------------------------

    def _hash_file(
        self,
        path: Path,
        cancelled: Callable[[], bool] | None = None,
    ) -> tuple[int, str, str]:
        """Calcula tamanho, CRC32 e SHA1 de um arquivo sem carregá-lo na RAM."""
        with path.open("rb") as stream:
            return self._hash_stream(stream, cancelled)

    def _hash_stream(
        self,
        stream,
        cancelled: Callable[[], bool] | None = None,
    ) -> tuple[int, str, str]:
        """Calcula hashes dos bytes efetivamente lidos do stream."""
        crc = 0
        sha1 = hashlib.sha1()
        size = 0

        while True:
            self._check_cancelled(cancelled)
            chunk = stream.read(self.CHUNK_SIZE)
            if not chunk:
                break

            size += len(chunk)
            crc = zlib.crc32(chunk, crc)
            sha1.update(chunk)

        return size, f"{crc & 0xFFFFFFFF:08x}", sha1.hexdigest()

    # ------------------------------------------------------------------
    # MATCH / PERSISTÊNCIA
    # ------------------------------------------------------------------

    def _record_matches(
        self,
        scan_id: int,
        source_path: Path,
        archive_member: str | None,
        source_kind: str,
        size: int,
        crc: str,
        sha1: str,
        candidates: list[dict],
        result: dict,
    ) -> int:
        """Registra a relação entre conteúdo físico e catálogo esperado.

        Um membro pode corresponder a várias ROMs do catálogo. Cada relação
        é preservada separadamente para que o reconstruidor possa resolver
        parent/clone e modos Split/Merged/Non-Merged posteriormente.
        """
        if not candidates:
            self._record(
                scan_id,
                None,
                source_path,
                archive_member,
                source_kind,
                size,
                crc,
                sha1,
                "unmatched",
                size,
                None,
            )
            result["unmatched"] += 1
            return 1

        records = 0
        matched = False

        for candidate in candidates:
            expected_sha1 = candidate["sha1"]

            if expected_sha1 and expected_sha1 != sha1:
                status = "sha1_mismatch"
                result["sha1_mismatch"] += 1
            else:
                status = "valid"
                matched = True
                result["valid"] += 1

            self._record(
                scan_id,
                candidate["rom_id"],
                source_path,
                archive_member,
                source_kind,
                size,
                crc,
                sha1,
                status,
                size,
                None,
            )
            records += 1

        if not matched:
            # Não duplica o registro; os candidatos já documentam o motivo.
            pass

        return records

    def _record(
        self,
        scan_id: int,
        rom_id: int | None,
        source_path: Path,
        archive_member: str | None,
        source_kind: str,
        size: int,
        crc: str,
        sha1: str,
        status: str,
        bytes_read: int,
        error: str | None,
    ) -> None:
        """Persiste uma evidência física do scan."""
        conn = self._connection()
        conn.execute(
            """
            INSERT INTO rom_source_match (
                dataset_run_id,
                rom_id,
                source_path,
                archive_member,
                source_kind,
                actual_size,
                actual_crc,
                actual_sha1,
                validation_status,
                bytes_read,
                checked_at,
                error
            )
            SELECT
                dataset_run_id,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?
              FROM rom_scan_run
             WHERE id = ?
            """,
            (
                rom_id,
                str(source_path),
                archive_member,
                source_kind,
                size,
                crc,
                sha1,
                status,
                bytes_read,
                error,
                scan_id,
            ),
        )

    # ------------------------------------------------------------------
    # SCHEMA OPERACIONAL
    # ------------------------------------------------------------------

    def _ensure_scan_tables(self, conn: sqlite3.Connection) -> None:
        """Garante as tabelas operacionais necessárias ao scanner.

        O schema oficial deverá conter essas tabelas nas próximas migrações;
        a criação idempotente aqui mantém o scanner compatível com bancos
        antigos enquanto a migração é aplicada.
        """
        conn.executescript(self._SCAN_TABLE_SQL)
        conn.commit()

    def _connection(self) -> sqlite3.Connection:
        """Retorna a conexão SQLite ativa, conectando quando necessário."""
        if self.db.conn is None:
            self.db.connect()
        assert self.db.conn is not None
        return self.db.conn

    # ------------------------------------------------------------------
    # AUXILIARES
    # ------------------------------------------------------------------

    @staticmethod
    def _empty_result() -> dict:
        """Cria acumulador de estatísticas para uma unidade física."""
        return {
            "members": 0,
            "bytes_read": 0,
            "valid": 0,
            "sha1_mismatch": 0,
            "unmatched": 0,
            "read_errors": 0,
            "records": 0,
        }

    @staticmethod
    def _check_cancelled(cancelled: Callable[[], bool] | None) -> None:
        """Interrompe o scan quando a GUI solicita cancelamento."""
        if cancelled and cancelled():
            raise RuntimeError("Operação cancelada.")

    @staticmethod
    def _progress_message(stats: dict) -> str:
        """Monta uma mensagem objetiva de progresso para a GUI."""
        return (
            "Scan físico: "
            f"{stats['members']:,} arquivos processados | "
            f"válidos {stats['valid']:,} | "
            f"SHA1 divergente {stats['sha1_mismatch']:,} | "
            f"não encontrados no catálogo {stats['unmatched']:,} | "
            f"erros {stats['read_errors']:,} | "
            f"{stats['bytes_read']:,} bytes lidos"
        )
