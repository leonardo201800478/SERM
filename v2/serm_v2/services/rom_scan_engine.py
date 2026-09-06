"""Camada estável do scanner MAME: pausa, retomada, novo scan e checkpoints."""
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
from .rom_scan_service import RomScanService, ScanResult, ScanEvidence, _MachineResult
from .rom_scan_cache_service import RomScanCacheService
from .scan_resilience import HEARTBEAT_SECONDS, ScanControl

_ORIGINAL_SCAN = RomScanService.scan
_ORIGINAL_SCAN_MACHINE = RomScanService._scan_machine
CHECKPOINT_INTERVAL = 500


class StableRomScanService(RomScanService):
    """Scanner MAME resiliente com pausa cooperativa e retomada por checkpoint."""

    HEARTBEAT_SECONDS = HEARTBEAT_SECONDS

    def __init__(self, *args, control: ScanControl | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.control = control or ScanControl()
        self._heartbeat_at = 0.0
        self._heartbeat_machine = ""
        self._heartbeat_rom = ""
        self._scan_catalog_hash = ""

    def pause(self) -> None:
        self.control.pause()
        self._log("INFO", "SCAN | PAUSA solicitada; workers concluirão a unidade atual e aguardarão.")

    def resume(self) -> None:
        self.control.resume()
        self._log("INFO", "SCAN | RETOMADA solicitada; workers liberados.")

    def cancel(self) -> None:
        self.control.cancel()
        super().cancel()

    @property
    def paused(self) -> bool:
        return self.control.paused

    @property
    def cancelled(self) -> bool:
        return self.control.cancelled or self._cancelled

    def _checkpoint_control(self) -> None:
        self.control.checkpoint()

    def _heartbeat(self, message):
        self._checkpoint_control()
        now = time.monotonic()
        last = getattr(self, "_heartbeat_at", 0.0)
        if now - last >= HEARTBEAT_SECONDS:
            self._heartbeat_at = now
            self._log("INFO", message)

    def _hash_stream(self, stream):
        crc = 0
        digest = hashlib.sha1()
        total = 0
        while True:
            self._checkpoint_control()
            chunk = stream.read(self.CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            crc = zlib.crc32(chunk, crc)
            digest.update(chunk)
            self._heartbeat(
                f"SCAN | processando | machine={getattr(self, '_heartbeat_machine', '')} | "
                f"ROM={getattr(self, '_heartbeat_rom', '') or '-'} | SHA1={total / 1024 / 1024:.1f} MiB"
            )
        return total, f"{crc & 0xFFFFFFFF:08x}", digest.hexdigest()

    def _crc32(self, path):
        crc = 0
        with Path(path).open("rb") as stream:
            while True:
                self._checkpoint_control()
                chunk = stream.read(self.CHUNK_SIZE)
                if not chunk:
                    break
                crc = zlib.crc32(chunk, crc)
        return f"{crc & 0xFFFFFFFF:08x}"

    def _sha1(self, path):
        with Path(path).open("rb") as stream:
            return self._hash_stream(stream)[2]

    def scan(self, profile, *, catalog_items=(), database=None):
        self.control = ScanControl()
        self._cancelled = False
        if str(profile.source).casefold() != "mame":
            return _ORIGINAL_SCAN(self, profile, catalog_items=catalog_items, database=database)
        return self._scan_mame_resumable(profile, database or database_path(), True)

    def scan_new(self, profile, *, database=None):
        self.control = ScanControl()
        self._cancelled = False
        if str(profile.source).casefold() != "mame":
            return _ORIGINAL_SCAN(self, profile, catalog_items=(), database=database)
        return self._scan_mame_resumable(profile, database or database_path(), False)

    def _scan_machine_with_heartbeat(self, machine, *args, **kwargs):
        self._checkpoint_control()
        self._heartbeat_machine = machine
        self._heartbeat_rom = ""
        sources = args[2] if len(args) > 2 else kwargs.get("sources", [])
        if self._scan_catalog_hash and len(sources) == 1:
            source = Path(sources[0])
            zip_path = source / f"{machine}.zip"
            machine_dir = source / machine
            if zip_path.is_file() and not machine_dir.is_dir():
                cached = RomScanCacheService.load(machine, self._scan_catalog_hash, zip_path)
                if cached is not None:
                    return cached
        result = _ORIGINAL_SCAN_MACHINE(self, machine, *args, **kwargs)
        self._checkpoint_control()
        if self._scan_catalog_hash and len(sources) == 1 and result.errors == 0:
            source = Path(sources[0])
            zip_path = source / f"{machine}.zip"
            machine_dir = source / machine
            if zip_path.is_file() and not machine_dir.is_dir():
                RomScanCacheService.save(machine, self._scan_catalog_hash, zip_path, result)
        return result

    def _machine_error(self, machine, exc):
        return _MachineResult(
            machine=machine,
            records=[ScanEvidence(machine_name=machine, rom_name="", status="ERROR",
                                  message="Falha inesperada durante a machine; será reprocessada na retomada",
                                  error=f"{type(exc).__name__}: {exc}")],
            errors=1,
        )

    @staticmethod
    def _checkpoint_path(stream_path: Path) -> Path:
        return stream_path.with_suffix(".checkpoint.json")

    @staticmethod
    def _write_checkpoint(path: Path, header: dict[str, object], completed: set[str], *, paused: bool = False, cancelled: bool = False) -> None:
        target = path.with_suffix(path.suffix + ".tmp")
        payload = {
            "format": "SERM-SCAN-CHECKPOINT-V3",
            "scan_id": header.get("scan_id"), "profile_id": header.get("profile_id"),
            "source": header.get("source"), "system": header.get("system"),
            "scan_type": header.get("scan_type"), "catalog_label": header.get("catalog_label"),
            "catalog_hash": header.get("catalog_hash"), "source_paths": header.get("source_paths", []),
            "machine_count_expected": header.get("machine_count_expected", 0),
            "completed_count": len(completed), "completed_machines": sorted(completed),
            "paused": paused, "cancelled": cancelled, "updated_at": time.time(),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n"); stream.flush()
        target.replace(path)

    def _scan_mame_resumable(self, profile, db_path, resume=True):
        with sqlite3.connect(db_path) as c:
            latest = c.execute("SELECT id,source_hash,mame_build FROM mame_listxml_import ORDER BY imported_at DESC,id DESC LIMIT 1").fetchone()
            if latest is None:
                raise RuntimeError("Nenhum ListXML MAME importado.")
            import_id, source_hash, build = latest
            scan_type = MameScanSettingsService.load(str(profile.profile_id))
            if scan_type == "software":
                raise RuntimeError("Tipo Software ainda não possui catálogo normalizado no V2.")
            machines = [str(r[0]) for r in c.execute("SELECT name FROM mame_machine WHERE import_id=? ORDER BY name", (import_id,))]
            columns = {str(r[1]) for r in c.execute("PRAGMA table_info(mame_classification)")}

        result = ScanResult(scan_id=self._make_scan_id(profile), profile_id=str(profile.profile_id), source=str(profile.source), system=str(profile.system), started_at=time.time(), scan_type=scan_type, catalog_hash=str(source_hash), catalog_label=str(build or source_hash[:12]))
        self._scan_catalog_hash = result.catalog_hash or ""
        sources = [Path(p).expanduser().resolve() for p in profile.source_directories]
        if not sources:
            raise RuntimeError("Nenhum diretório de origem foi configurado para o scan.")
        for source in sources:
            if not source.is_dir():
                raise RuntimeError(f"Diretório de origem não encontrado: {source}")

        if resume:
            path, completed = self._find_resume_stream(result, profile, sources, machines, db_path)
        else:
            path, completed = self._create_new_stream(result, profile, sources, machines)
        result.evidence_stream_path = str(path)
        pending = [m for m in machines if m not in completed]
        self._log("INFO", f"SCAN | MAME | modo={'retomada' if resume else 'novo'} | concluídas={len(completed):,}/{len(machines):,} | pendentes={len(pending):,} | workers=6 | checkpoint={CHECKPOINT_INTERVAL} | cache=ativo")

        workers = min(6, max(1, len(pending)))
        checkpoint_path = self._checkpoint_path(path)
        header = {"scan_id": result.scan_id, "profile_id": result.profile_id, "source": result.source, "system": result.system, "scan_type": result.scan_type, "catalog_label": result.catalog_label, "catalog_hash": result.catalog_hash, "source_paths": [str(p) for p in sources], "machine_count_expected": len(machines)}
        completed_for_checkpoint = set(completed)
        last_checkpoint_done = len(completed)

        with path.open("a", encoding="utf-8", newline="\n") as stream, ThreadPoolExecutor(max_workers=workers, thread_name_prefix="mame-scan") as executor, ThreadPoolExecutor(max_workers=1, thread_name_prefix="mame-checkpoint") as checkpoint_executor:
            futures = {executor.submit(self._scan_machine_with_heartbeat, machine, db_path, int(import_id), sources, columns): machine for machine in pending}
            done = len(completed)
            checkpoint_future = None
            for future in as_completed(futures):
                if self.paused:
                    stream.flush()
                    snapshot = set(completed_for_checkpoint)
                    if checkpoint_future is not None:
                        checkpoint_future.result()
                    checkpoint_future = checkpoint_executor.submit(self._write_checkpoint, checkpoint_path, header, snapshot, paused=True)
                    checkpoint_future.result()
                    self._log("INFO", f"PAUSA | checkpoint salvo | concluídas={len(snapshot):,}/{len(machines):,}")
                    self.control.wait_if_paused()
                    self._log("INFO", "RETOMADA | checkpoint mantido; continuando as máquinas pendentes.")
                machine = futures[future]
                try:
                    unit = future.result()
                except Exception as exc:
                    if self.cancelled:
                        break
                    unit = self._machine_error(machine, exc)
                    self._log("ERROR", f"SCAN | machine={machine} | falha isolada: {type(exc).__name__}: {exc} | continuará")
                self._write_machine(stream, unit)
                if unit.errors == 0:
                    completed_for_checkpoint.add(unit.machine)
                done += 1
                self._merge_unit_stats(result, unit)
                if self.progress_callback:
                    self.progress_callback(done, len(machines))
                if done == 1 or done % 100 == 0 or done == len(machines):
                    self._log("INFO", self._progress_message(result, machine, done, len(machines)))
                if done - last_checkpoint_done >= CHECKPOINT_INTERVAL:
                    stream.flush()
                    snapshot = set(completed_for_checkpoint)
                    if checkpoint_future is not None:
                        checkpoint_future.result()
                    checkpoint_future = checkpoint_executor.submit(self._write_checkpoint, checkpoint_path, header, snapshot)
                    last_checkpoint_done = done
                if self.cancelled:
                    break

            stream.flush()
            snapshot = set(completed_for_checkpoint)
            if checkpoint_future is not None:
                checkpoint_future.result()
            if self.cancelled:
                checkpoint_future = checkpoint_executor.submit(self._write_checkpoint, checkpoint_path, header, snapshot, cancelled=True)
                checkpoint_future.result()
            elif done == len(machines):
                checkpoint_future = checkpoint_executor.submit(self._write_checkpoint, checkpoint_path, header, snapshot)
                checkpoint_future.result()
            self._write_jsonl(stream, {"record_type": "scan_end", "status": "cancelled" if self.cancelled else "completed", "finished_at": time.time(), "status_counts": dict(result.status_counts), "files_examined": result.files_examined, "archives_examined": result.archives_examined, "items_examined": result.items_examined, "errors": result.errors})
            stream.flush()

        result.finished_at = time.time()
        self._log_summary(result)
        return result

    def _create_new_stream(self, result, profile, sources, machines):
        root = scans_root() / "streaming"; root.mkdir(parents=True, exist_ok=True)
        path = root / f"{result.scan_id}.jsonl"
        wanted = [str(p) for p in sources]
        with path.open("w", encoding="utf-8", newline="\n") as s:
            self._write_jsonl(s, {"record_type":"header","format":"SERM-SCAN-V2","scan_id":result.scan_id,"profile_id":result.profile_id,"source":result.source,"system":result.system,"scan_type":result.scan_type,"catalog_label":result.catalog_label,"catalog_hash":result.catalog_hash,"started_at":result.started_at,"source_paths":wanted,"machine_count_expected":len(machines),"metadata":{"validation":"expected_driven","persist_mode":"streaming","filters_applied":False,"resumable":True,"checkpoint_interval":CHECKPOINT_INTERVAL,"checkpoint_storage":"sidecar","hash_cache":"physical_zip_stat","pause_resume":True}})
        return path, set()

    def _find_resume_stream(self, result, profile, sources, machines, db_path):
        root = scans_root() / "streaming"; root.mkdir(parents=True, exist_ok=True)
        wanted = [str(p) for p in sources]
        for path in sorted(root.glob("scan_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                with path.open("r", encoding="utf-8") as s:
                    header = json.loads(s.readline())
            except (OSError, ValueError, UnicodeDecodeError):
                continue
            if header.get("record_type") != "header":
                continue
            if str(header.get("profile_id")) != str(profile.profile_id) or str(header.get("source")).casefold() != str(profile.source).casefold() or str(header.get("system")) != str(profile.system):
                continue
            if str(header.get("scan_type")) != str(result.scan_type) or str(header.get("catalog_hash")) != str(result.catalog_hash) or str(header.get("catalog_label")) != str(result.catalog_label) or header.get("source_paths") != wanted:
                continue
            completed = self._read_checkpoint(path, machines)
            if not completed:
                completed = self._completed_machines(path, machines, db_path)
            if not completed:
                self._log("WARNING", f"RESUME | ignorando stream sem checkpoint válido: {path.name}")
                continue
            result.scan_id = str(header.get("scan_id") or result.scan_id)
            self._log("INFO", f"RESUME | {path.name} | concluídas={len(completed):,}/{len(machines):,} | última machine={self._last_completed(completed, machines) or 'nenhuma'}")
            return path, completed
        return self._create_new_stream(result, profile, sources, machines)

    @classmethod
    def _read_checkpoint(cls, path: Path, machines) -> set[str]:
        checkpoint = cls._checkpoint_path(path); valid = set(machines)
        if not checkpoint.is_file() or not valid:
            return set()
        try:
            payload = json.loads(checkpoint.read_text(encoding="utf-8"))
            if payload.get("format") not in {"SERM-SCAN-CHECKPOINT-V2", "SERM-SCAN-CHECKPOINT-V3"}:
                return set()
            return {str(name) for name in payload.get("completed_machines", []) if str(name) in valid}
        except (OSError, ValueError, TypeError):
            return set()

    @staticmethod
    def _completed_machines(path, machines, db_path=None):
        valid = set(machines)
        if not valid: return set()
        completed = set()
        try:
            with path.open("r", encoding="utf-8") as stream:
                next(stream, None)
                for raw in stream:
                    try: record = json.loads(raw)
                    except ValueError: break
                    if record.get("record_type") == "machine_complete":
                        machine = str(record.get("machine") or "")
                        if machine in valid: completed.add(machine)
        except OSError: return set()
        return completed

    @staticmethod
    def _last_completed(completed, ordered):
        for name in reversed(ordered):
            if name in completed: return name
        return None
