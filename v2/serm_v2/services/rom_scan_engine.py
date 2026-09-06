"""Camada estável do scanner MAME: retomada e heartbeat."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..runtime.paths import database_path, scans_root
from .mame_scan_settings_service import MameScanSettingsService
from .rom_scan_service import RomScanService, ScanResult


class StableRomScanService(RomScanService):
    """Mantém o motor expected-driven e adiciona retomada segura."""

    HEARTBEAT_SECONDS = 5.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._heartbeat_at = 0.0
        self._heartbeat_machine = ""
        self._heartbeat_rom = ""

    def _heartbeat(self, message: str) -> None:
        now = time.monotonic()
        if now - self._heartbeat_at >= self.HEARTBEAT_SECONDS:
            self._heartbeat_at = now
            self._log("INFO", message)

    def _hash_stream(self, stream):
        crc = 0
        digest = hashlib.sha1()
        total = 0
        while True:
            if self._cancelled:
                raise RuntimeError("Operação cancelada.")
            chunk = stream.read(self.CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            crc = zlib.crc32(chunk, crc)
            digest.update(chunk)
            self._heartbeat(f"SCAN | processando | machine={self._heartbeat_machine} | ROM={self._heartbeat_rom or '-'} | SHA1={total / 1024 / 1024:.1f} MiB")
        return total, f"{crc & 0xFFFFFFFF:08x}", digest.hexdigest()

    def _crc32(self, path):
        crc = 0
        with Path(path).open("rb") as stream:
            while True:
                if self._cancelled:
                    raise RuntimeError("Operação cancelada.")
                chunk = stream.read(self.CHUNK_SIZE)
                if not chunk:
                    break
                crc = zlib.crc32(chunk, crc)
        return f"{crc & 0xFFFFFFFF:08x}"

    def _sha1(self, path):
        with Path(path).open("rb") as stream:
            return self._hash_stream(stream)[2]

    def _scan_machine(self, machine, *args, **kwargs):
        self._heartbeat_machine = machine
        self._heartbeat_rom = ""
        return super()._scan_machine(machine, *args, **kwargs)

    def scan(self, profile, *, catalog_items=(), database=None):
        if str(profile.source).casefold() != "mame":
            return super().scan(profile, catalog_items=catalog_items, database=database)
        return self._scan_mame_resumable(profile, database or database_path())

    def _scan_mame_resumable(self, profile, db_path):
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            latest = connection.execute("SELECT id, source_hash, mame_build FROM mame_listxml_import ORDER BY imported_at DESC, id DESC LIMIT 1").fetchone()
            if latest is None:
                raise RuntimeError("Nenhum ListXML MAME importado.")
            import_id, source_hash, build = latest
            scan_type = MameScanSettingsService.load(str(profile.profile_id))
            if scan_type == "software":
                raise RuntimeError("Tipo Software ainda não possui catálogo normalizado no V2.")
            machine_names = [str(r[0]) for r in connection.execute("SELECT name FROM mame_machine WHERE import_id=? ORDER BY name", (import_id,))]
            classification_columns = {str(r[1]) for r in connection.execute("PRAGMA table_info(mame_classification)")}

        result = ScanResult(scan_id=self._make_scan_id(profile), profile_id=str(profile.profile_id), source=str(profile.source), system=str(profile.system), started_at=time.time(), scan_type=scan_type, catalog_hash=str(source_hash), catalog_label=str(build or source_hash[:12]))
        sources = [Path(p).expanduser().resolve() for p in profile.source_directories]
        stream_path, completed = self._find_resume_stream(result, profile, sources, machine_names)
        result.evidence_stream_path = str(stream_path)
        pending = [m for m in machine_names if m not in completed]
        self._log("INFO", f"SCAN | MAME | retomada={bool(completed)} | concluídas={len(completed):,}/{len(machine_names):,} | pendentes={len(pending):,}")

        workers = min(self.DEFAULT_WORKERS, max(1, len(pending)))
        with stream_path.open("a", encoding="utf-8", newline="\n") as stream:
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="mame-scan") as executor:
                futures = {executor.submit(self._scan_machine, name, db_path, int(import_id), sources, classification_columns): name for name in pending}
                done = len(completed)
                for future in as_completed(futures):
                    if self._cancelled:
                        break
                    machine = futures[future]
                    unit = future.result()
                    self._write_machine(stream, unit)
                    stream.flush()
                    done += 1
                    self._merge_unit_stats(result, unit)
                    if self.progress_callback:
                        self.progress_callback(done, len(machine_names))
                    self._log("INFO", self._progress_message(result, machine, done, len(machine_names)))
            if not self._cancelled:
                self._write_jsonl(stream, {"record_type":"scan_end", "status":"completed", "finished_at":time.time(), "status_counts":dict(result.status_counts), "files_examined":result.files_examined, "archives_examined":result.archives_examined, "items_examined":result.items_examined, "errors":result.errors})
                stream.flush()
        result.finished_at = time.time()
        self._log_summary(result)
        return result

    def _find_resume_stream(self, result, profile, sources, machine_names):
        root = scans_root() / "streaming"
        root.mkdir(parents=True, exist_ok=True)
        wanted_paths = [str(p) for p in sources]
        for path in sorted(root.glob("scan_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                with path.open("r", encoding="utf-8") as stream:
                    header = json.loads(stream.readline())
            except (OSError, ValueError, UnicodeDecodeError):
                continue
            if header.get("record_type") != "header":
                continue
            if str(header.get("profile_id")) != str(profile.profile_id) or str(header.get("source")).casefold() != str(profile.source).casefold() or str(header.get("system")) != str(profile.system):
                continue
            if str(header.get("scan_type")) != str(result.scan_type) or str(header.get("catalog_hash")) != str(result.catalog_hash) or str(header.get("catalog_label")) != str(result.catalog_label):
                continue
            if header.get("source_paths") != wanted_paths:
                continue
            completed = self._completed_machines(path, machine_names)
            result.scan_id = str(header.get("scan_id") or result.scan_id)
            self._log("INFO", f"RESUME | {path.name} | última machine={self._last_completed(completed, machine_names) or 'nenhuma'}")
            return path, completed

        path = root / f"{result.scan_id}.jsonl"
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            self._write_jsonl(stream, {"record_type":"header", "format":"SERM-SCAN-V2", "scan_id":result.scan_id, "profile_id":result.profile_id, "source":result.source, "system":result.system, "scan_type":result.scan_type, "catalog_label":result.catalog_label, "catalog_hash":result.catalog_hash, "started_at":result.started_at, "source_paths":wanted_paths, "machine_count_expected":len(machine_names), "metadata":{"validation":"expected_driven","persist_mode":"streaming","filters_applied":False,"resumable":True}})
        return path, set()

    @staticmethod
    def _completed_machines(path, machine_names):
        valid = set(machine_names)
        completed = set()
        current = None
        try:
            with path.open("r", encoding="utf-8") as stream:
                next(stream, None)
                for raw in stream:
                    try:
                        record = json.loads(raw)
                    except ValueError:
                        break
                    if record.get("record_type") == "machine":
                        if current in valid:
                            completed.add(current)
                        current = str(record.get("machine") or "")
                    elif record.get("record_type") == "scan_end" and current in valid:
                        completed.add(current)
            return completed
        except OSError:
            return set()

    @staticmethod
    def _last_completed(completed, ordered):
        for name in reversed(ordered):
            if name in completed:
                return name
        return None


# Bootstrap: filter_profiles_page já importa ScanFileRepository depois do motor
# base. O import abaixo ativa a versão estável sem alterar a API pública usada
# pelo restante da GUI.
_base_scan = RomScanService
_base_scan.scan = StableRomScanService.scan
_base_scan._scan_machine = StableRomScanService._scan_machine
_base_scan._hash_stream = StableRomScanService._hash_stream
_base_scan._crc32 = StableRomScanService._crc32
_base_scan._sha1 = StableRomScanService._sha1

__all__ = ["StableRomScanService"]
