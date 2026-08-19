"""Scanner físico de ROMs e CHDs MAME orientado a conteúdo.

ROMs são indexadas por CRC/tamanho e validadas por SHA-1 quando disponível.
CHDs são tratados separadamente: são arquivos externos aos ZIPs e são
localizados em ``<origem>/<machine>/<disk>.chd`` (incluindo a cadeia de
clone/parent quando necessário).
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
import zlib
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

logger = logging.getLogger(__name__)


class PhysicalRomScanner:
    """Indexa fisicamente ROMs e CHDs sem modificar os arquivos de origem."""

    CHUNK_SIZE = 1024 * 1024
    COMMIT_EVERY = 250
    _SCAN_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS rom_scan_run (
        id INTEGER PRIMARY KEY AUTOINCREMENT, dataset_run_id INTEGER,
        source_count INTEGER NOT NULL DEFAULT 0, started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        finished_at TIMESTAMP, status TEXT NOT NULL, archive_count INTEGER NOT NULL DEFAULT 0,
        member_count INTEGER NOT NULL DEFAULT 0, loose_file_count INTEGER NOT NULL DEFAULT 0,
        bytes_read INTEGER NOT NULL DEFAULT 0, valid_match_count INTEGER NOT NULL DEFAULT 0,
        unmatched_count INTEGER NOT NULL DEFAULT 0, error TEXT
    );
    CREATE TABLE IF NOT EXISTS rom_source_match (
        id INTEGER PRIMARY KEY AUTOINCREMENT, dataset_run_id INTEGER, scan_run_id INTEGER,
        rom_id INTEGER, source_path TEXT NOT NULL, archive_member TEXT, source_kind TEXT NOT NULL,
        actual_size INTEGER NOT NULL, actual_crc TEXT NOT NULL, actual_sha1 TEXT,
        validation_status TEXT NOT NULL, bytes_read INTEGER NOT NULL DEFAULT 0,
        checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, error TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_run ON rom_source_match(dataset_run_id);
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_scan_run ON rom_source_match(scan_run_id);
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_rom ON rom_source_match(rom_id);
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_hash ON rom_source_match(actual_crc, actual_size);
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_sha1 ON rom_source_match(actual_sha1);
    """

    def __init__(self, db, source_dirs: Iterable[Path | str]) -> None:
        self.db = db
        self.source_dirs = [Path(p).expanduser() for p in source_dirs]
        self._cancel_requested = False
        self.last_scan_id: int | None = None
        self.last_stats: dict = {}
        self._chd_results: dict[tuple[str, str], dict] = {}

    def cancel(self) -> None:
        """Solicita cancelamento no próximo ponto seguro de leitura."""
        self._cancel_requested = True

    @property
    def cancelled(self) -> bool:
        """Retorna se o scan foi cancelado."""
        return self._cancel_requested

    def scan(
        self,
        machine_names: Iterable[str] | None = None,
        run_id: int | None = None,
        progress: Callable[[int, str], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
        machine_disks: dict[str, list[dict]] | None = None,
    ) -> dict:
        """Executa o inventário físico de ROMs e CHDs esperados."""
        conn = self._connection()
        self._ensure_scan_tables(conn)
        self._validate_sources()
        self._cancel_requested = False
        self._chd_results.clear()

        names = [str(n).strip() for n in (machine_names or []) if str(n).strip()]
        expected = self._build_expected_index(names)
        started = time.monotonic()
        conn.execute(
            "INSERT INTO rom_scan_run (dataset_run_id, source_count, status) VALUES (?, ?, 'running')",
            (run_id, len(self.source_dirs)),
        )
        scan_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.last_scan_id = scan_id
        conn.commit()

        stats = {
            "scan_id": scan_id,
            "dataset_run_id": run_id,
            "expected_roms": sum(len(v) for v in expected.values()),
            "expected_chds": sum(len(v) for v in (machine_disks or {}).values()),
            "archives": 0,
            "members": 0,
            "loose": 0,
            "chds": 0,
            "chds_valid": 0,
            "chds_missing": 0,
            "chds_invalid": 0,
            "chds_errors": 0,
            "bytes_read": 0,
            "valid": 0,
            "sha1_mismatch": 0,
            "unmatched": 0,
            "read_errors": 0,
            "seconds": 0.0,
            "status": "running",
        }
        pending = 0

        logger.info(
            "Scan físico iniciado: %d ROMs e %d CHDs esperados, %d origem(ns).",
            stats["expected_roms"], stats["expected_chds"], len(self.source_dirs),
        )

        try:
            for root in self.source_dirs:
                self._check_cancelled(cancelled)
                logger.info("Origem física: %s", root)
                if progress:
                    progress(stats["members"], f"Lendo origem: {root}")

                for path in root.rglob("*"):
                    self._check_cancelled(cancelled)
                    if not path.is_file():
                        continue
                    # CHDs não participam do índice global de ROMs.
                    if path.suffix.lower() == ".chd":
                        continue
                    if path.suffix.lower() == ".zip":
                        unit = self._scan_zip(path, expected, scan_id, cancelled)
                        stats["archives"] += 1
                    else:
                        unit = self._scan_loose(path, expected, scan_id, cancelled)
                        stats["loose"] += 1
                    for key in ("members", "bytes_read", "valid", "sha1_mismatch", "unmatched", "read_errors"):
                        stats[key] += unit[key]
                    pending += unit["records"]
                    if pending >= self.COMMIT_EVERY:
                        conn.commit()
                        pending = 0
                    if progress:
                        progress(stats["members"], self._progress_message(stats, path))

            # CHDs são processados por expectativa, não por varredura global.
            for machine_name, disks in (machine_disks or {}).items():
                for disk in disks:
                    self._check_cancelled(cancelled)
                    stats["chds"] += 1
                    result = self._scan_expected_chd(machine_name, disk, machine_disks, cancelled)
                    self._chd_results[(machine_name, str(disk.get("name") or ""))] = result
                    stats["bytes_read"] += int(result.get("actual_size") or 0)
                    status = result.get("status")
                    if status == "valid":
                        stats["chds_valid"] += 1
                    elif status == "missing":
                        stats["chds_missing"] += 1
                    elif status == "invalid":
                        stats["chds_invalid"] += 1
                    else:
                        stats["chds_errors"] += 1
                    if progress:
                        progress(stats["members"], self._progress_message(stats, Path(result.get("source_path") or machine_name)))

            conn.commit()
            stats["seconds"] = round(time.monotonic() - started, 2)
            stats["status"] = "completed"
            self._finish_run(conn, scan_id, stats)
            self.last_stats = stats
            logger.info(
                "Scan físico concluído: archives=%d members=%d loose=%d chds=%d/%d válidos bytes=%d valid=%d sha1_mismatch=%d unmatched=%d errors=%d tempo=%.2fs",
                stats["archives"], stats["members"], stats["loose"], stats["chds"],
                stats["chds_valid"], stats["bytes_read"], stats["valid"],
                stats["sha1_mismatch"], stats["unmatched"], stats["read_errors"], stats["seconds"],
            )
            return stats
        except Exception as exc:
            conn.rollback()
            stats["seconds"] = round(time.monotonic() - started, 2)
            stats["status"] = "cancelled" if str(exc) == "Operação cancelada." else "failed"
            self._finish_run(conn, scan_id, stats, str(exc))
            self.last_stats = stats
            if stats["status"] == "cancelled":
                logger.info("Scan físico cancelado pelo usuário.")
                return stats
            logger.exception("Falha no scan físico.")
            raise

    def _build_expected_index(self, machine_names: Iterable[str] | None) -> dict[tuple[str, int], list[dict]]:
        """Cria índice CRC+tamanho limitado às machines selecionadas."""
        index: dict[tuple[str, int], list[dict]] = {}
        names = [str(n).strip() for n in (machine_names or []) if str(n).strip()]
        if names:
            placeholders = ",".join("?" for _ in names)
            rows = self.db.fetchall(
                f"""SELECT r.id, r.machine_id, r.name, r.size, r.crc, r.sha1
                FROM rom r JOIN machine m ON m.id=r.machine_id
                WHERE m.name IN ({placeholders}) AND r.crc IS NOT NULL
                AND TRIM(r.crc) <> '' AND r.size IS NOT NULL AND r.size >= 0""",
                names,
            )
        else:
            rows = self.db.fetchall(
                "SELECT id, machine_id, name, size, crc, sha1 FROM rom "
                "WHERE crc IS NOT NULL AND TRIM(crc) <> '' AND size IS NOT NULL AND size >= 0"
            )
        for row in rows:
            crc = str(row["crc"]).strip().lower()
            size = int(row["size"] or 0)
            index.setdefault((crc, size), []).append({
                "rom_id": int(row["id"]),
                "machine_id": int(row["machine_id"]),
                "name": str(row["name"]),
                "sha1": str(row["sha1"] or "").strip().lower(),
            })
        return index

    def _scan_zip(self, path: Path, expected: dict[tuple[str, int], list[dict]], scan_id: int, cancelled: Callable[[], bool] | None) -> dict:
        """Abre um ZIP uma única vez e lê cada membro em streaming."""
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
                            size, crc, sha1 = self._hash_stream(stream, cancelled)
                    except (OSError, EOFError, RuntimeError, zipfile.BadZipFile) as exc:
                        result["read_errors"] += 1
                        self._record(scan_id, None, path, info.filename, "zip", 0, "", "", "read_error", 0, str(exc))
                        result["records"] += 1
                        continue
                    result["bytes_read"] += size
                    result["records"] += self._record_matches(
                        scan_id, path, info.filename, "zip", size, crc, sha1,
                        expected.get((crc, size), []), result,
                    )
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            result["read_errors"] += 1
            self._record(scan_id, None, path, None, "zip", 0, "", "", "archive_error", 0, str(exc))
            result["records"] += 1
        return result

    def _scan_loose(self, path: Path, expected: dict[tuple[str, int], list[dict]], scan_id: int, cancelled: Callable[[], bool] | None) -> dict:
        """Lê um arquivo solto em streaming."""
        result = self._empty_result()
        try:
            size, crc, sha1 = self._hash_file(path, cancelled)
        except (OSError, RuntimeError) as exc:
            result["read_errors"] = 1
            self._record(scan_id, None, path, None, "loose", 0, "", "", "read_error", 0, str(exc))
            result["records"] = 1
            return result
        result["members"] = 1
        result["bytes_read"] = size
        result["records"] = self._record_matches(
            scan_id, path, None, "loose", size, crc, sha1,
            expected.get((crc, size), []), result,
        )
        return result

    def _scan_expected_chd(self, machine_name: str, disk: dict, machine_disks: dict[str, list[dict]], cancelled: Callable[[], bool] | None) -> dict:
        """Localiza e valida um CHD esperado sem varrer CHDs não relacionados."""
        disk_name = str(disk.get("name") or "").strip()
        expected_sha1 = str(disk.get("sha1") or "").strip().lower()
        expected_size = int(disk.get("size") or 0)
        if not disk_name:
            return {"status": "error", "source_path": None, "actual_size": 0, "actual_sha1": None, "error": "CHD sem nome"}

        disk_filename = disk_name if disk_name.lower().endswith(".chd") else f"{disk_name}.chd"
        candidates: list[Path] = []
        machine_meta = machine_disks.get(machine_name, [])
        # O caller pode fornecer um campo _cloneof/_parents sem alterar o formato público.
        parent_names = list(disk.get("_parent_machines") or [])
        for base in self.source_dirs:
            for candidate_machine in [machine_name, *parent_names]:
                if candidate_machine:
                    candidates.append(base / candidate_machine / disk_filename)
            candidates.append(base / disk_filename)

        found = next((p for p in candidates if p.is_file()), None)
        if found is None:
            return {"status": "missing", "source_path": None, "actual_size": 0, "actual_sha1": None, "error": "CHD não encontrado"}

        try:
            self._check_cancelled(cancelled)
            actual_size, _crc, actual_sha1 = self._hash_file(found, cancelled)
            valid = (expected_size <= 0 or actual_size == expected_size) and (not expected_sha1 or actual_sha1 == expected_sha1)
            return {
                "status": "valid" if valid else "invalid",
                "source_path": str(found),
                "actual_size": actual_size,
                "actual_sha1": actual_sha1,
                "error": None if valid else "tamanho ou SHA-1 incompatível",
            }
        except Exception as exc:
            return {"status": "error", "source_path": str(found), "actual_size": 0, "actual_sha1": None, "error": str(exc)}

    def _hash_file(self, path: Path, cancelled: Callable[[], bool] | None = None) -> tuple[int, str, str]:
        with path.open("rb") as stream:
            return self._hash_stream(stream, cancelled)

    def _hash_stream(self, stream, cancelled: Callable[[], bool] | None = None) -> tuple[int, str, str]:
        """Calcula CRC32 e SHA1 sobre os bytes efetivamente lidos."""
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

    def _record_matches(self, scan_id: int, source_path: Path, archive_member: str | None, source_kind: str, size: int, crc: str, sha1: str, candidates: list[dict], result: dict) -> int:
        """Relaciona o conteúdo físico com todas as ROMs compatíveis."""
        if not candidates:
            self._record(scan_id, None, source_path, archive_member, source_kind, size, crc, sha1, "unmatched", size, None)
            result["unmatched"] += 1
            return 1
        records = 0
        for candidate in candidates:
            status = "sha1_mismatch" if candidate["sha1"] and candidate["sha1"] != sha1 else "valid"
            if status == "valid":
                result["valid"] += 1
            else:
                result["sha1_mismatch"] += 1
            self._record(scan_id, candidate["rom_id"], source_path, archive_member, source_kind, size, crc, sha1, status, size, None)
            records += 1
        return records

    def _record(self, scan_id: int, rom_id: int | None, source_path: Path, archive_member: str | None, source_kind: str, size: int, crc: str, sha1: str, status: str, bytes_read: int, error: str | None) -> None:
        """Persiste uma evidência de ROM no banco."""
        self._connection().execute(
            """INSERT INTO rom_source_match (dataset_run_id, scan_run_id, rom_id, source_path, archive_member, source_kind, actual_size, actual_crc, actual_sha1, validation_status, bytes_read, checked_at, error)
            SELECT dataset_run_id, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?
            FROM rom_scan_run WHERE id=?""",
            (scan_id, rom_id, str(source_path), archive_member, source_kind, size, crc, sha1, status, bytes_read, error, scan_id),
        )

    def write_manifest(self, xml_machines: list[dict], xml_path: Path, output_path: Path, mame_version: str, source_paths: Iterable[Path | str]) -> Path:
        """Gera ``current_scan.jsonl`` incluindo registros explícitos de CHD."""
        if not self.last_scan_id:
            raise RuntimeError("Nenhum scan físico foi executado.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        header = {
            "record_type": "header",
            "schema_version": 3,
            "scan_id": f"physical_{self.last_scan_id}",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "mame_version": mame_version,
            "xml_path": str(xml_path),
            "source_paths": [str(Path(p)) for p in source_paths],
            "machine_count_expected": len(xml_machines),
            "metadata": {
                "validation": "physical_stream_crc32_sha1_size",
                "bytes_read": self.last_stats.get("bytes_read", 0),
                "chds_scanned": self.last_stats.get("chds", 0),
                "chds_valid": self.last_stats.get("chds_valid", 0),
            },
        }
        with output_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(header, ensure_ascii=False) + "\n")
            for machine in xml_machines:
                name = machine["name"]
                disks = machine.get("disks", [])
                meta = {
                    "name": name,
                    "description": machine.get("description", ""),
                    "cloneof": machine.get("cloneof"),
                    "rom_count": len(machine.get("roms", [])) + len(disks),
                }
                handle.write(json.dumps({"record_type": "machine", "event": "started", "machine": {**meta, "status": "scanned"}}, ensure_ascii=False) + "\n")

                for rom in machine.get("roms", []):
                    # ROM match é obtido do banco físico.
                    row = self._latest_rom_match(name, rom["name"])
                    record = {
                        "machine": name,
                        "machine_description": machine.get("description", ""),
                        "rom_name": rom["name"],
                        "expected_size": rom.get("size", 0),
                        "expected_crc": rom.get("crc", ""),
                        "expected_sha1": rom.get("sha1", ""),
                        "merge": rom.get("merge"),
                        "required": not bool(rom.get("optional")),
                        "optional": bool(rom.get("optional")),
                        "status": "missing" if row is None else row["validation_status"],
                        "actual_size": 0 if row is None else row["actual_size"],
                        "actual_crc": None if row is None else row["actual_crc"],
                        "actual_sha1": None if row is None else row["actual_sha1"],
                        "source": None if row is None else {"kind": row["source_kind"], "archive": row["source_path"], "member": row["archive_member"], "machine": name},
                        "error": None if row is None else row["error"],
                    }
                    handle.write(json.dumps({"record_type": "rom", "record": record}, ensure_ascii=False) + "\n")

                for disk in disks:
                    disk_name = str(disk.get("name") or "")
                    chd = self._chd_results.get((name, disk_name), {})
                    record = {
                        "machine": name,
                        "machine_description": machine.get("description", ""),
                        "disk_name": disk_name,
                        "expected_size": int(disk.get("size") or 0),
                        "expected_sha1": str(disk.get("sha1") or "").lower(),
                        "merge": disk.get("merge"),
                        "required": not bool(disk.get("optional")),
                        "optional": bool(disk.get("optional")),
                        "status": chd.get("status", "missing"),
                        "actual_size": chd.get("actual_size") or 0,
                        "actual_sha1": chd.get("actual_sha1"),
                        "source": {
                            "kind": "chd",
                            "archive": chd.get("source_path"),
                            "member": None,
                            "machine": name,
                        } if chd.get("source_path") else None,
                        "error": chd.get("error"),
                    }
                    handle.write(json.dumps({"record_type": "disk", "record": record}, ensure_ascii=False) + "\n")

                handle.write(json.dumps({"record_type": "machine", "event": "finished", "machine": {**meta, "status": "completed"}}, ensure_ascii=False) + "\n")
        return output_path

    def _latest_rom_match(self, machine_name: str, rom_name: str):
        """Obtém a melhor evidência física de uma ROM para o manifesto."""
        row = self._connection().execute(
            """SELECT s.source_path, s.archive_member, s.source_kind, s.actual_size, s.actual_crc, s.actual_sha1, s.validation_status, s.error
            FROM rom_source_match s JOIN rom r ON r.id=s.rom_id JOIN machine m ON m.id=r.machine_id
            WHERE s.scan_run_id=? AND m.name=? AND r.name=?
            ORDER BY CASE s.validation_status WHEN 'valid' THEN 0 WHEN 'sha1_mismatch' THEN 1 ELSE 2 END, s.id DESC LIMIT 1""",
            (self.last_scan_id, machine_name, rom_name),
        ).fetchone()
        return row

    def _validate_sources(self) -> None:
        """Valida as origens configuradas."""
        if not self.source_dirs:
            raise RuntimeError("Nenhuma origem física de ROM foi configurada.")
        for path in self.source_dirs:
            if not path.is_dir():
                raise FileNotFoundError(f"Origem física não encontrada: {path}")

    def _ensure_scan_tables(self, conn: sqlite3.Connection) -> None:
        """Cria as tabelas auxiliares do scan se necessário."""
        conn.executescript(self._SCAN_TABLE_SQL)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(rom_source_match)").fetchall()}
        if "scan_run_id" not in columns:
            conn.execute("ALTER TABLE rom_source_match ADD COLUMN scan_run_id INTEGER")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rom_source_match_scan_run ON rom_source_match(scan_run_id)")
        conn.commit()

    def _finish_run(self, conn: sqlite3.Connection, scan_id: int, stats: dict, error: str | None = None) -> None:
        """Finaliza o registro do scan físico."""
        conn.execute(
            "UPDATE rom_scan_run SET finished_at=CURRENT_TIMESTAMP, status=?, archive_count=?, member_count=?, loose_file_count=?, bytes_read=?, valid_match_count=?, unmatched_count=?, error=? WHERE id=?",
            (stats["status"], stats["archives"], stats["members"], stats["loose"], stats["bytes_read"], stats["valid"], stats["unmatched"] + stats["sha1_mismatch"] + stats["read_errors"] + stats.get("chds_missing", 0) + stats.get("chds_invalid", 0) + stats.get("chds_errors", 0), error, scan_id),
        )
        conn.commit()

    def _connection(self) -> sqlite3.Connection:
        """Retorna a conexão SQLite do projeto."""
        if self.db.conn is None:
            self.db.connect()
        assert self.db.conn is not None
        return self.db.conn

    @staticmethod
    def _empty_result() -> dict:
        """Cria contadores para uma unidade de leitura."""
        return {"members": 0, "bytes_read": 0, "valid": 0, "sha1_mismatch": 0, "unmatched": 0, "read_errors": 0, "records": 0}

    def _check_cancelled(self, cancelled: Callable[[], bool] | None) -> None:
        """Interrompe a operação quando solicitado."""
        if self._cancel_requested or (cancelled and cancelled()):
            raise RuntimeError("Operação cancelada.")

    @staticmethod
    def _progress_message(stats: dict, path: Path) -> str:
        """Formata o progresso do scan físico."""
        return (
            f"{path.name} | membros {stats['members']:,} | "
            f"válidas {stats['valid']:,} | CHDs {stats.get('chds_valid', 0):,}/{stats.get('chds', 0):,} válidos | "
            f"SHA1 divergente {stats['sha1_mismatch']:,} | não correspondentes {stats['unmatched']:,} | "
            f"erros {stats['read_errors']:,} | bytes lidos {stats['bytes_read']:,}"
        )
