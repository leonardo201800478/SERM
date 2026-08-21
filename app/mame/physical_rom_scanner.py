"""Scanner físico expected-driven de ROMs e CHDs MAME.

O scanner consulta o LISTXML/banco como fonte de verdade e nunca enumera o
HDD inteiro. Para cada machine verifica somente ``machine.zip``, ``machine/``
e os CHDs diretamente associados à machine.

A persistência operacional ocorre durante o scan: cada machine concluída é
persistida no SQLite e escrita no JSONL por uma fila de resultados. SHA-1 de
ROM só é calculado depois de tamanho+CRC coincidirem. CHD não é lido durante
o scan; sua validação permanece na reconstrução.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
import zlib
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

logger = logging.getLogger(__name__)


class PhysicalRomScanner:
    """Escaneia somente o conteúdo esperado e persiste resultados por machine."""

    CHUNK_SIZE = 1024 * 1024

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
        scan_run_id INTEGER,
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
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_run ON rom_source_match(dataset_run_id);
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_scan_run ON rom_source_match(scan_run_id);
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_rom ON rom_source_match(rom_id);
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_hash ON rom_source_match(actual_crc, actual_size);
    CREATE INDEX IF NOT EXISTS idx_rom_source_match_sha1 ON rom_source_match(actual_sha1);
    """

    def __init__(self, db, source_dirs: Iterable[Path | str], max_workers: int = 4) -> None:
        self.db = db
        self.source_dirs = self._normalize_paths(source_dirs)
        self.max_workers = max(1, int(max_workers or 1))
        self._cancel_requested = False
        self.last_scan_id: int | None = None
        self.last_stats: dict = {}
        self._expected_roms: dict[str, list[dict]] = {}
        self._expected_disks: dict[str, list[dict]] = {}
        self._chd_results: dict[tuple[str, str], dict] = {}
        self._manifest_path: Path | None = None

    @staticmethod
    def _normalize_paths(paths: Iterable[Path | str]) -> list[Path]:
        result: list[Path] = []
        seen: set[str] = set()
        for value in paths:
            path = Path(value).expanduser()
            key = str(path.resolve()).lower()
            if key not in seen:
                seen.add(key)
                result.append(path)
        return result

    def cancel(self) -> None:
        """Solicita cancelamento cooperativo."""
        self._cancel_requested = True

    @property
    def cancelled(self) -> bool:
        """Indica se o scanner foi cancelado."""
        return self._cancel_requested

    def scan(
        self,
        machine_names: Iterable[str] | None = None,
        run_id: int | None = None,
        progress: Callable[[int, str], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
        machine_disks: dict[str, list[dict]] | None = None,
        *,
        manifest_path: Path | str | None = None,
        xml_path: Path | str | None = None,
        xml_machines: list[dict] | None = None,
        mame_version: str = "unknown",
    ) -> dict:
        """Executa o scan e grava SQLite/JSONL enquanto as machines terminam."""
        conn = self._connection()
        self._ensure_scan_tables(conn)
        self._validate_sources()
        self._cancel_requested = False
        self._chd_results.clear()

        names = [str(n).strip() for n in (machine_names or []) if str(n).strip()]
        self._expected_roms = self._build_expected_roms(names)
        self._expected_disks = machine_disks if machine_disks is not None else self._build_expected_disks(names)

        started = time.monotonic()
        conn.execute(
            "INSERT INTO rom_scan_run (dataset_run_id, source_count, status) VALUES (?, ?, 'running')",
            (run_id, len(self.source_dirs)),
        )
        scan_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        self.last_scan_id = scan_id
        conn.commit()

        stats = self._new_stats(scan_id, run_id, names)
        self._manifest_path = Path(manifest_path) if manifest_path else None
        manifest = None
        if self._manifest_path:
            self._manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest = self._open_manifest(
                self._manifest_path, names, xml_path, xml_machines or [], mame_version
            )

        logger.info(
            "Scan físico esperado iniciado: %d ROMs e %d CHDs em %d machine(s).",
            stats["expected_roms"], stats["expected_chds"], len(names),
        )
        if progress:
            progress(0, f"Preparando scan: {len(names):,} machines | {stats['expected_roms']:,} ROMs | {stats['expected_chds']:,} CHDs")

        try:
            with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="rom-scan") as executor:
                futures = {
                    executor.submit(self._scan_machine, name, scan_id, cancelled): name
                    for name in names
                }
                completed = 0
                for future in as_completed(futures):
                    self._check_cancelled(cancelled)
                    machine_name = futures[future]
                    unit = future.result()
                    self._persist_unit(conn, unit)
                    self._update_stats(stats, unit)
                    if manifest is not None:
                        self._write_unit_manifest(manifest, unit)
                    completed += 1
                    if progress:
                        progress(
                            min(100, int(completed * 100 / max(1, len(names)))),
                            self._progress_message(stats, machine_name, completed, len(names)),
                        )

            stats["seconds"] = round(time.monotonic() - started, 2)
            stats["status"] = "completed"
            self._finish_run(conn, scan_id, stats)
            if manifest is not None:
                self._finish_manifest(manifest, stats)
                manifest.close()
            self.last_stats = stats
            if progress:
                progress(100, self._summary_message(stats))
            logger.info("Scan esperado concluído em %.2fs: %s", stats["seconds"], self._summary_message(stats))
            return stats
        except Exception as exc:
            stats["seconds"] = round(time.monotonic() - started, 2)
            stats["status"] = "cancelled" if str(exc) == "Operação cancelada." else "failed"
            try:
                self._finish_run(conn, scan_id, stats, str(exc))
            finally:
                if manifest is not None:
                    manifest.write(json.dumps({"record_type": "scan_end", "status": stats["status"], "error": str(exc)}, ensure_ascii=False) + "\n")
                    manifest.flush()
                    manifest.close()
            self.last_stats = stats
            if stats["status"] == "cancelled":
                logger.info("Scan físico cancelado pelo usuário.")
                return stats
            logger.exception("Falha no scan físico.")
            raise

    def _scan_machine(self, machine_name: str, scan_id: int, cancelled: Callable[[], bool] | None) -> dict:
        """Escaneia uma machine, incluindo seus CHDs, sem acessar outras machines."""
        unit = self._empty_unit(machine_name, scan_id)
        expected = self._expected_roms.get(machine_name, [])

        for base in self.source_dirs:
            self._check_cancelled(cancelled)
            zip_path = base / f"{machine_name}.zip"
            if zip_path.is_file():
                unit["archives"] += 1
                self._scan_expected_zip(zip_path, expected, unit, cancelled)

            machine_dir = base / machine_name
            if machine_dir.is_dir():
                self._scan_expected_loose_dir(machine_dir, expected, unit, cancelled)

        for disk in self._expected_disks.get(machine_name, []):
            self._check_cancelled(cancelled)
            result = self._scan_expected_chd(machine_name, disk, cancelled)
            unit["chds"] += 1
            if result["status"] == "present":
                unit["chds_present"] += 1
            elif result["status"] == "missing":
                unit["chds_missing"] += 1
            else:
                unit["chds_errors"] += 1
            unit["chd_results"][str(disk.get("name") or "")] = result

        # Qualquer requisito não encontrado recebe uma evidência explícita.
        found_ids = {int(r[0]) for r in unit["records"] if r[0] is not None}
        for candidate in expected:
            if candidate["rom_id"] not in found_ids:
                unit["records"].append((
                    candidate["rom_id"], "", None, "expected", 0, "", None,
                    "missing", 0, "ROM não encontrada em machine.zip nem na pasta da machine",
                ))
                unit["missing"] += 1
        return unit

    def _build_expected_roms(self, machine_names: list[str]) -> dict[str, list[dict]]:
        """Carrega requisitos por machine, incluindo size/CRC/SHA1 completos."""
        result = {name: [] for name in machine_names}
        if not machine_names:
            return result
        placeholders = ",".join("?" for _ in machine_names)
        rows = self.db.fetchall(
            f"""SELECT m.name AS machine_name, r.id, r.machine_id, r.name, r.size, r.crc, r.sha1, r.merge, r.optional
                FROM rom r JOIN machine m ON m.id=r.machine_id
                WHERE m.name IN ({placeholders})
                ORDER BY m.name, r.id""",
            machine_names,
        )
        for row in rows:
            result.setdefault(str(row["machine_name"]), []).append({
                "rom_id": int(row["id"]),
                "machine_id": int(row["machine_id"]),
                "machine_name": str(row["machine_name"]),
                "name": str(row["name"] or "").replace("\\", "/"),
                "size": int(row["size"] or 0),
                "crc": str(row["crc"] or "").strip().lower(),
                "sha1": str(row["sha1"] or "").strip().lower(),
                "merge": row["merge"],
                "optional": bool(row["optional"]),
            })
        return result

    def _build_expected_disks(self, machine_names: list[str]) -> dict[str, list[dict]]:
        """Carrega somente os CHDs declarados pelas machines selecionadas."""
        result = {name: [] for name in machine_names}
        if not machine_names:
            return result
        placeholders = ",".join("?" for _ in machine_names)
        rows = self.db.fetchall(
            f"""SELECT m.name AS machine_name, d.name, d.sha1, d.merge, d.region,
                       d.disk_index, d.writable, d.optional, d.size
                FROM disk d JOIN machine m ON m.id=d.machine_id
                WHERE m.name IN ({placeholders})
                ORDER BY m.name, d.disk_index, d.id""",
            machine_names,
        )
        for row in rows:
            result.setdefault(str(row["machine_name"]), []).append({
                "name": str(row["name"] or ""),
                "sha1": str(row["sha1"] or "").strip().lower(),
                "merge": row["merge"],
                "region": row["region"],
                "index": int(row["disk_index"] or 0),
                "writable": bool(row["writable"]),
                "optional": bool(row["optional"]),
                "size": int(row["size"] or 0),
            })
        return result

    def _scan_expected_zip(self, path: Path, expected: list[dict], unit: dict, cancelled: Callable[[], bool] | None) -> None:
        """Consulta somente os membros esperados usando o diretório central ZIP."""
        try:
            with zipfile.ZipFile(path, "r") as archive:
                infos = {
                    info.filename.replace("\\", "/"): info
                    for info in archive.infolist()
                    if not info.is_dir()
                }
                basenames = {Path(name).name: info for name, info in infos.items()}
                for candidate in expected:
                    self._check_cancelled(cancelled)
                    info = infos.get(candidate["name"]) or basenames.get(Path(candidate["name"]).name)
                    if info is None:
                        continue
                    unit["members"] += 1
                    size = int(info.file_size)
                    crc = f"{info.CRC & 0xFFFFFFFF:08x}"
                    size_ok = size == candidate["size"] if candidate["size"] > 0 else True
                    crc_ok = crc == candidate["crc"] if candidate["crc"] else True
                    status = "valid" if size_ok and crc_ok else "invalid"
                    actual_sha1 = None
                    bytes_read = 0
                    error = None
                    if status == "valid" and candidate["sha1"]:
                        try:
                            with archive.open(info, "r") as stream:
                                actual_size, _actual_crc, actual_sha1 = self._hash_stream(stream, cancelled)
                            bytes_read = actual_size
                            unit["bytes_read"] += actual_size
                            status = "valid" if actual_sha1 == candidate["sha1"] else "sha1_mismatch"
                        except (OSError, EOFError, RuntimeError, zipfile.BadZipFile) as exc:
                            status = "read_error"
                            error = str(exc)
                            unit["read_errors"] += 1
                    if status == "valid":
                        unit["valid"] += 1
                    elif status == "sha1_mismatch":
                        unit["sha1_mismatch"] += 1
                    unit["records"].append((candidate["rom_id"], str(path), info.filename, "zip", size, crc, actual_sha1, status, bytes_read, error))
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            unit["read_errors"] += 1
            unit["errors"].append(f"{path}: {exc}")

    def _scan_expected_loose_dir(self, machine_dir: Path, expected: list[dict], unit: dict, cancelled: Callable[[], bool] | None) -> None:
        """Consulta somente arquivos esperados dentro da pasta da machine."""
        by_name = {Path(c["name"]).name: c for c in expected}
        for name, candidate in by_name.items():
            self._check_cancelled(cancelled)
            path = machine_dir / name
            if not path.is_file():
                continue
            try:
                size = path.stat().st_size
                crc = self._crc_file(path, cancelled)
                size_ok = size == candidate["size"] if candidate["size"] > 0 else True
                crc_ok = crc == candidate["crc"] if candidate["crc"] else True
                status = "valid" if size_ok and crc_ok else "invalid"
                actual_sha1 = None
                bytes_read = size
                if status == "valid" and candidate["sha1"]:
                    actual_sha1 = self._sha1_file(path, cancelled)
                    status = "valid" if actual_sha1 == candidate["sha1"] else "sha1_mismatch"
                unit["loose"] += 1
                unit["bytes_read"] += bytes_read
                if status == "valid":
                    unit["valid"] += 1
                elif status == "sha1_mismatch":
                    unit["sha1_mismatch"] += 1
                unit["records"].append((candidate["rom_id"], str(path), None, "loose", size, crc, actual_sha1, status, bytes_read, None))
            except (OSError, RuntimeError) as exc:
                unit["read_errors"] += 1
                unit["records"].append((candidate["rom_id"], str(path), None, "loose", 0, "", None, "read_error", 0, str(exc)))

    def _scan_expected_chd(self, machine_name: str, disk: dict, cancelled: Callable[[], bool] | None) -> dict:
        """Testa apenas a existência de ``machine/disk.chd``; não lê o CHD."""
        disk_name = str(disk.get("name") or "").strip()
        if not disk_name:
            return {"status": "error", "source_path": None, "error": "CHD sem nome"}
        filename = disk_name if disk_name.lower().endswith(".chd") else f"{disk_name}.chd"
        for base in self.source_dirs:
            self._check_cancelled(cancelled)
            path = base / machine_name / filename
            if path.is_file():
                return {"status": "present", "source_path": str(path), "error": None}
        return {"status": "missing", "source_path": None, "error": "CHD não encontrado na pasta da machine"}

    def _persist_unit(self, conn: sqlite3.Connection, unit: dict) -> None:
        """Persiste uma machine em uma única transação curta."""
        for row in unit["records"]:
            self._record(conn, unit["scan_id"], *row)
        conn.commit()

    def _record(self, conn: sqlite3.Connection, scan_id: int, rom_id: int | None, source_path: str, archive_member: str | None, source_kind: str, size: int, crc: str, sha1: str | None, status: str, bytes_read: int, error: str | None) -> None:
        conn.execute(
            """INSERT INTO rom_source_match
            (dataset_run_id, scan_run_id, rom_id, source_path, archive_member,
             source_kind, actual_size, actual_crc, actual_sha1, validation_status,
             bytes_read, checked_at, error)
            SELECT dataset_run_id, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?
            FROM rom_scan_run WHERE id=?""",
            (scan_id, rom_id, source_path or "", archive_member, source_kind, size, crc, sha1, status, bytes_read, error, scan_id),
        )

    def _open_manifest(self, path: Path, names: list[str], xml_path: Path | str | None, machines: list[dict], mame_version: str):
        """Abre o JSONL e grava o cabeçalho antes do primeiro resultado."""
        handle = path.open("w", encoding="utf-8", newline="\n")
        header = {
            "record_type": "header",
            "schema_version": 4,
            "scan_id": f"physical_{self.last_scan_id}",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "mame_version": mame_version,
            "xml_path": str(xml_path) if xml_path else "",
            "source_paths": [str(p) for p in self.source_dirs],
            "machine_count_expected": len(names),
            "metadata": {"validation": "expected_driven", "persist_mode": "streaming"},
        }
        handle.write(json.dumps(header, ensure_ascii=False) + "\n")
        handle.flush()
        return handle

    def _write_unit_manifest(self, handle, unit: dict) -> None:
        """Escreve os resultados da machine assim que ela termina."""
        machine = unit["machine"]
        expected = {c["rom_id"]: c for c in self._expected_roms.get(machine, [])}
        best: dict[int, tuple] = {}
        for row in unit["records"]:
            rom_id = row[0]
            if rom_id is None:
                continue
            previous = best.get(rom_id)
            if previous is None or self._status_rank(row[7]) < self._status_rank(previous[7]):
                best[rom_id] = row

        handle.write(json.dumps({"record_type": "machine", "event": "started", "machine": {"name": machine}}, ensure_ascii=False) + "\n")
        for rom_id, candidate in expected.items():
            row = best.get(rom_id)
            if row:
                _, source_path, member, kind, size, crc, sha1, status, bytes_read, error = row
            else:
                source_path = member = sha1 = error = None
                kind, size, crc, status, bytes_read = "expected", 0, "", "missing", 0
            record = {
                "machine": machine,
                "rom_name": candidate["name"],
                "expected_size": candidate["size"],
                "expected_crc": candidate["crc"],
                "expected_sha1": candidate["sha1"] or None,
                "merge": candidate["merge"],
                "required": not candidate["optional"],
                "optional": candidate["optional"],
                "status": status,
                "actual_size": size,
                "actual_crc": crc or None,
                "actual_sha1": sha1,
                "source": {"kind": kind, "archive": source_path, "member": member, "machine": machine} if source_path else None,
                "error": error,
            }
            handle.write(json.dumps({"record_type": "rom", "record": record}, ensure_ascii=False) + "\n")

        for disk_name, disk in unit["chd_results"].items():
            record = {
                "machine": machine,
                "disk_name": disk_name,
                "expected_size": next((int(d.get("size") or 0) for d in self._expected_disks.get(machine, []) if str(d.get("name") or "") == disk_name), 0),
                "expected_sha1": next((str(d.get("sha1") or "").lower() for d in self._expected_disks.get(machine, []) if str(d.get("name") or "") == disk_name), ""),
                "required": not next((bool(d.get("optional")) for d in self._expected_disks.get(machine, []) if str(d.get("name") or "") == disk_name), False),
                "optional": next((bool(d.get("optional")) for d in self._expected_disks.get(machine, []) if str(d.get("name") or "") == disk_name), False),
                "status": disk["status"],
                "actual_size": 0,
                "actual_sha1": None,
                "source": {"kind": "chd", "archive": disk.get("source_path"), "member": None, "machine": machine} if disk.get("source_path") else None,
                "error": disk.get("error"),
            }
            handle.write(json.dumps({"record_type": "disk", "record": record}, ensure_ascii=False) + "\n")
        handle.write(json.dumps({"record_type": "machine", "event": "finished", "machine": {"name": machine, "status": "completed"}}, ensure_ascii=False) + "\n")
        handle.flush()

    @staticmethod
    def _status_rank(status: str) -> int:
        return {"valid": 0, "sha1_mismatch": 1, "invalid": 2, "read_error": 3, "missing": 4}.get(status, 5)

    def _finish_manifest(self, handle, stats: dict) -> None:
        handle.write(json.dumps({"record_type": "summary", "status": stats["status"], "stats": stats}, ensure_ascii=False) + "\n")
        handle.flush()

    def write_manifest(self, xml_machines: list[dict], xml_path: Path, output_path: Path, mame_version: str, source_paths: Iterable[Path | str]) -> Path:
        """Compatibilidade: retorna o manifesto já criado durante o scan."""
        if self._manifest_path and self._manifest_path.resolve() == output_path.resolve() and output_path.is_file():
            return output_path
        raise RuntimeError("O manifesto deve ser criado durante PhysicalRomScanner.scan().")

    @staticmethod
    def _new_stats(scan_id: int, run_id: int | None, names: list[str]) -> dict:
        return {
            "scan_id": scan_id, "dataset_run_id": run_id,
            "expected_roms": 0, "expected_chds": 0,
            "archives": 0, "members": 0, "loose": 0,
            "chds": 0, "chds_present": 0, "chds_missing": 0, "chds_errors": 0,
            "chds_valid": 0, "bytes_read": 0, "valid": 0,
            "missing": 0, "sha1_mismatch": 0, "unmatched": 0,
            "read_errors": 0, "seconds": 0.0, "status": "running",
            "machines": len(names), "machines_completed": 0,
        }

    @staticmethod
    def _empty_unit(machine: str, scan_id: int) -> dict:
        return {
            "machine": machine, "scan_id": scan_id, "archives": 0, "members": 0,
            "loose": 0, "bytes_read": 0, "valid": 0, "missing": 0,
            "sha1_mismatch": 0, "unmatched": 0, "read_errors": 0,
            "chds": 0, "chds_present": 0, "chds_missing": 0, "chds_errors": 0,
            "records": [], "errors": [], "chd_results": {},
        }

    @staticmethod
    def _update_stats(stats: dict, unit: dict) -> None:
        for key in ("archives", "members", "loose", "bytes_read", "valid", "missing", "sha1_mismatch", "unmatched", "read_errors", "chds", "chds_present", "chds_missing", "chds_errors"):
            stats[key] += unit.get(key, 0)
        stats["chds_valid"] = stats["chds_present"]
        stats["machines_completed"] += 1

    @staticmethod
    def _progress_message(stats: dict, machine: str, completed: int, total: int) -> str:
        return (
            f"Machine {completed:,}/{total:,}: {machine} | "
            f"ROMs {stats['members']:,} verificadas | válidas {stats['valid']:,} | "
            f"ausentes {stats['missing']:,} | CHDs {stats['chds_present']:,}/{stats['chds']:,} presentes | "
            f"dados lidos {stats['bytes_read'] / (1024**3):.2f} GiB"
        )

    @staticmethod
    def _summary_message(stats: dict) -> str:
        return (
            f"Scan concluído: {stats['machines_completed']:,}/{stats['machines']:,} machines | "
            f"ROMs válidas {stats['valid']:,} | ausentes {stats['missing']:,} | "
            f"CHDs presentes {stats['chds_present']:,}/{stats['chds']:,} | tempo {stats['seconds']:.2f}s"
        )

    def _finish_run(self, conn: sqlite3.Connection, scan_id: int, stats: dict, error: str | None = None) -> None:
        conn.execute(
            """UPDATE rom_scan_run SET finished_at=CURRENT_TIMESTAMP, status=?, archive_count=?, member_count=?, loose_file_count=?, bytes_read=?, valid_match_count=?, unmatched_count=?, error=? WHERE id=?""",
            (stats["status"], stats["archives"], stats["members"], stats["loose"], stats["bytes_read"], stats["valid"], stats["unmatched"] + stats["missing"] + stats["sha1_mismatch"] + stats["read_errors"] + stats.get("chds_missing", 0) + stats.get("chds_errors", 0), error, scan_id),
        )
        conn.commit()

    def _ensure_scan_tables(self, conn: sqlite3.Connection) -> None:
        conn.executescript(self._SCAN_TABLE_SQL)
        conn.commit()

    def _validate_sources(self) -> None:
        if not self.source_dirs:
            raise RuntimeError("Nenhuma origem física de ROM foi configurada.")
        for path in self.source_dirs:
            if not path.is_dir():
                raise FileNotFoundError(f"Origem física não encontrada: {path}")

    def _connection(self) -> sqlite3.Connection:
        if self.db.conn is None:
            self.db.connect()
        assert self.db.conn is not None
        return self.db.conn

    def _check_cancelled(self, cancelled: Callable[[], bool] | None) -> None:
        if self._cancel_requested or (cancelled and cancelled()):
            raise RuntimeError("Operação cancelada.")

    def _hash_stream(self, stream, cancelled: Callable[[], bool] | None = None) -> tuple[int, str, str]:
        crc = 0
        digest = hashlib.sha1()
        size = 0
        while True:
            self._check_cancelled(cancelled)
            chunk = stream.read(self.CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
            crc = zlib.crc32(chunk, crc)
            digest.update(chunk)
        return size, f"{crc & 0xFFFFFFFF:08x}", digest.hexdigest()

    def _crc_file(self, path: Path, cancelled: Callable[[], bool] | None = None) -> str:
        crc = 0
        with path.open("rb") as stream:
            while True:
                self._check_cancelled(cancelled)
                chunk = stream.read(self.CHUNK_SIZE)
                if not chunk:
                    break
                crc = zlib.crc32(chunk, crc)
        return f"{crc & 0xFFFFFFFF:08x}"

    def _sha1_file(self, path: Path, cancelled: Callable[[], bool] | None = None) -> str:
        digest = hashlib.sha1()
        with path.open("rb") as stream:
            while True:
                self._check_cancelled(cancelled)
                chunk = stream.read(self.CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
