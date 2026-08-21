"""Scanner físico de ROMs e CHDs MAME orientado ao conjunto esperado.

O scanner não varre o HDD inteiro para descobrir conteúdo que não foi
solicitado pelo LISTXML. Ele consulta somente ZIPs/diretórios das machines
selecionadas e registra o resultado imediatamente no SQLite.

A busca global por conteúdo alternativo não faz parte do caminho crítico do
scan. Ela deverá ser executada por um indexador em background e consultada na
reconstrução.
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
    """Escaneia somente ROMs/CHDs esperados sem varredura global do HDD."""

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
        self.source_dirs = [Path(p).expanduser() for p in source_dirs]
        self.max_workers = max(1, int(max_workers or 1))
        self._cancel_requested = False
        self.last_scan_id: int | None = None
        self.last_stats: dict = {}
        self._chd_results: dict[tuple[str, str], dict] = {}
        self._expected_disks: dict[str, list[dict]] = {}

    def cancel(self) -> None:
        """Solicita cancelamento cooperativo."""
        self._cancel_requested = True

    @property
    def cancelled(self) -> bool:
        """Indica se o scan foi cancelado."""
        return self._cancel_requested

    def scan(
        self,
        machine_names: Iterable[str] | None = None,
        run_id: int | None = None,
        progress: Callable[[int, str], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
        machine_disks: dict[str, list[dict]] | None = None,
    ) -> dict:
        """Executa o scan esperado-driven.

        O caminho crítico consulta somente:

        * ``<rom_path>/<machine>.zip``;
        * ``<rom_path>/<machine>/<rom>``;
        * ``<rom_path>/<machine>/<disk>.chd``.

        Não há ``rglob('*')`` da origem. CHDs inexistentes são descartados
        com um simples teste ``is_file()`` e CHDs presentes não são lidos.
        SHA-1 e ``chdman verify`` pertencem exclusivamente à reconstrução.
        """
        conn = self._connection()
        self._ensure_scan_tables(conn)
        self._validate_sources()
        self._cancel_requested = False
        self._chd_results.clear()

        names = [str(n).strip() for n in (machine_names or []) if str(n).strip()]
        expected = self._build_expected_index(names)
        self._expected_disks = (
            machine_disks
            if machine_disks is not None
            else self._build_expected_disks(names)
        )

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
            "expected_chds": sum(len(v) for v in self._expected_disks.values()),
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

        logger.info(
            "Scan físico esperado iniciado: %d ROMs e %d CHDs em %d machine(s).",
            stats["expected_roms"], stats["expected_chds"], len(names),
        )

        try:
            tasks = []
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                for machine_name in names:
                    self._check_cancelled(cancelled)
                    tasks.append(
                        executor.submit(
                            self._scan_machine_expected,
                            machine_name,
                            expected,
                            scan_id,
                            cancelled,
                        )
                    )

                for future in as_completed(tasks):
                    self._check_cancelled(cancelled)
                    unit = future.result()
                    self._persist_unit(conn, unit)
                    for key in ("archives", "members", "loose", "bytes_read", "valid", "sha1_mismatch", "unmatched", "read_errors"):
                        stats[key] += unit[key]
                    if progress:
                        progress(stats["members"], self._progress_message(stats, Path(unit.get("machine") or "scan")))

            # CHDs são deliberadamente separados das ROMs. O scan só testa
            # o caminho esperado da própria machine e nunca lê o arquivo.
            for machine_name, disks in self._expected_disks.items():
                for disk in disks:
                    self._check_cancelled(cancelled)
                    stats["chds"] += 1
                    result = self._scan_expected_chd(machine_name, disk, cancelled)
                    self._chd_results[(machine_name, str(disk.get("name") or ""))] = result
                    status = result.get("status")
                    if status == "present":
                        stats["chds_valid"] += 1
                    elif status == "missing":
                        stats["chds_missing"] += 1
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
                "Scan esperado concluído: archives=%d members=%d loose=%d CHDs=%d/%d presentes tempo=%.2fs",
                stats["archives"], stats["members"], stats["loose"],
                stats["chds"], stats["chds_valid"], stats["seconds"],
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
        """Cria índice CRC+tamanho somente para as machines selecionadas."""
        index: dict[tuple[str, int], list[dict]] = {}
        names = [str(n).strip() for n in (machine_names or []) if str(n).strip()]
        if not names:
            return index
        placeholders = ",".join("?" for _ in names)
        rows = self.db.fetchall(
            f"SELECT r.id, r.machine_id, r.name, r.size, r.crc, r.sha1 FROM rom r JOIN machine m ON m.id=r.machine_id WHERE m.name IN ({placeholders}) AND r.crc IS NOT NULL AND TRIM(r.crc) <> '' AND r.size IS NOT NULL AND r.size >= 0",
            names,
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

    def _build_expected_disks(self, machine_names: Iterable[str] | None) -> dict[str, list[dict]]:
        """Carrega CHDs esperados diretamente do catálogo."""
        names = [str(n).strip() for n in (machine_names or []) if str(n).strip()]
        result: dict[str, list[dict]] = {name: [] for name in names}
        if not names:
            return result
        placeholders = ",".join("?" for _ in names)
        rows = self.db.fetchall(
            f"SELECT m.name machine_name, m.cloneof, d.name, d.sha1, d.merge, d.region, d.disk_index, d.writable, d.optional, d.size FROM disk d JOIN machine m ON m.id=d.machine_id WHERE m.name IN ({placeholders}) ORDER BY m.name, d.disk_index, d.id",
            names,
        )
        parent_map = {str(row["machine_name"]): str(row["cloneof"] or "") for row in rows}
        for row in rows:
            machine = str(row["machine_name"])
            parents: list[str] = []
            current = parent_map.get(machine, "")
            visited: set[str] = set()
            while current and current not in visited:
                visited.add(current)
                parents.append(current)
                current = parent_map.get(current, "")
            result.setdefault(machine, []).append({
                "name": str(row["name"] or ""),
                "sha1": str(row["sha1"] or "").strip().lower(),
                "merge": row["merge"],
                "region": row["region"],
                "index": int(row["disk_index"] or 0),
                "writable": bool(row["writable"]),
                "optional": bool(row["optional"]),
                "size": int(row["size"] or 0),
                "_parent_machines": parents,
            })
        return result

    def _scan_machine_expected(self, machine_name: str, expected: dict[tuple[str, int], list[dict]], scan_id: int, cancelled: Callable[[], bool] | None) -> dict:
        """Escaneia somente os artefatos diretamente ligados à machine."""
        unit = self._empty_unit(machine_name)
        expected_for_machine = {
            key: values for key, values in expected.items()
            if any(v["machine_id"] for v in values)
        }

        for base in self.source_dirs:
            self._check_cancelled(cancelled)
            zip_path = base / f"{machine_name}.zip"
            if zip_path.is_file():
                unit["archives"] += 1
                self._scan_expected_zip(zip_path, expected_for_machine, unit, cancelled)

            machine_dir = base / machine_name
            if machine_dir.is_dir():
                self._scan_expected_loose_dir(machine_dir, expected_for_machine, unit, cancelled)

        return unit

    def _scan_expected_zip(self, path: Path, expected: dict[tuple[str, int], list[dict]], unit: dict, cancelled: Callable[[], bool] | None) -> None:
        """Lê o diretório central do ZIP sem descompactar nem hashear todos os membros."""
        try:
            with zipfile.ZipFile(path, "r") as archive:
                infos = {info.filename.replace("\\", "/"): info for info in archive.infolist() if not info.is_dir()}
                basenames = {Path(name).name: info for name, info in infos.items()}
                for candidates in expected.values():
                    for candidate in candidates:
                        self._check_cancelled(cancelled)
                        name = candidate["name"]
                        info = infos.get(name) or basenames.get(Path(name).name)
                        if info is None:
                            continue
                        unit["members"] += 1
                        size = int(info.file_size)
                        crc = f"{info.CRC & 0xFFFFFFFF:08x}"
                        status = "valid" if (size == int(candidate["size"]) and crc == str(candidate["crc"]).lower()) else "invalid"
                        actual_sha1 = None
                        bytes_read = 0
                        if status == "valid" and candidate["sha1"]:
                            try:
                                with archive.open(info, "r") as stream:
                                    actual_size, _actual_crc, actual_sha1 = self._hash_stream(stream, cancelled)
                                bytes_read = actual_size
                                unit["bytes_read"] += actual_size
                                status = "valid" if actual_sha1 == candidate["sha1"] else "sha1_mismatch"
                            except (OSError, RuntimeError, EOFError, zipfile.BadZipFile) as exc:
                                status = "read_error"
                                unit["read_errors"] += 1
                                unit["errors"].append(str(exc))
                        if status == "valid":
                            unit["valid"] += 1
                        elif status == "sha1_mismatch":
                            unit["sha1_mismatch"] += 1
                        self._add_evidence(unit, candidate, path, info.filename, "zip", size, crc, actual_sha1, status, bytes_read, None)
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            unit["read_errors"] += 1
            unit["errors"].append(f"{path}: {exc}")

    def _scan_expected_loose_dir(self, machine_dir: Path, expected: dict[tuple[str, int], list[dict]], unit: dict, cancelled: Callable[[], bool] | None) -> None:
        """Consulta somente nomes esperados no diretório da machine."""
        by_name: dict[str, list[dict]] = {}
        for candidates in expected.values():
            for candidate in candidates:
                by_name.setdefault(Path(candidate["name"]).name, []).append(candidate)
        for name, candidates in by_name.items():
            self._check_cancelled(cancelled)
            path = machine_dir / name
            if not path.is_file():
                continue
            for candidate in candidates:
                try:
                    size = path.stat().st_size
                    crc = self._crc_file(path, cancelled)
                    status = "valid" if size == int(candidate["size"]) and crc == str(candidate["crc"]).lower() else "invalid"
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
                    self._add_evidence(unit, candidate, path, None, "loose", size, crc, actual_sha1, status, bytes_read, None)
                except (OSError, RuntimeError) as exc:
                    unit["read_errors"] += 1
                    self._add_evidence(unit, candidate, path, None, "loose", 0, "", None, "read_error", 0, str(exc))

    def _scan_expected_chd(self, machine_name: str, disk: dict, cancelled: Callable[[], bool] | None) -> dict:
        """Localiza somente o CHD esperado; não lê nem valida seu conteúdo."""
        disk_name = str(disk.get("name") or "").strip()
        if not disk_name:
            return {
                "status": "error",
                "source_path": None,
                "actual_size": 0,
                "bytes_read": 0,
                "actual_sha1": None,
                "error": "CHD sem nome",
            }

        filename = disk_name if disk_name.lower().endswith(".chd") else f"{disk_name}.chd"
        for base in self.source_dirs:
            self._check_cancelled(cancelled)
            candidate = base / machine_name / filename
            if candidate.is_file():
                # Presença física é tudo o que o scan precisa saber. A
                # validação de content SHA1 e chdman verify ocorre na
                # reconstrução, onde uma cópia inválida será descartada.
                return {
                    "status": "present",
                    "source_path": str(candidate),
                    "actual_size": 0,
                    "bytes_read": 0,
                    "actual_sha1": None,
                    "error": None,
                }

        return {
            "status": "missing",
            "source_path": None,
            "actual_size": 0,
            "bytes_read": 0,
            "actual_sha1": None,
            "error": "CHD não encontrado na pasta da machine",
        }

    def _add_evidence(self, unit: dict, candidate: dict, source_path: Path, member: str | None, kind: str, size: int, crc: str, sha1: str | None, status: str, bytes_read: int, error: str | None) -> None:
        """Adiciona evidência para persistência pelo thread principal."""
        unit["records"].append((candidate["rom_id"], str(source_path), member, kind, size, crc, sha1, status, bytes_read, error))

    def _persist_unit(self, conn: sqlite3.Connection, unit: dict) -> None:
        """Persiste todos os resultados de uma machine em uma transação curta."""
        for evidence in unit["records"]:
            rom_id, source_path, member, kind, size, crc, sha1, status, bytes_read, error = evidence
            self._record(conn, unit["scan_id"], rom_id, source_path, member, kind, size, crc, sha1, status, bytes_read, error)
        conn.commit()

    def _record(self, conn: sqlite3.Connection, scan_id: int, rom_id: int | None, source_path: str, archive_member: str | None, source_kind: str, size: int, crc: str, sha1: str | None, status: str, bytes_read: int, error: str | None) -> None:
        """Persiste evidência de ROM no banco."""
        conn.execute(
            """INSERT INTO rom_source_match (dataset_run_id, scan_run_id, rom_id, source_path, archive_member, source_kind, actual_size, actual_crc, actual_sha1, validation_status, bytes_read, checked_at, error)
               SELECT dataset_run_id, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ? FROM rom_scan_run WHERE id=?""",
            (scan_id, rom_id, source_path, archive_member, source_kind, size, crc, sha1, status, bytes_read, error, scan_id),
        )

    def write_manifest(self, xml_machines: list[dict], xml_path: Path, output_path: Path, mame_version: str, source_paths: Iterable[Path | str]) -> Path:
        """Gera current_scan.jsonl a partir dos resultados já registrados."""
        if not self.last_scan_id:
            raise RuntimeError("Nenhum scan físico foi executado.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        disks_by_machine = self._expected_disks or self._build_expected_disks([m["name"] for m in xml_machines])
        header = {
            "record_type": "header", "schema_version": 4,
            "scan_id": f"physical_{self.last_scan_id}",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "mame_version": mame_version, "xml_path": str(xml_path),
            "source_paths": [str(Path(p)) for p in source_paths],
            "machine_count_expected": len(xml_machines),
            "metadata": {"validation": "expected_driven_crc_size_sha1_rom_presence_chd", "bytes_read": self.last_stats.get("bytes_read", 0), "chds_scanned": self.last_stats.get("chds", 0), "chds_present": self.last_stats.get("chds_valid", 0)},
        }
        with output_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(header, ensure_ascii=False) + "\n")
            for machine in xml_machines:
                name = machine["name"]
                disks = machine.get("disks") or disks_by_machine.get(name, [])
                meta = {"name": name, "description": machine.get("description", ""), "cloneof": machine.get("cloneof"), "rom_count": len(machine.get("roms", [])) + len(disks)}
                handle.write(json.dumps({"record_type": "machine", "event": "started", "machine": {**meta, "status": "scanned"}}, ensure_ascii=False) + "\n")
                for rom in machine.get("roms", []):
                    row = self._latest_rom_match(name, rom["name"])
                    record = {"machine": name, "machine_description": machine.get("description", ""), "rom_name": rom["name"], "expected_size": rom.get("size", 0), "expected_crc": rom.get("crc", ""), "expected_sha1": rom.get("sha1", ""), "merge": rom.get("merge"), "required": not bool(rom.get("optional")), "optional": bool(rom.get("optional")), "status": "missing" if row is None else row["validation_status"], "actual_size": 0 if row is None else row["actual_size"], "actual_crc": None if row is None else row["actual_crc"], "actual_sha1": None if row is None else row["actual_sha1"], "source": None if row is None else {"kind": row["source_kind"], "archive": row["source_path"], "member": row["archive_member"], "machine": name}, "error": None if row is None else row["error"]}
                    handle.write(json.dumps({"record_type": "rom", "record": record}, ensure_ascii=False) + "\n")
                for disk in disks:
                    disk_name = str(disk.get("name") or "")
                    chd = self._chd_results.get((name, disk_name), {})
                    record = {"machine": name, "machine_description": machine.get("description", ""), "disk_name": disk_name, "expected_size": int(disk.get("size") or 0), "expected_sha1": str(disk.get("sha1") or "").lower(), "required": not bool(disk.get("optional")), "optional": bool(disk.get("optional")), "status": chd.get("status", "missing"), "actual_size": 0, "actual_sha1": None, "source": {"kind": "chd", "archive": chd.get("source_path"), "member": None, "machine": name} if chd.get("source_path") else None, "error": chd.get("error")}
                    handle.write(json.dumps({"record_type": "disk", "record": record}, ensure_ascii=False) + "\n")
                handle.write(json.dumps({"record_type": "machine", "event": "finished", "machine": {**meta, "status": "completed"}}, ensure_ascii=False) + "\n")
        return output_path

    def _latest_rom_match(self, machine_name: str, rom_name: str):
        """Obtém a melhor evidência física de uma ROM."""
        return self._connection().execute(
            """SELECT s.source_path, s.archive_member, s.source_kind, s.actual_size, s.actual_crc, s.actual_sha1, s.validation_status, s.error
               FROM rom_source_match s JOIN rom r ON r.id=s.rom_id JOIN machine m ON m.id=r.machine_id
               WHERE s.scan_run_id=? AND m.name=? AND r.name=?
               ORDER BY CASE s.validation_status WHEN 'valid' THEN 0 WHEN 'sha1_mismatch' THEN 1 ELSE 2 END, s.id DESC LIMIT 1""",
            (self.last_scan_id, machine_name, rom_name),
        ).fetchone()

    def _validate_sources(self) -> None:
        """Valida as origens configuradas sem enumerar seu conteúdo."""
        if not self.source_dirs:
            raise RuntimeError("Nenhuma origem física de ROM foi configurada.")
        for path in self.source_dirs:
            if not path.is_dir():
                raise FileNotFoundError(f"Origem física não encontrada: {path}")

    def _ensure_scan_tables(self, conn: sqlite3.Connection) -> None:
        """Cria tabelas auxiliares do scan."""
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
            (stats["status"], stats["archives"], stats["members"], stats["loose"], stats["bytes_read"], stats["valid"], stats["unmatched"] + stats["sha1_mismatch"] + stats["read_errors"] + stats.get("chds_missing", 0) + stats.get("chds_errors", 0), error, scan_id),
        )
        conn.commit()

    def _connection(self) -> sqlite3.Connection:
        """Retorna a conexão SQLite do projeto."""
        if self.db.conn is None:
            self.db.connect()
        assert self.db.conn is not None
        return self.db.conn

    @staticmethod
    def _empty_unit(machine: str) -> dict:
        """Cria acumulador de uma machine."""
        return {"machine": machine, "scan_id": 0, "archives": 0, "members": 0, "loose": 0, "bytes_read": 0, "valid": 0, "sha1_mismatch": 0, "unmatched": 0, "read_errors": 0, "records": [], "errors": []}

    @staticmethod
    def _progress_message(stats: dict, path: Path) -> str:
        """Formata o progresso sem enumerar o HDD."""
        return f"{path.name} | ZIPs {stats['archives']:,} | ROMs verificadas {stats['members']:,} | válidas {stats['valid']:,} | CHDs {stats.get('chds_valid', 0):,}/{stats.get('chds', 0):,} presentes | SHA1 divergente {stats['sha1_mismatch']:,} | erros {stats['read_errors']:,}"

    def _check_cancelled(self, cancelled: Callable[[], bool] | None) -> None:
        """Interrompe a operação quando solicitado."""
        if self._cancel_requested or (cancelled and cancelled()):
            raise RuntimeError("Operação cancelada.")

    def _hash_stream(self, stream, cancelled: Callable[[], bool] | None = None) -> tuple[int, str, str]:
        """Calcula CRC32 e SHA1 em streaming."""
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

    def _crc_file(self, path: Path, cancelled: Callable[[], bool] | None = None) -> str:
        """Calcula somente CRC32 de arquivo solto."""
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
        """Calcula SHA1 somente quando CRC+tamanho já coincidiram."""
        digest = hashlib.sha1()
        with path.open("rb") as stream:
            while True:
                self._check_cancelled(cancelled)
                chunk = stream.read(self.CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
