"""Scanner físico de ROMs MAME orientado a conteúdo.

A origem física é somente leitura. A leitura do HDD permanece serial para evitar
seek excessivo; as fases CPU-bound posteriores usam o scheduler adaptativo.
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

from app.core.system import PerformanceManager

logger = logging.getLogger(__name__)


def _render_manifest_machine(payload: dict) -> str:
    """Renderiza uma machine inteira em JSONL; função top-level para workers."""
    machine = payload["machine"]
    rows = payload["rows"]
    name = machine["name"]
    meta = {"name": name, "description": machine.get("description", ""), "cloneof": machine.get("cloneof"), "rom_count": len(machine.get("roms", []))}
    lines = [json.dumps({"record_type": "machine", "event": "started", "machine": {**meta, "status": "scanned"}}, ensure_ascii=False)]
    for rom in machine.get("roms", []):
        row = rows.get(rom["name"])
        record = {
            "machine": name, "machine_description": machine.get("description", ""), "rom_name": rom["name"],
            "expected_size": rom.get("size", 0), "expected_crc": rom.get("crc", ""), "expected_sha1": rom.get("sha1", ""),
            "merge": rom.get("merge"), "required": not bool(rom.get("optional")), "optional": bool(rom.get("optional")),
            "status": "missing" if row is None else row["validation_status"],
            "actual_size": 0 if row is None else row["actual_size"],
            "actual_crc": None if row is None else row["actual_crc"], "actual_sha1": None if row is None else row["actual_sha1"],
            "source": None if row is None else {"kind": row["source_kind"], "archive": row["source_path"], "member": row["archive_member"], "machine": name},
            "error": None if row is None else row["error"],
        }
        lines.append(json.dumps({"record_type": "rom", "record": record}, ensure_ascii=False))
    lines.append(json.dumps({"record_type": "machine", "event": "finished", "machine": {**meta, "status": "completed"}}, ensure_ascii=False))
    return "\n".join(lines) + "\n"


class PhysicalRomScanner:
    """Indexa fisicamente ROMs sem modificar os arquivos de origem."""
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
        self.performance = PerformanceManager.detect()
        logger.info("Perfil de performance do scanner: %s", self.performance.describe())

    def cancel(self) -> None:
        """Solicita cancelamento no próximo ponto seguro de leitura."""
        self._cancel_requested = True

    @property
    def cancelled(self) -> bool:
        """Retorna se o scan recebeu cancelamento."""
        return self._cancel_requested

    def scan(self, machine_names: Iterable[str] | None = None, run_id: int | None = None, progress: Callable[[int, str], None] | None = None, cancelled: Callable[[], bool] | None = None) -> dict:
        """Executa o inventário físico; a origem é lida de forma serial e segura."""
        conn = self._connection(); self._ensure_scan_tables(conn); self._validate_sources()
        expected = self._build_expected_index(machine_names); started = time.monotonic()
        conn.execute("INSERT INTO rom_scan_run (dataset_run_id, source_count, status) VALUES (?, ?, 'running')", (run_id, len(self.source_dirs)))
        scan_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0]); self.last_scan_id = scan_id; conn.commit()
        stats = {"scan_id": scan_id, "dataset_run_id": run_id, "expected_roms": sum(len(v) for v in expected.values()), "archives": 0, "members": 0, "loose": 0, "bytes_read": 0, "valid": 0, "sha1_mismatch": 0, "unmatched": 0, "read_errors": 0, "seconds": 0.0, "status": "running"}
        pending = 0
        logger.info("Scan físico iniciado: %d ROMs esperadas, %d origem(ns).", stats["expected_roms"], len(self.source_dirs))
        try:
            for root in self.source_dirs:
                self._check_cancelled(cancelled); logger.info("Origem física: %s", root)
                if progress: progress(stats["members"], f"Lendo origem: {root}")
                for path in root.rglob("*"):
                    self._check_cancelled(cancelled)
                    if not path.is_file() or path.suffix.lower() == ".chd": continue
                    if path.suffix.lower() == ".zip":
                        unit = self._scan_zip(path, expected, scan_id, cancelled); stats["archives"] += 1
                    else:
                        unit = self._scan_loose(path, expected, scan_id, cancelled); stats["loose"] += 1
                    for key in ("members", "bytes_read", "valid", "sha1_mismatch", "unmatched", "read_errors"): stats[key] += unit[key]
                    pending += unit["records"]
                    if pending >= self.COMMIT_EVERY: conn.commit(); pending = 0
                    if progress: progress(stats["members"], self._progress_message(stats, path))
            conn.commit(); stats["seconds"] = round(time.monotonic() - started, 2); stats["status"] = "completed"
            self._finish_run(conn, scan_id, stats); self.last_stats = stats
            logger.info("Scan físico concluído: archives=%d members=%d loose=%d bytes=%d valid=%d sha1_mismatch=%d unmatched=%d errors=%d tempo=%.2fs", stats["archives"], stats["members"], stats["loose"], stats["bytes_read"], stats["valid"], stats["sha1_mismatch"], stats["unmatched"], stats["read_errors"], stats["seconds"])
            return stats
        except Exception as exc:
            conn.rollback(); stats["seconds"] = round(time.monotonic() - started, 2); stats["status"] = "cancelled" if str(exc) == "Operação cancelada." else "failed"
            self._finish_run(conn, scan_id, stats, str(exc)); self.last_stats = stats
            if stats["status"] == "cancelled": logger.info("Scan físico cancelado pelo usuário."); return stats
            logger.exception("Falha no scan físico."); raise

    def _build_expected_index(self, machine_names: Iterable[str] | None) -> dict[tuple[str, int], list[dict]]:
        """Cria índice CRC+tamanho limitado às machines selecionadas."""
        index: dict[tuple[str, int], list[dict]] = {}; names = [str(n).strip() for n in (machine_names or []) if str(n).strip()]
        if names:
            placeholders = ",".join("?" for _ in names)
            rows = self.db.fetchall(f"SELECT r.id, r.machine_id, r.name, r.size, r.crc, r.sha1 FROM rom r JOIN machine m ON m.id=r.machine_id WHERE m.name IN ({placeholders}) AND r.crc IS NOT NULL AND TRIM(r.crc) <> '' AND r.size IS NOT NULL AND r.size >= 0", names)
        else:
            rows = self.db.fetchall("SELECT id, machine_id, name, size, crc, sha1 FROM rom WHERE crc IS NOT NULL AND TRIM(crc) <> '' AND size IS NOT NULL AND size >= 0")
        for row in rows:
            crc = str(row["crc"]).strip().lower(); size = int(row["size"] or 0)
            index.setdefault((crc, size), []).append({"rom_id": int(row["id"]), "machine_id": int(row["machine_id"]), "name": str(row["name"]), "sha1": str(row["sha1"] or "").strip().lower()})
        return index

    def _scan_zip(self, path: Path, expected: dict[tuple[str, int], list[dict]], scan_id: int, cancelled: Callable[[], bool] | None) -> dict:
        """Abre um ZIP uma única vez e lê cada membro em streaming."""
        result = self._empty_result()
        try:
            with zipfile.ZipFile(path, "r") as archive:
                for info in archive.infolist():
                    self._check_cancelled(cancelled)
                    if info.is_dir(): continue
                    result["members"] += 1
                    try:
                        with archive.open(info, "r") as stream: size, crc, sha1 = self._hash_stream(stream, cancelled)
                    except (OSError, EOFError, RuntimeError, zlib.error, zipfile.BadZipFile) as exc:
                        result["read_errors"] += 1; self._record(scan_id, None, path, info.filename, "zip", 0, "", "", "read_error", 0, str(exc)); result["records"] += 1; continue
                    result["bytes_read"] += size
                    result["records"] += self._record_matches(scan_id, path, info.filename, "zip", size, crc, sha1, expected.get((crc, size), []), result)
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            result["read_errors"] += 1; self._record(scan_id, None, path, None, "zip", 0, "", "", "archive_error", 0, str(exc)); result["records"] += 1
        return result

    def _scan_loose(self, path: Path, expected: dict[tuple[str, int], list[dict]], scan_id: int, cancelled: Callable[[], bool] | None) -> dict:
        """Lê um arquivo solto em streaming."""
        result = self._empty_result()
        try: size, crc, sha1 = self._hash_file(path, cancelled)
        except (OSError, RuntimeError, zlib.error) as exc:
            result["read_errors"] = 1; self._record(scan_id, None, path, None, "loose", 0, "", "", "read_error", 0, str(exc)); result["records"] = 1; return result
        result["members"] = 1; result["bytes_read"] = size
        result["records"] = self._record_matches(scan_id, path, None, "loose", size, crc, sha1, expected.get((crc, size), []), result)
        return result

    def _hash_file(self, path: Path, cancelled: Callable[[], bool] | None = None) -> tuple[int, str, str]:
        with path.open("rb") as stream: return self._hash_stream(stream, cancelled)

    def _hash_stream(self, stream, cancelled: Callable[[], bool] | None = None) -> tuple[int, str, str]:
        """Calcula CRC32 e SHA1 sobre os bytes efetivamente lidos."""
        crc = 0; sha1 = hashlib.sha1(); size = 0
        while True:
            self._check_cancelled(cancelled); chunk = stream.read(self.CHUNK_SIZE)
            if not chunk: break
            size += len(chunk); crc = zlib.crc32(chunk, crc); sha1.update(chunk)
        return size, f"{crc & 0xFFFFFFFF:08x}", sha1.hexdigest()

    def _record_matches(self, scan_id: int, source_path: Path, archive_member: str | None, source_kind: str, size: int, crc: str, sha1: str, candidates: list[dict], result: dict) -> int:
        """Relaciona o conteúdo físico com todas as ROMs compatíveis."""
        if not candidates:
            self._record(scan_id, None, source_path, archive_member, source_kind, size, crc, sha1, "unmatched", size, None); result["unmatched"] += 1; return 1
        records = 0
        for candidate in candidates:
            if candidate["sha1"] and candidate["sha1"] != sha1: status = "sha1_mismatch"; result["sha1_mismatch"] += 1
            else: status = "valid"; result["valid"] += 1
            self._record(scan_id, candidate["rom_id"], source_path, archive_member, source_kind, size, crc, sha1, status, size, None); records += 1
        return records

    def _record(self, scan_id: int, rom_id: int | None, source_path: Path, archive_member: str | None, source_kind: str, size: int, crc: str, sha1: str, status: str, bytes_read: int, error: str | None) -> None:
        self._connection().execute("INSERT INTO rom_source_match (dataset_run_id, scan_run_id, rom_id, source_path, archive_member, source_kind, actual_size, actual_crc, actual_sha1, validation_status, bytes_read, checked_at, error) SELECT dataset_run_id, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ? FROM rom_scan_run WHERE id=?", (scan_id, rom_id, str(source_path), archive_member, source_kind, size, crc, sha1, status, bytes_read, error, scan_id))

    def write_manifest(self, xml_machines: list[dict], xml_path: Path, output_path: Path, mame_version: str, source_paths: Iterable[Path | str]) -> Path:
        """Consolida o scan e renderiza o manifesto usando CPU em paralelo."""
        if not self.last_scan_id: raise RuntimeError("Nenhum scan físico foi executado.")
        output_path.parent.mkdir(parents=True, exist_ok=True); conn = self._connection()
        logger.info("Iniciando consolidação do manifesto: %d machines.", len(xml_machines))
        rows = conn.execute("""WITH ranked AS (
            SELECT r.name AS rom_name, m.name AS machine_name, m.description AS machine_description,
                   r.size AS expected_size, r.crc AS expected_crc, r.sha1 AS expected_sha1,
                   s.source_path, s.archive_member, s.source_kind, s.actual_size, s.actual_crc,
                   s.actual_sha1, s.validation_status, s.error,
                   ROW_NUMBER() OVER (PARTITION BY s.rom_id ORDER BY CASE s.validation_status WHEN 'valid' THEN 0 WHEN 'sha1_mismatch' THEN 1 ELSE 2 END, s.id DESC) AS rn
            FROM rom_source_match s JOIN rom r ON r.id=s.rom_id JOIN machine m ON m.id=r.machine_id
            WHERE s.scan_run_id=?
        ) SELECT rom_name, machine_name, machine_description, expected_size, expected_crc, expected_sha1,
                 source_path, archive_member, source_kind, actual_size, actual_crc, actual_sha1, validation_status, error
          FROM ranked WHERE rn=1""", (self.last_scan_id,)).fetchall()
        by_machine: dict[str, dict[str, dict]] = {}
        for row in rows: by_machine.setdefault(str(row["machine_name"]), {})[str(row["rom_name"])] = dict(row)
        payloads = [{"machine": machine, "rows": by_machine.get(machine["name"], {})} for machine in xml_machines]
        header = {"record_type": "header", "schema_version": 2, "scan_id": f"physical_{self.last_scan_id}", "started_at": datetime.now(timezone.utc).isoformat(), "mame_version": mame_version, "xml_path": str(xml_path), "source_paths": [str(Path(p)) for p in source_paths], "machine_count_expected": len(xml_machines), "metadata": {"validation": "physical_stream_crc32_sha1_size", "bytes_read": self.last_stats.get("bytes_read", 0), "cpu_profile": self.performance.profile.to_dict()}}
        logger.info("Consolidação SQL concluída. Renderizando JSONL com %d worker(s).", self.performance.cpu_workers())
        try:
            rendered = self.performance.map_cpu(_render_manifest_machine, payloads, chunksize=max(1, self.performance.profile.recommended_batch_size // 250))
        except Exception:
            logger.exception("Falha no processamento paralelo do manifesto; fallback serial ativado.")
            rendered = [_render_manifest_machine(payload) for payload in payloads]
        with output_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(header, ensure_ascii=False) + "\n")
            for block in rendered: handle.write(block)
        logger.info("Manifesto JSONL concluído: %s", output_path)
        return output_path

    def _validate_sources(self) -> None:
        """Valida todas as origens antes de iniciar qualquer leitura."""
        if not self.source_dirs: raise RuntimeError("Nenhuma origem física de ROM foi configurada.")
        for path in self.source_dirs:
            if not path.is_dir(): raise FileNotFoundError(f"Origem física não encontrada: {path}")

    def _ensure_scan_tables(self, conn: sqlite3.Connection) -> None:
        """Cria as tabelas auxiliares do scan de forma idempotente."""
        conn.executescript(self._SCAN_TABLE_SQL)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(rom_source_match)").fetchall()}
        if "scan_run_id" not in columns:
            conn.execute("ALTER TABLE rom_source_match ADD COLUMN scan_run_id INTEGER")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rom_source_match_scan_run ON rom_source_match(scan_run_id)")
        conn.commit()

    def _finish_run(self, conn: sqlite3.Connection, scan_id: int, stats: dict, error: str | None = None) -> None:
        """Finaliza a execução e persiste suas estatísticas."""
        conn.execute("UPDATE rom_scan_run SET finished_at=CURRENT_TIMESTAMP, status=?, archive_count=?, member_count=?, loose_file_count=?, bytes_read=?, valid_match_count=?, unmatched_count=?, error=? WHERE id=?", (stats["status"], stats["archives"], stats["members"], stats["loose"], stats["bytes_read"], stats["valid"], stats["unmatched"] + stats["sha1_mismatch"] + stats["read_errors"], error, scan_id)); conn.commit()

    def _connection(self) -> sqlite3.Connection:
        """Obtém a conexão SQLite pertencente ao processo do scanner."""
        if self.db.conn is None: self.db.connect()
        assert self.db.conn is not None
        return self.db.conn

    @staticmethod
    def _empty_result() -> dict:
        """Cria acumulador de resultados de um arquivo físico."""
        return {"members": 0, "bytes_read": 0, "valid": 0, "sha1_mismatch": 0, "unmatched": 0, "read_errors": 0, "records": 0}

    def _check_cancelled(self, cancelled: Callable[[], bool] | None) -> None:
        """Interrompe o processamento no próximo ponto seguro."""
        if self._cancel_requested or (cancelled and cancelled()): raise RuntimeError("Operação cancelada.")

    @staticmethod
    def _progress_message(stats: dict, path: Path) -> str:
        """Monta a mensagem compacta de progresso do scan físico."""
        return f"{path.name} | membros {stats['members']:,} | válidas {stats['valid']:,} | SHA1 divergente {stats['sha1_mismatch']:,} | não correspondentes {stats['unmatched']:,} | erros {stats['read_errors']:,} | bytes lidos {stats['bytes_read']:,}"
