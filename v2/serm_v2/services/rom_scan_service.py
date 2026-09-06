"""Motor de auditoria bruta do SERM V2.

O caminho crítico é expected-driven: o catálogo informa as machines/ROMs que
serão verificadas e o scanner consulta somente os ZIPs/diretórios dessas
machines. Não existe enumeração global do HDD.

A estratégia recupera a última V1 funcional: workers por machine, fila limitada
de tarefas, persistência incremental e manifesto JSONL. Filtros não participam
do scan.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
import zipfile
import zlib
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ..runtime.paths import database_path, scans_root
from .mame_scan_settings_service import MameScanSettingsService

LogCallback = Callable[[str, str], None]
ProgressCallback = Callable[[int, int], None]


@dataclass(slots=True, frozen=True)
class ScanItem:
    machine_name: str
    rom_name: str
    size: int
    crc32: str = ""
    sha1: str = ""
    optional: bool = False


@dataclass(slots=True)
class ScanEvidence:
    machine_name: str
    rom_name: str
    status: str
    expected_size: int | None = None
    actual_size: int | None = None
    expected_crc: str = ""
    actual_crc: str = ""
    expected_sha1: str = ""
    actual_sha1: str = ""
    expected_md5: str = ""
    actual_md5: str = ""
    path: str | None = None
    archive_path: str | None = None
    archive_member: str | None = None
    merge_name: str | None = None
    optional: bool = False
    message: str = ""
    error: str | None = None
    categories: tuple[str, ...] = ()
    cloneof: str | None = None
    isbios: str | None = None
    isdevice: str | None = None
    ismechanical: str | None = None
    runnable: str | None = None


@dataclass(slots=True)
class ScanResult:
    scan_id: str
    profile_id: str
    source: str
    system: str
    status_counts: Counter[str] = field(default_factory=Counter)
    files_examined: int = 0
    archives_examined: int = 0
    items_examined: int = 0
    started_at: float = 0.0
    finished_at: float = 0.0
    errors: int = 0
    catalog_hash: str | None = None
    catalog_label: str = "catalog"
    scan_type: str = "full"
    evidence: list[ScanEvidence] = field(default_factory=list)
    evidence_stream_path: str | None = None

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, (self.finished_at or time.time()) - self.started_at)


@dataclass(slots=True, frozen=True)
class _ExpectedRom:
    rom_id: int
    machine_name: str
    rom_name: str
    size: int
    crc: str
    sha1: str
    md5: str
    merge: str | None
    optional: bool
    categories: tuple[str, ...]
    cloneof: str | None
    isbios: str | None
    isdevice: str | None
    ismechanical: str | None
    runnable: str | None


@dataclass(slots=True)
class _MachineResult:
    machine: str
    records: list[ScanEvidence] = field(default_factory=list)
    files_examined: int = 0
    archives_examined: int = 0
    items_examined: int = 0
    bytes_read: int = 0
    errors: int = 0


class RomScanService:
    """Scanner expected-driven com streaming, sem aplicar filtros."""

    CHUNK_SIZE = 1024 * 1024
    DEFAULT_WORKERS = 4
    DEFAULT_BATCH_MULTIPLIER = 4

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        log_callback: LogCallback | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.logger = logger or logging.getLogger("serm.scan")
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        self._log("WARNING", "CANCELAMENTO | solicitado; encerrando no próximo checkpoint")

    def estimate_mame(
        self, profile, *, database: Path | None = None
    ) -> dict[str, int | str | None]:
        db_path = database or database_path()
        if not db_path.is_file():
            return {
                "machines": 0,
                "roms": 0,
                "optional_roms": 0,
                "disks": 0,
                "catalog_roms": 0,
                "catalog_hash": None,
                "error": str(db_path),
            }
        scan_type = MameScanSettingsService.load(str(profile.profile_id))
        try:
            with sqlite3.connect(db_path) as connection:
                latest = connection.execute(
                    "SELECT id, source_hash, mame_build FROM mame_listxml_import ORDER BY imported_at DESC, id DESC LIMIT 1"
                ).fetchone()
                if latest is None:
                    return {
                        "machines": 0,
                        "roms": 0,
                        "optional_roms": 0,
                        "disks": 0,
                        "catalog_roms": 0,
                        "catalog_hash": None,
                        "error": "Nenhum ListXML MAME importado.",
                    }
                import_id, source_hash, build = latest
                machines = connection.execute(
                    "SELECT COUNT(*) FROM mame_machine WHERE import_id=?", (import_id,)
                ).fetchone()[0]
                roms = connection.execute(
                    "SELECT COUNT(*) FROM mame_rom WHERE machine_id IN (SELECT id FROM mame_machine WHERE import_id=?)",
                    (import_id,),
                ).fetchone()[0]
                optional = connection.execute(
                    "SELECT COUNT(*) FROM mame_rom WHERE optional IN ('yes','true','1') AND machine_id IN (SELECT id FROM mame_machine WHERE import_id=?)",
                    (import_id,),
                ).fetchone()[0]
                disks = connection.execute(
                    "SELECT COUNT(*) FROM mame_disk WHERE machine_id IN (SELECT id FROM mame_machine WHERE import_id=?)",
                    (import_id,),
                ).fetchone()[0]
                has_software = self._has_software_catalog(connection)
        except sqlite3.Error as exc:
            return {
                "machines": 0,
                "roms": 0,
                "optional_roms": 0,
                "disks": 0,
                "catalog_roms": 0,
                "catalog_hash": None,
                "error": str(exc),
            }
        if scan_type in {"software", "both"} and not has_software:
            return {
                "machines": int(machines),
                "roms": int(roms),
                "optional_roms": int(optional),
                "disks": int(disks),
                "catalog_roms": int(roms),
                "catalog_hash": str(source_hash),
                "scan_type": scan_type,
                "catalog_label": str(build or source_hash[:12]),
                "error": "O catálogo de Software Lists do MAME ainda não foi importado para o banco V2.",
            }
        return {
            "machines": int(machines),
            "roms": int(roms),
            "optional_roms": int(optional),
            "disks": int(disks),
            "catalog_roms": int(roms),
            "catalog_hash": str(source_hash),
            "scan_type": scan_type,
            "catalog_label": str(build or source_hash[:12]),
            "error": None,
        }

    def scan(
        self, profile, *, catalog_items: Iterable[ScanItem] = (), database: Path | None = None
    ) -> ScanResult:
        started = time.time()
        is_mame = str(profile.source).casefold() == "mame"
        scan_type = MameScanSettingsService.load(str(profile.profile_id)) if is_mame else "full"
        result = ScanResult(
            scan_id=self._make_scan_id(profile),
            profile_id=str(profile.profile_id),
            source=str(profile.source),
            system=str(profile.system),
            started_at=started,
            scan_type=scan_type,
        )
        self._cancelled = False
        sources = [Path(p).expanduser().resolve() for p in profile.source_directories]
        if not sources:
            raise RuntimeError("Nenhum diretório de origem foi configurado para o scan.")
        for source in sources:
            if not source.is_dir():
                raise RuntimeError(f"Diretório de origem não encontrado: {source}")
        self._log(
            "INFO", f"SCAN | início | scan_id={result.scan_id} | profile_id={profile.profile_id}"
        )
        self._log("INFO", f"SCAN | catálogo={profile.source} › {profile.system} | tipo={scan_type}")
        self._log("INFO", f"SCAN | fontes={len(sources)} | modo=expected-driven | streaming=JSONL")
        stream_path = scans_root() / "streaming" / f"{result.scan_id}.jsonl"
        stream_path.parent.mkdir(parents=True, exist_ok=True)
        result.evidence_stream_path = str(stream_path)
        if is_mame:
            self._scan_mame(result, profile, database or database_path(), sources, stream_path)
        else:
            self._scan_generic_physical(result, profile, sources, stream_path, catalog_items)
        result.finished_at = time.time()
        self._log_summary(result)
        return result

    def _scan_mame(
        self, result: ScanResult, profile, db_path: Path, sources: list[Path], stream_path: Path
    ) -> None:
        if not db_path.is_file():
            raise RuntimeError(f"Banco do catálogo MAME não encontrado: {db_path}")
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            latest = connection.execute(
                "SELECT id, source_hash, mame_build FROM mame_listxml_import ORDER BY imported_at DESC, id DESC LIMIT 1"
            ).fetchone()
            if latest is None:
                raise RuntimeError("Nenhum ListXML MAME importado.")
            import_id, source_hash, build = latest
            result.catalog_hash = str(source_hash)
            result.catalog_label = str(build or source_hash[:12])
            if result.scan_type in {"software", "both"} and not self._has_software_catalog(
                connection
            ):
                raise RuntimeError(
                    "O catálogo de Software Lists do MAME ainda não foi importado para o banco V2."
                )
            if result.scan_type == "software":
                raise RuntimeError(
                    "Tipo de scan 'Software' selecionado, mas o catálogo de Software Lists ainda não possui ROMs normalizadas."
                )
            if result.scan_type == "both":
                self._log(
                    "WARNING",
                    "SCAN | Ambos ainda usa somente a parte Arcade; Software Lists será adicionada quando normalizada.",
                )
            machine_names = [
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM mame_machine WHERE import_id=? ORDER BY name", (import_id,)
                )
            ]
            classification_columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(mame_classification)")
            }
        workers = min(self.DEFAULT_WORKERS, max(1, len(machine_names)))
        batch_size = max(workers * self.DEFAULT_BATCH_MULTIPLIER, 16)
        total = len(machine_names)
        completed = 0
        self._log(
            "INFO",
            f"CATALOGO | MAME | build={result.catalog_label} | machines={total:,} | workers={workers} | lote={batch_size}",
        )
        with stream_path.open("w", encoding="utf-8", newline="\n") as stream:
            self._write_jsonl(
                stream,
                {
                    "record_type": "header",
                    "format": "SERM-SCAN-V1",
                    "scan_id": result.scan_id,
                    "profile_id": result.profile_id,
                    "source": result.source,
                    "system": result.system,
                    "scan_type": result.scan_type,
                    "catalog_label": result.catalog_label,
                    "catalog_hash": result.catalog_hash,
                    "started_at": result.started_at,
                    "source_paths": [str(path) for path in sources],
                    "machine_count_expected": total,
                    "metadata": {
                        "validation": "expected_driven",
                        "persist_mode": "streaming",
                        "filters_applied": False,
                    },
                },
            )
            for offset in range(0, total, batch_size):
                if self._cancelled:
                    break
                batch = machine_names[offset : offset + batch_size]
                with ThreadPoolExecutor(
                    max_workers=workers, thread_name_prefix="mame-scan"
                ) as executor:
                    futures = {
                        executor.submit(
                            self._scan_machine,
                            name,
                            db_path,
                            int(import_id),
                            sources,
                            classification_columns,
                        ): name
                        for name in batch
                    }
                    for future in as_completed(futures):
                        if self._cancelled:
                            break
                        machine = futures[future]
                        unit = future.result()
                        self._write_machine(stream, unit)
                        completed += 1
                        self._merge_unit_stats(result, unit)
                        if self.progress_callback:
                            self.progress_callback(completed, total)
                        if completed == 1 or completed % 25 == 0 or completed == total:
                            self._log(
                                "INFO", self._progress_message(result, machine, completed, total)
                            )
                stream.flush()
            self._write_jsonl(
                stream,
                {
                    "record_type": "scan_end",
                    "status": "cancelled" if self._cancelled else "completed",
                    "finished_at": time.time(),
                    "status_counts": dict(result.status_counts),
                    "files_examined": result.files_examined,
                    "archives_examined": result.archives_examined,
                    "items_examined": result.items_examined,
                    "errors": result.errors,
                },
            )
            stream.flush()

    def _scan_machine(
        self,
        machine: str,
        db_path: Path,
        import_id: int,
        sources: list[Path],
        classification_columns: set[str],
    ) -> _MachineResult:
        unit = _MachineResult(machine)
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """SELECT m.name AS machine_name, m.cloneof, r.id AS rom_id, r.name AS rom_name, r.size, lower(coalesce(r.crc,'')) AS expected_crc, lower(coalesce(r.sha1,'')) AS expected_sha1, lower(coalesce(r.md5,'')) AS expected_md5, r.merge, r.optional, m.isbios, m.isdevice, m.ismechanical, m.runnable, m.id AS machine_id FROM mame_machine m JOIN mame_rom r ON r.machine_id=m.id WHERE m.import_id=? AND m.name=? ORDER BY r.name""",
                (import_id, machine),
            ).fetchall()
            machine_id = int(rows[0]["machine_id"]) if rows else None
            categories: tuple[str, ...] = ()
            if machine_id is not None and {"machine_id", "category"}.issubset(
                classification_columns
            ):
                category_rows = connection.execute(
                    "SELECT category, subcategory FROM mame_classification WHERE machine_id=?",
                    (machine_id,),
                ).fetchall()
                values = {
                    str(value).strip().casefold()
                    for row in category_rows
                    for value in (row["category"], row["subcategory"])
                    if value
                }
                categories = tuple(sorted(values))
        expected = [
            _ExpectedRom(
                rom_id=hash(str(row["rom_name"] or "").casefold()),
                machine_name=machine,
                rom_name=str(row["rom_name"] or ""),
                size=int(row["size"] or 0),
                crc=str(row["expected_crc"] or ""),
                sha1=str(row["expected_sha1"] or ""),
                md5=str(row["expected_md5"] or ""),
                merge=row["merge"],
                optional=str(row["optional"] or "").casefold() in {"yes", "true", "1"},
                categories=categories,
                cloneof=row["cloneof"],
                isbios=row["isbios"],
                isdevice=row["isdevice"],
                ismechanical=row["ismechanical"],
                runnable=row["runnable"],
            )
            for row in rows
        ]
        expected_by_name: dict[str, list[_ExpectedRom]] = {}
        for item in expected:
            expected_by_name.setdefault(Path(item.rom_name).name.casefold(), []).append(item)
        for base in sources:
            if self._cancelled:
                break
            zip_path = base / f"{machine}.zip"
            if zip_path.is_file():
                unit.files_examined += 1
                unit.archives_examined += 1
                self._scan_zip(zip_path, expected_by_name, unit)
            machine_dir = base / machine
            if machine_dir.is_dir():
                self._scan_loose(machine_dir, expected_by_name, unit)
        found_names = {
            e.rom_name.casefold() for e in unit.records if e.status != "MISSING" and e.rom_name
        }
        for item in expected:
            if item.rom_name.casefold() not in found_names:
                unit.records.append(self._missing(item))
        return unit

    def _scan_zip(
        self, path: Path, expected_by_name: dict[str, list[_ExpectedRom]], unit: _MachineResult
    ) -> None:
        try:
            with zipfile.ZipFile(path, "r") as archive:
                infos = {
                    Path(info.filename).name.casefold(): info
                    for info in archive.infolist()
                    if not info.is_dir()
                }
                for name, candidates in expected_by_name.items():
                    if self._cancelled:
                        return
                    info = infos.get(name)
                    if info is None:
                        continue
                    unit.items_examined += 1
                    for item in candidates:
                        crc = f"{info.CRC & 0xFFFFFFFF:08x}"
                        size = int(info.file_size)
                        size_ok = item.size <= 0 or size == item.size
                        crc_ok = not item.crc or crc == item.crc
                        status = "CURRENT" if size_ok and crc_ok else "WRONG"
                        actual_sha1 = ""
                        bytes_read = 0
                        if status == "CURRENT" and item.sha1:
                            with archive.open(info, "r") as stream:
                                actual_size, _, actual_sha1 = self._hash_stream(stream)
                            bytes_read = actual_size
                            unit.bytes_read += actual_size
                            if actual_sha1 != item.sha1:
                                status = "WRONG"
                        unit.records.append(
                            self._evidence(
                                item,
                                status,
                                size,
                                crc,
                                actual_sha1,
                                path,
                                path,
                                info.filename,
                                bytes_read,
                                "nome encontrado, mas tamanho/CRC diverge"
                                if status == "WRONG"
                                else "hash/tamanho correspondentes",
                            )
                        )
        except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
            unit.errors += 1
            unit.records.append(
                ScanEvidence(
                    machine_name=unit.machine,
                    rom_name="",
                    status="ERROR",
                    path=str(path),
                    message="Falha ao abrir ZIP",
                    error=str(exc),
                )
            )

    def _scan_loose(
        self,
        machine_dir: Path,
        expected_by_name: dict[str, list[_ExpectedRom]],
        unit: _MachineResult,
    ) -> None:
        for name, candidates in expected_by_name.items():
            if self._cancelled:
                return
            path = machine_dir / Path(name).name
            if not path.is_file():
                continue
            for item in candidates:
                try:
                    unit.items_examined += 1
                    size = int(path.stat().st_size)
                    crc = self._crc32(path)
                    status = (
                        "CURRENT"
                        if (item.size <= 0 or size == item.size)
                        and (not item.crc or crc == item.crc)
                        else "WRONG"
                    )
                    actual_sha1 = ""
                    if status == "CURRENT" and item.sha1:
                        actual_sha1 = self._sha1(path)
                        if actual_sha1 != item.sha1:
                            status = "WRONG"
                    unit.bytes_read += size
                    unit.records.append(
                        self._evidence(
                            item,
                            status,
                            size,
                            crc,
                            actual_sha1,
                            path,
                            None,
                            None,
                            size,
                            "nome encontrado, mas tamanho/CRC diverge"
                            if status == "WRONG"
                            else "hash/tamanho correspondentes",
                        )
                    )
                except OSError as exc:
                    unit.errors += 1
                    unit.records.append(
                        self._evidence(item, "ERROR", 0, "", "", path, None, None, 0, str(exc))
                    )

    @staticmethod
    def _evidence(
        item: _ExpectedRom,
        status: str,
        actual_size: int,
        actual_crc: str,
        actual_sha1: str,
        path: Path,
        archive_path: Path | None,
        archive_member: str | None,
        bytes_read: int,
        message: str,
    ) -> ScanEvidence:
        return ScanEvidence(
            machine_name=item.machine_name,
            rom_name=item.rom_name,
            status=status,
            expected_size=item.size,
            actual_size=actual_size,
            expected_crc=item.crc,
            actual_crc=actual_crc,
            expected_sha1=item.sha1,
            actual_sha1=actual_sha1,
            expected_md5=item.md5,
            path=str(path),
            archive_path=str(archive_path) if archive_path else None,
            archive_member=archive_member,
            merge_name=item.merge,
            optional=item.optional,
            message=message,
            categories=item.categories,
            cloneof=item.cloneof,
            isbios=item.isbios,
            isdevice=item.isdevice,
            ismechanical=item.ismechanical,
            runnable=item.runnable,
        )

    @staticmethod
    def _missing(item: _ExpectedRom) -> ScanEvidence:
        return ScanEvidence(
            machine_name=item.machine_name,
            rom_name=item.rom_name,
            status="MISSING",
            expected_size=item.size,
            expected_crc=item.crc,
            expected_sha1=item.sha1,
            expected_md5=item.md5,
            merge_name=item.merge,
            optional=item.optional,
            message="ROM não encontrada em machine.zip nem na pasta da machine",
            categories=item.categories,
            cloneof=item.cloneof,
            isbios=item.isbios,
            isdevice=item.isdevice,
            ismechanical=item.ismechanical,
            runnable=item.runnable,
        )

    @staticmethod
    def _hash_stream(stream) -> tuple[int, str, str]:
        crc = 0
        digest = hashlib.sha1()
        total = 0
        while True:
            chunk = stream.read(RomScanService.CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            crc = zlib.crc32(chunk, crc)
            digest.update(chunk)
        return total, f"{crc & 0xFFFFFFFF:08x}", digest.hexdigest()

    @staticmethod
    def _crc32(path: Path) -> str:
        crc = 0
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(RomScanService.CHUNK_SIZE)
                if not chunk:
                    break
                crc = zlib.crc32(chunk, crc)
        return f"{crc & 0xFFFFFFFF:08x}"

    @staticmethod
    def _sha1(path: Path) -> str:
        digest = hashlib.sha1()
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(RomScanService.CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _write_jsonl(stream, payload: dict) -> None:
        stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")

    def _write_machine(self, stream, unit: _MachineResult) -> None:
        self._write_jsonl(
            stream,
            {
                "record_type": "machine",
                "machine": unit.machine,
                "files_examined": unit.files_examined,
                "archives_examined": unit.archives_examined,
                "items_examined": unit.items_examined,
                "errors": unit.errors,
            },
        )
        for evidence in unit.records:
            self._write_jsonl(
                stream,
                {
                    "record_type": "evidence",
                    "machine_name": evidence.machine_name,
                    "rom_name": evidence.rom_name,
                    "status": evidence.status,
                    "expected_size": evidence.expected_size,
                    "actual_size": evidence.actual_size,
                    "expected_crc": evidence.expected_crc,
                    "actual_crc": evidence.actual_crc,
                    "expected_sha1": evidence.expected_sha1,
                    "actual_sha1": evidence.actual_sha1,
                    "expected_md5": evidence.expected_md5,
                    "actual_md5": evidence.actual_md5,
                    "path": evidence.path,
                    "archive_path": evidence.archive_path,
                    "archive_member": evidence.archive_member,
                    "merge_name": evidence.merge_name,
                    "optional": evidence.optional,
                    "message": evidence.message,
                    "error": evidence.error,
                    "categories": list(evidence.categories),
                    "cloneof": evidence.cloneof,
                    "isbios": evidence.isbios,
                    "isdevice": evidence.isdevice,
                    "ismechanical": evidence.ismechanical,
                    "runnable": evidence.runnable,
                },
            )

    @staticmethod
    def _merge_unit_stats(result: ScanResult, unit: _MachineResult) -> None:
        result.files_examined += unit.files_examined
        result.archives_examined += unit.archives_examined
        result.items_examined += unit.items_examined
        result.errors += unit.errors
        for evidence in unit.records:
            result.status_counts[evidence.status] += 1

    @staticmethod
    def _make_scan_id(profile) -> str:
        return (
            datetime.now(UTC).strftime("scan_%Y%m%d_%H%M%S_%f") + "_" + str(profile.profile_id)[:8]
        )

    @staticmethod
    def _has_software_catalog(connection: sqlite3.Connection) -> bool:
        names = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        return bool({"mame_software", "mame_software_rom", "mame_software_item"} & names)

    def _scan_generic_physical(
        self,
        result: ScanResult,
        profile,
        sources: list[Path],
        stream_path: Path,
        catalog_items: Iterable[ScanItem],
    ) -> None:
        with stream_path.open("w", encoding="utf-8", newline="\n") as stream:
            self._write_jsonl(
                stream,
                {
                    "record_type": "header",
                    "format": "SERM-SCAN-V1",
                    "scan_id": result.scan_id,
                    "profile_id": result.profile_id,
                    "source": result.source,
                    "system": result.system,
                    "scan_type": result.scan_type,
                    "catalog_label": result.catalog_label,
                    "source_paths": [str(p) for p in sources],
                    "metadata": {
                        "validation": "expected_driven",
                        "persist_mode": "streaming",
                        "filters_applied": False,
                    },
                },
            )
            for item in catalog_items:
                if self._cancelled:
                    break
                evidence = ScanEvidence(
                    machine_name=item.machine_name,
                    rom_name=item.rom_name,
                    status="MISSING",
                    expected_size=item.size,
                    expected_crc=item.crc32.casefold(),
                    expected_sha1=item.sha1.casefold(),
                    optional=item.optional,
                    message="ROM não encontrada",
                )
                self._write_jsonl(
                    stream,
                    {
                        "record_type": "evidence",
                        "machine_name": evidence.machine_name,
                        "rom_name": evidence.rom_name,
                        "status": evidence.status,
                        "expected_size": evidence.expected_size,
                        "actual_size": None,
                        "expected_crc": evidence.expected_crc,
                        "actual_crc": "",
                        "expected_sha1": evidence.expected_sha1,
                        "actual_sha1": "",
                        "expected_md5": "",
                        "actual_md5": "",
                        "path": None,
                        "archive_path": None,
                        "archive_member": None,
                        "merge_name": None,
                        "optional": evidence.optional,
                        "message": evidence.message,
                        "error": None,
                        "categories": [],
                    },
                )
                result.status_counts["MISSING"] += 1
            self._write_jsonl(
                stream,
                {
                    "record_type": "scan_end",
                    "status": "cancelled" if self._cancelled else "completed",
                    "status_counts": dict(result.status_counts),
                },
            )

    def _progress_message(
        self, result: ScanResult, machine: str, completed: int, total: int
    ) -> str:
        percent = completed / total * 100 if total else 100.0
        return f"SCAN | machine={machine} | progresso={completed:,}/{total:,} ({percent:.1f}%) | CURRENT={result.status_counts['CURRENT']:,} | MISSING={result.status_counts['MISSING']:,} | WRONG={result.status_counts['WRONG']:,}"

    def _log_summary(self, result: ScanResult) -> None:
        self._log(
            "INFO",
            f"SCAN | fim | status={dict(result.status_counts)} | arquivos={result.files_examined} | itens={result.items_examined} | duração={result.elapsed_seconds:.2f}s | stream={result.evidence_stream_path}",
        )

    def _log(self, level: str, message: str) -> None:
        getattr(self.logger, level.casefold(), self.logger.info)(message)
        if self.log_callback:
            self.log_callback(level, message)


__all__ = ["RomScanService", "ScanEvidence", "ScanItem", "ScanResult"]
