"""Motor de auditoria bruta do SERM V2.

Regra arquitetural: este serviço NUNCA aplica filtros de seleção. Ele compara
a fonte física contra o catálogo escolhido e grava o universo completo da
auditoria. Os filtros são uma etapa posterior sobre o snapshot persistido.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import time
import zipfile
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from ..runtime.paths import database_path
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

    @property
    def elapsed_seconds(self) -> float:
        return max(0.0, (self.finished_at or time.time()) - self.started_at)


@dataclass(slots=True, frozen=True)
class _PhysicalEntry:
    path: Path
    member: str | None
    size: int
    crc32: str


class RomScanService:
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
        self._log("WARNING", "CANCELAMENTO | solicitado; encerrando no próximo checkpoint")

    def estimate_mame(self, profile, *, database: Path | None = None) -> dict[str, int | str | None]:
        """Retorna somente o universo bruto do catálogo, sem qualquer filtro."""
        db_path = database or database_path()
        if not db_path.is_file():
            return {"machines": 0, "roms": 0, "optional_roms": 0, "disks": 0, "catalog_roms": 0, "catalog_hash": None, "error": str(db_path)}
        scan_type = MameScanSettingsService.load(str(profile.profile_id))
        try:
            with sqlite3.connect(db_path) as connection:
                row = connection.execute("SELECT id, source_hash, mame_build, machine_count FROM mame_listxml_import ORDER BY imported_at DESC, id DESC LIMIT 1").fetchone()
                if row is None:
                    return {"machines": 0, "roms": 0, "optional_roms": 0, "disks": 0, "catalog_roms": 0, "catalog_hash": None, "error": "Nenhum ListXML MAME importado."}
                import_id, source_hash, build, _ = row
                machines = connection.execute("SELECT COUNT(*) FROM mame_machine WHERE import_id=?", (import_id,)).fetchone()[0]
                roms = connection.execute("SELECT COUNT(*) FROM mame_rom WHERE machine_id IN (SELECT id FROM mame_machine WHERE import_id=?)", (import_id,)).fetchone()[0]
                optional = connection.execute("SELECT COUNT(*) FROM mame_rom WHERE optional IN ('yes','true','1') AND machine_id IN (SELECT id FROM mame_machine WHERE import_id=?)", (import_id,)).fetchone()[0]
                disks = connection.execute("SELECT COUNT(*) FROM mame_disk WHERE machine_id IN (SELECT id FROM mame_machine WHERE import_id=?)", (import_id,)).fetchone()[0]
                has_software = self._has_software_catalog(connection)
        except sqlite3.Error as exc:
            return {"machines": 0, "roms": 0, "optional_roms": 0, "disks": 0, "catalog_roms": 0, "catalog_hash": None, "error": str(exc)}
        if scan_type in {"software", "both"} and not has_software:
            return {"machines": int(machines), "roms": int(roms), "optional_roms": int(optional), "disks": int(disks), "catalog_roms": int(roms), "catalog_hash": str(source_hash), "error": "O catálogo de Software Lists do MAME ainda não foi importado para o banco V2."}
        return {"machines": int(machines), "roms": int(roms), "optional_roms": int(optional), "disks": int(disks), "catalog_roms": int(roms), "catalog_hash": str(source_hash), "scan_type": scan_type, "catalog_label": str(build or source_hash[:12]), "error": None}

    def scan(self, profile, *, catalog_items: Iterable[ScanItem] = (), database: Path | None = None) -> ScanResult:
        started = time.time()
        scan_type = MameScanSettingsService.load(str(profile.profile_id)) if str(profile.source).casefold() == "mame" else "full"
        result = ScanResult(scan_id=self._make_scan_id(profile), profile_id=str(profile.profile_id), source=str(profile.source), system=str(profile.system), started_at=started, scan_type=scan_type)
        self._cancelled = False
        sources = [Path(p).expanduser().resolve() for p in profile.source_directories]
        self._log("INFO", f"SCAN | início | scan_id={result.scan_id} | profile_id={profile.profile_id}")
        self._log("INFO", f"SCAN | catálogo={profile.source} › {profile.system} | tipo={scan_type}")
        self._log("INFO", f"SCAN | fontes={len(sources)} | recursivo={bool(profile.recursive)}")
        files = list(self._iter_files(sources, bool(profile.recursive)))
        self._log("INFO", f"ARQUIVOS | candidatos={len(files)}")
        physical = self._index_files(files, result)
        if str(profile.source).casefold() == "mame":
            catalog = self._load_mame_catalog(database or database_path(), profile, result)
            self._match_mame(catalog, physical, result)
        else:
            self._log("INFO", "MATCH | catálogo externo específico pendente; índice físico preservado")
        result.finished_at = time.time()
        self._log_summary(result)
        return result

    def _index_files(self, files: list[Path], result: ScanResult) -> dict[tuple[str, int, str], list[_PhysicalEntry]]:
        index: dict[tuple[str, int, str], list[_PhysicalEntry]] = defaultdict(list)
        last_log = time.monotonic()
        for number, path in enumerate(files, 1):
            if self._cancelled:
                result.status_counts["CANCELLED"] += 1
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
                self._log("ERROR", f"ARQUIVO ERRO | {path} | {type(exc).__name__}: {exc}")
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
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            latest = connection.execute("SELECT id, source_hash, mame_build FROM mame_listxml_import ORDER BY imported_at DESC, id DESC LIMIT 1").fetchone()
            if latest is None:
                raise RuntimeError("Nenhum ListXML MAME importado.")
            result.catalog_hash = str(latest["source_hash"])
            result.catalog_label = str(latest["mame_build"] or latest["source_hash"][:12])
            if result.scan_type in {"software", "both"} and not self._has_software_catalog(connection):
                raise RuntimeError("O catálogo de Software Lists do MAME ainda não foi importado para o banco V2.")
            rows = [dict(row) for row in connection.execute(
                """
                SELECT m.name AS machine_name, m.cloneof, r.name AS rom_name, r.size,
                       lower(coalesce(r.crc,'')) AS expected_crc, lower(coalesce(r.sha1,'')) AS expected_sha1,
                       lower(coalesce(r.md5,'')) AS expected_md5, r.merge, r.optional,
                       m.isbios, m.isdevice, m.ismechanical, m.runnable, m.id AS machine_id
                FROM mame_machine m JOIN mame_rom r ON r.machine_id=m.id
                WHERE m.import_id=? ORDER BY m.name, r.name
                """, (int(latest["id"]),)
            )]
            categories = self._machine_categories(connection, {int(row["machine_id"]) for row in rows})
        if result.scan_type == "software":
            raise RuntimeError("Tipo de scan 'Software' selecionado, mas o catálogo de Software Lists ainda não possui ROMs normalizadas.")
        # Arcade é o catálogo completo de máquinas. Em 'Ambos', a parte Arcade
        # é preservada e a camada Software será adicionada quando normalizada.
        self._log("INFO", f"CATALOGO | MAME | tipo={result.scan_type} | ROMs={len(rows):,} | build={result.catalog_label}")
        for row in rows:
            row["categories"] = tuple(categories.get(int(row["machine_id"]), ()))
        return rows

    @staticmethod
    def _has_software_catalog(connection: sqlite3.Connection) -> bool:
        names = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return bool({"mame_software", "mame_software_rom", "mame_software_item"} & names)

    @staticmethod
    def _machine_categories(connection: sqlite3.Connection, machine_ids: set[int]) -> dict[int, tuple[str, ...]]:
        if not machine_ids:
            return {}
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(mame_classification)")}
        if not {"machine_id", "category"}.issubset(columns):
            return {}
        categories: dict[int, set[str]] = defaultdict(set)
        placeholders = ",".join("?" for _ in machine_ids)
        rows = connection.execute(f"SELECT machine_id, category, subcategory FROM mame_classification WHERE machine_id IN ({placeholders})", tuple(machine_ids)).fetchall()
        for machine_id, category, subcategory in rows:
            for value in (category, subcategory):
                if value:
                    categories[int(machine_id)].add(str(value).strip().casefold())
        return {key: tuple(sorted(value)) for key, value in categories.items()}

    def _match_mame(self, catalog: list[dict], physical: dict[tuple[str, int, str], list[_PhysicalEntry]], result: ScanResult) -> None:
        by_name_size: dict[tuple[str, int], list[_PhysicalEntry]] = defaultdict(list)
        by_name: dict[str, list[_PhysicalEntry]] = defaultdict(list)
        for (name, size, _crc), entries in physical.items():
            by_name_size[(name, size)].extend(entries)
            by_name[name].extend(entries)
        for index, row in enumerate(catalog, 1):
            if self._cancelled:
                result.status_counts["CANCELLED"] += 1
                break
            name = str(row.get("rom_name") or "")
            size = int(row.get("size") or 0)
            crc = str(row.get("expected_crc") or "").lower()
            sha1 = str(row.get("expected_sha1") or "").lower()
            md5 = str(row.get("expected_md5") or "").lower()
            entries = physical.get((Path(name).name.casefold(), size, crc), [])
            same_size = by_name_size.get((Path(name).name.casefold(), size), [])
            same_name = by_name.get(Path(name).name.casefold(), [])
            if entries:
                status = "DUPLICATE" if len(entries) > 1 else "CURRENT"; entry = entries[0]; message = "hash/tamanho correspondentes"
            elif same_size:
                status = "WRONG"; entry = same_size[0]; message = "nome e tamanho correspondem, mas CRC diverge"
            elif same_name:
                status = "WRONG"; entry = same_name[0]; message = "nome corresponde, mas tamanho/CRC divergem"
            else:
                status = "MISSING"; entry = None; message = "ROM não localizada nas fontes"
            result.evidence.append(ScanEvidence(
                machine_name=str(row["machine_name"]), rom_name=name, status=status,
                expected_size=size, actual_size=entry.size if entry else None,
                expected_crc=crc, actual_crc=entry.crc32 if entry else "", expected_sha1=sha1,
                expected_md5=md5, path=str(entry.path) if entry else None,
                archive_path=str(entry.path) if entry and entry.member else None,
                archive_member=entry.member if entry else None, merge_name=row.get("merge"),
                optional=str(row.get("optional") or "").casefold() in {"yes", "true", "1"}, message=message,
                categories=tuple(row.get("categories") or ()), cloneof=row.get("cloneof"),
                isbios=row.get("isbios"), isdevice=row.get("isdevice"), ismechanical=row.get("ismechanical"),
                runnable=row.get("runnable"),
            ))
            result.status_counts[status] += 1
            if index == 1 or index % 5000 == 0 or index == len(catalog):
                self._log("INFO", f"MATCH | progresso={index:,}/{len(catalog):,} | CURRENT={result.status_counts['CURRENT']:,} | WRONG={result.status_counts['WRONG']:,} | MISSING={result.status_counts['MISSING']:,} | DUPLICATE={result.status_counts['DUPLICATE']:,}")

    def _crc32(self, path: Path) -> str:
        value = 0
        with path.open("rb") as handle:
            while chunk := handle.read(self.CHUNK_SIZE):
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
        self._log("INFO", f"SCAN | finalizado | {counts}")
        self._log("INFO", f"SCAN | arquivos={result.files_examined} | archives={result.archives_examined} | itens={result.items_examined} | duração={result.elapsed_seconds:.2f}s")

    def _log(self, level: str, message: str) -> None:
        getattr(self.logger, level.casefold(), self.logger.info)(message)
        if self.log_callback:
            self.log_callback(level, message)

    @staticmethod
    def _make_scan_id(profile) -> str:
        seed = f"{profile.profile_id}|{time.time_ns()}|{os.getpid()}".encode()
        return hashlib.sha1(seed).hexdigest()[:16]


__all__ = ["LogCallback", "ProgressCallback", "RomScanService", "ScanEvidence", "ScanItem", "ScanResult"]
