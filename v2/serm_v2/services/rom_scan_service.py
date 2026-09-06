"""Motor de scan V2 orientado por perfil.

O serviço indexa fontes físicas e, quando o perfil é MAME, confronta cada
ROM do catálogo relacional com os arquivos/entries encontrados. Os mesmos
eventos seguem para logging e para a GUI.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import time
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from ..runtime.paths import database_path

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
    evidence: list[ScanEvidence] = field(default_factory=list)

    @property
    def elapsed_seconds(self) -> float:
        end = self.finished_at or time.time()
        return max(0.0, end - self.started_at)


@dataclass(slots=True, frozen=True)
class _PhysicalEntry:
    path: Path
    member: str | None
    size: int
    crc32: str


class RomScanService:
    """Executa scan físico seguro e observável sobre fontes temporárias."""

    CHUNK_SIZE = 1024 * 1024
    LOG_EVERY_FILES = 250
    LOG_EVERY_SECONDS = 2.0

    def __init__(self, *, logger: logging.Logger | None = None,
                 log_callback: LogCallback | None = None,
                 progress_callback: ProgressCallback | None = None) -> None:
        self.logger = logger or logging.getLogger("serm.scan")
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        self._log("INFO", "CANCELAMENTO | solicitação recebida; encerrando no próximo checkpoint")

    def scan(self, profile, *, catalog_items: Iterable[ScanItem] = (), database: Path | None = None) -> ScanResult:
        scan_id = self._make_scan_id(profile)
        started = time.time()
        result = ScanResult(scan_id=scan_id, profile_id=str(profile.profile_id),
                            source=str(profile.source), system=str(profile.system), started_at=started)
        self._cancelled = False
        sources = [Path(p).expanduser().resolve() for p in profile.source_directories]
        self._log("INFO", "SCAN | início")
        self._log("INFO", f"SCAN | scan_id={scan_id}")
        self._log("INFO", f"SCAN | profile_id={profile.profile_id} | schema={getattr(profile, 'schema_version', 1)}")
        self._log("INFO", f"SCAN | fonte={profile.source} | sistema={profile.system}")
        self._log("INFO", f"SCAN | fontes={len(sources)} | recursivo={bool(profile.recursive)}")
        for index, source in enumerate(sources, 1):
            self._log("INFO", f"SCAN | fonte[{index}]={source}")

        files = list(self._iter_files(sources, bool(profile.recursive)))
        self._log("INFO", f"ARQUIVOS | candidatos={len(files)}")
        physical = self._index_files(files, result)
        if str(profile.source).casefold() == "mame":
            catalog = self._load_mame_catalog(database or database_path(), profile, result)
            self._match_mame(catalog, physical, result)
        else:
            self._log("INFO", "MATCH | catálogo específico ainda não conectado; mantendo índice físico")
        result.finished_at = time.time()
        self._log_summary(result)
        return result

    def _index_files(self, files: list[Path], result: ScanResult) -> dict[tuple[str, int, str], list[_PhysicalEntry]]:
        index: dict[tuple[str, int, str], list[_PhysicalEntry]] = defaultdict(list)
        last_log = time.monotonic()
        for number, path in enumerate(files, 1):
            if self._cancelled:
                result.status_counts["CANCELLED"] += 1
                self._log("WARNING", f"SCAN | cancelado durante indexação={number}/{len(files)}")
                break
            try:
                result.files_examined += 1
                if path.suffix.casefold() == ".zip":
                    result.archives_examined += 1
                    with zipfile.ZipFile(path) as archive:
                        for info in archive.infolist():
                            if info.is_dir():
                                continue
                            result.items_examined += 1
                            key = (Path(info.filename).name.casefold(), info.file_size, f"{info.CRC:08x}")
                            index[key].append(_PhysicalEntry(path, info.filename, info.file_size, f"{info.CRC:08x}"))
                else:
                    result.items_examined += 1
                    size = path.stat().st_size
                    crc = self._crc32(path)
                    index[(path.name.casefold(), size, crc)].append(_PhysicalEntry(path, None, size, crc))
            except (OSError, zipfile.BadZipFile) as exc:
                result.errors += 1
                result.status_counts["ERROR"] += 1
                self._log("ERROR", f"ARQUIVO ERRO | arquivo={path} | {type(exc).__name__}: {exc}")
            if self.progress_callback:
                self.progress_callback(number, len(files))
            now = time.monotonic()
            if number == 1 or number % self.LOG_EVERY_FILES == 0 or now - last_log >= self.LOG_EVERY_SECONDS or number == len(files):
                self._log("INFO", f"ARQUIVOS | progresso={number}/{len(files)} | arquivos={result.files_examined} | itens={result.items_examined} | erros={result.errors}")
                last_log = now
        return index

    def _load_mame_catalog(self, db_path: Path, profile, result: ScanResult) -> list[dict]:
        if not db_path.is_file():
            raise RuntimeError(f"Banco do catálogo MAME não encontrado: {db_path}")
        query = """
            SELECT m.name AS machine_name, m.cloneof, r.name AS rom_name, r.size,
                   lower(coalesce(r.crc,'')), lower(coalesce(r.sha1,'')), lower(coalesce(r.md5,'')),
                   r.merge, r.optional, m.isbios, m.isdevice, m.runnable
            FROM mame_machine m JOIN mame_rom r ON r.machine_id=m.id
            JOIN mame_listxml_import i ON i.id=m.import_id
            WHERE i.id=(SELECT id FROM mame_listxml_import ORDER BY imported_at DESC, id DESC LIMIT 1)
        """
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = [dict(row) for row in connection.execute(query)]
            source = connection.execute("SELECT source_hash FROM mame_listxml_import WHERE id=(SELECT id FROM mame_listxml_import ORDER BY imported_at DESC,id DESC LIMIT 1)").fetchone()
        result.catalog_hash = str(source[0]) if source else None
        self._log("INFO", f"CATALOGO | MAME | ROMs={len(rows):,} | hash={result.catalog_hash[:16] if result.catalog_hash else 'desconhecido'}")
        return self._filter_mame_rows(rows, profile)

    @staticmethod
    def _filter_mame_rows(rows: list[dict], profile) -> list[dict]:
        filtered = []
        set_type = str(getattr(profile, "mame_set_type", "split"))
        clone_policy = str(getattr(profile, "mame_clone_policy", "with_clones"))
        for row in rows:
            if not getattr(profile, "mame_include_bios", False) and str(row.get("isbios") or "").casefold() == "yes":
                continue
            if not getattr(profile, "mame_include_devices", False) and str(row.get("isdevice") or "").casefold() == "yes":
                continue
            if getattr(profile, "mame_working_only", False) and str(row.get("runnable") or "").casefold() not in {"yes", "true"}:
                continue
            if clone_policy == "parents_only" and row.get("cloneof"):
                continue
            if not getattr(profile, "mame_include_optional", True) and str(row.get("optional") or "").casefold() in {"yes", "true", "1"}:
                continue
            # set_type permanece explícito no perfil; a resolução física usa os
            # campos merge/clone do catálogo e não renomeia arquivos.
            row["set_type"] = set_type
            filtered.append(row)
        return filtered

    def _match_mame(self, catalog: list[dict], physical: dict[tuple[str, int, str], list[_PhysicalEntry]], result: ScanResult) -> None:
        self._log("INFO", f"MATCH | MAME | catálogo filtrado={len(catalog):,} ROMs")
        duplicate_keys = {key for key, entries in physical.items() if len(entries) > 1}
        matched = 0
        for index, row in enumerate(catalog, 1):
            if self._cancelled:
                result.status_counts["CANCELLED"] += 1
                break
            name = str(row.get("rom_name") or "")
            size = row.get("size")
            crc = str(row.get("lower(coalesce(r.crc,''))") or "").lower()
            sha1 = str(row.get("lower(coalesce(r.sha1,''))") or "").lower()
            md5 = str(row.get("lower(coalesce(r.md5,''))") or "").lower()
            key = (Path(name).name.casefold(), int(size or 0), crc)
            entries = physical.get(key, [])
            optional = str(row.get("optional") or "").casefold() in {"yes", "true", "1"}
            if entries:
                status = "DUPLICATE" if key in duplicate_keys else "CURRENT"
                entry = entries[0]
                matched += 1
                evidence = ScanEvidence(str(row["machine_name"]), name, status, int(size or 0), entry.size,
                    crc, entry.crc32, sha1, "", md5, "", str(entry.path), str(entry.path) if entry.member else None,
                    entry.member, row.get("merge"), optional, "hash/tamanho correspondentes")
            else:
                status = "MISSING"
                evidence = ScanEvidence(str(row["machine_name"]), name, status, int(size or 0), None,
                    crc, "", sha1, "", md5, "", None, None, None, row.get("merge"), optional,
                    "ROM não localizada nas fontes")
            result.evidence.append(evidence)
            result.status_counts[status] += 1
            if index == 1 or index % 5000 == 0 or index == len(catalog):
                self._log("INFO", f"MATCH | progresso={index:,}/{len(catalog):,} | CURRENT={result.status_counts['CURRENT']:,} | MISSING={result.status_counts['MISSING']:,} | DUPLICATE={result.status_counts['DUPLICATE']:,}")
        self._log("INFO", f"MATCH | MAME | concluído | correspondentes={matched:,} | faltantes={result.status_counts['MISSING']:,}")

    @staticmethod
    def _crc32(path: Path) -> str:
        import zlib
        value = 0
        with path.open("rb") as handle:
            while chunk := handle.read(RomScanService.CHUNK_SIZE):
                value = zlib.crc32(chunk, value)
        return f"{value & 0xffffffff:08x}"

    def _iter_files(self, sources: list[Path], recursive: bool) -> Iterable[Path]:
        for source in sources:
            if not source.is_dir():
                self._log("WARNING", f"FONTE | diretório inexistente ou inválido={source}")
                continue
            iterator = source.rglob("*") if recursive else source.glob("*")
            for path in iterator:
                if path.is_file():
                    yield path

    def _log_summary(self, result: ScanResult) -> None:
        counts = " | ".join(f"{key}={value}" for key, value in sorted(result.status_counts.items())) or "nenhum resultado"
        self._log("INFO", "SCAN | finalizando")
        self._log("INFO", f"SCAN | resultado | {counts}")
        self._log("INFO", f"SCAN | arquivos={result.files_examined} | archives={result.archives_examined} | itens={result.items_examined} | erros={result.errors} | duração={result.elapsed_seconds:.2f}s")
        self._log("INFO", f"SCAN | scan_id={result.scan_id} | profile_id={result.profile_id} | catalog_hash={result.catalog_hash or '—'}")

    def _log(self, level: str, message: str) -> None:
        getattr(self.logger, level.casefold(), self.logger.info)(message)
        if self.log_callback:
            self.log_callback(level, message)

    @staticmethod
    def _make_scan_id(profile) -> str:
        seed = f"{profile.profile_id}|{time.time_ns()}|{os.getpid()}".encode()
        return hashlib.sha1(seed).hexdigest()[:16]


__all__ = ["LogCallback", "ProgressCallback", "RomScanService", "ScanEvidence", "ScanItem", "ScanResult"]
