"""Scanner de ROMs orientado a reconstrução.

O Scan ROMs valida a ROM física, não apenas o CRC armazenado no diretório
central do ZIP. Para ZIPs, cada membro esperado é lido em streaming e o
CRC/tamanho (e SHA1 quando informado pelo LISTXML) são recalculados.
"""
from __future__ import annotations

import binascii
import hashlib
import logging
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Iterable

from app.core.models.scan_result import MachineScanResult, RomScanResult, ScanStatus
from app.mame.rom_source_index import RomSourceCandidate, RomSourceIndexer, RomSourceIndex
from app.mame.scan_manifest import ScanMachineRecord, ScanManifestWriter, ScanRomRecord, ScanSource

logger = logging.getLogger(__name__)
DEFAULT_CHUNK_SIZE = 1024 * 1024
ProgressCallback = Callable[[int, int, RomScanResult], None]
MachineCallback = Callable[[MachineScanResult], None]
LogCallback = Callable[[str], None]


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _hash(value: Any) -> str:
    return str(value or "").strip().lower()


class RomScanEngine:
    """Scanner streaming por machine com manifesto persistente."""

    def __init__(self, rom_paths: Iterable[str | Path], *, max_workers: int = 1, progress_callback: ProgressCallback | None = None, machine_callback: MachineCallback | None = None, log_callback: LogCallback | None = None, enable_alternate_search: bool = True, include_chds: bool = True, chunk_size: int = DEFAULT_CHUNK_SIZE, manifest_directory: str | Path | None = None) -> None:
        self.rom_paths = [Path(p).expanduser().resolve() for p in rom_paths]
        self.max_workers = max(1, int(max_workers))
        self.progress_callback = progress_callback
        self.machine_callback = machine_callback
        self.log_callback = log_callback
        self.enable_alternate_search = bool(enable_alternate_search)
        self.include_chds = bool(include_chds)
        self.chunk_size = max(4096, int(chunk_size))
        self.cancel_event = threading.Event()
        self.manifest_directory = Path(manifest_directory) if manifest_directory else Path(__file__).resolve().parents[2] / "data" / "database" / "scan"
        self.source_index_path = self.manifest_directory / "rom_source_index.jsonl"
        self._source_lookup: dict[tuple[str, int], list[RomSourceCandidate]] = {}
        self._source_index_ready = False
        self.manifest_writer: ScanManifestWriter | None = None

    def cancel(self) -> None:
        """Solicita cancelamento cooperativo."""
        self.cancel_event.set()

    @property
    def cancelled(self) -> bool:
        """Indica se o scan foi cancelado."""
        return self.cancel_event.is_set()

    def _log(self, message: str, *args: Any) -> None:
        text = message % args if args else message
        logger.info(text)
        if self.log_callback:
            self.log_callback(text)

    def _crc_file(self, path: Path) -> tuple[int, str, str]:
        """Lê um arquivo físico em streaming e calcula tamanho, CRC32 e SHA1."""
        size = 0
        crc = 0
        sha1 = hashlib.sha1()
        with path.open("rb") as handle:
            while True:
                if self.cancelled:
                    raise InterruptedError
                chunk = handle.read(self.chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                crc = binascii.crc32(chunk, crc)
                sha1.update(chunk)
        return size, f"{crc & 0xFFFFFFFF:08x}", sha1.hexdigest()

    def _crc_zip_member(self, archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> tuple[int, str, str]:
        """Lê o conteúdo descompactado de um membro ZIP em streaming."""
        size = 0
        crc = 0
        sha1 = hashlib.sha1()
        with archive.open(info, "r") as handle:
            while True:
                if self.cancelled:
                    raise InterruptedError
                chunk = handle.read(self.chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                crc = binascii.crc32(chunk, crc)
                sha1.update(chunk)
        return size, f"{crc & 0xFFFFFFFF:08x}", sha1.hexdigest()

    def _scan_zip(self, machine_name: str, rom: Any, zip_path: Path) -> RomScanResult | None:
        """Localiza e verifica fisicamente uma ROM dentro do ZIP.

        O CRC presente no diretório central é usado apenas para localização.
        A validade final é determinada pelo conteúdo efetivamente descompactado.
        """
        name = str(_get(rom, "name", ""))
        expected_size = _int(_get(rom, "size", 0))
        expected_crc = _hash(_get(rom, "crc", ""))
        expected_sha1 = _hash(_get(rom, "sha1", ""))
        try:
            with zipfile.ZipFile(zip_path, "r") as archive:
                target = None
                fallback = None
                normalized_name = name.replace("\\", "/")
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    if info.filename.replace("\\", "/") == normalized_name:
                        target = info
                        break
                    if self.enable_alternate_search and Path(info.filename).name.lower() == Path(name).name.lower() and fallback is None:
                        fallback = info
                info = target or fallback
                if info is None:
                    return None
                actual_size, actual_crc, actual_sha1 = self._crc_zip_member(archive, info)
                valid = (expected_size <= 0 or actual_size == expected_size) and (not expected_crc or actual_crc == expected_crc)
                if expected_sha1:
                    valid = valid and actual_sha1 == expected_sha1
                return RomScanResult(machine_name=machine_name, rom_name=name, expected_size=expected_size, actual_size=actual_size, expected_crc=expected_crc, actual_crc=actual_crc, expected_sha1=expected_sha1, actual_sha1=actual_sha1, status=ScanStatus.VALID if valid else ScanStatus.INVALID, path=zip_path, archive_path=zip_path, archive_member=info.filename, merge=_get(rom, "merge"), optional=bool(_get(rom, "optional", False)), message="ROM válida." if valid else "ROM encontrada, mas conteúdo CRC/tamanho/SHA1 inválido.")
        except InterruptedError:
            raise
        except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, RuntimeError, EOFError, ValueError) as exc:
            return RomScanResult(machine_name=machine_name, rom_name=name, expected_size=expected_size, expected_crc=expected_crc, expected_sha1=expected_sha1, status=ScanStatus.ERROR, path=zip_path, archive_path=zip_path, message=str(exc), error=str(exc))

    def _scan_direct(self, machine_name: str, rom: Any) -> RomScanResult:
        """Procura a ROM nas origens e valida o conteúdo em streaming."""
        name = str(_get(rom, "name", ""))
        expected_size = _int(_get(rom, "size", 0))
        expected_crc = _hash(_get(rom, "crc", ""))
        expected_sha1 = _hash(_get(rom, "sha1", ""))
        if not name:
            return RomScanResult(machine_name=machine_name, rom_name="", expected_size=expected_size, expected_crc=expected_crc, status=ScanStatus.ERROR, message="ROM sem nome.")
        for base in self.rom_paths:
            zip_path = base / f"{machine_name}.zip"
            if zip_path.is_file():
                result = self._scan_zip(machine_name, rom, zip_path)
                if result is not None:
                    return result
            raw = base / machine_name / name
            if raw.is_file():
                try:
                    actual_size, actual_crc, actual_sha1 = self._crc_file(raw)
                    valid = (expected_size <= 0 or actual_size == expected_size) and (not expected_crc or actual_crc == expected_crc)
                    if expected_sha1:
                        valid = valid and actual_sha1 == expected_sha1
                    return RomScanResult(machine_name=machine_name, rom_name=name, expected_size=expected_size, actual_size=actual_size, expected_crc=expected_crc, actual_crc=actual_crc, expected_sha1=expected_sha1, actual_sha1=actual_sha1, status=ScanStatus.VALID if valid else ScanStatus.INVALID, path=raw, merge=_get(rom, "merge"), optional=bool(_get(rom, "optional", False)), message="ROM válida." if valid else "ROM encontrada, mas inválida.")
                except InterruptedError:
                    raise
                except OSError as exc:
                    return RomScanResult(machine_name=machine_name, rom_name=name, expected_size=expected_size, expected_crc=expected_crc, status=ScanStatus.ERROR, path=raw, message=str(exc), error=str(exc))
        return RomScanResult(machine_name=machine_name, rom_name=name, expected_size=expected_size, expected_crc=expected_crc, expected_sha1=expected_sha1, status=ScanStatus.MISSING, merge=_get(rom, "merge"), optional=bool(_get(rom, "optional", False)), message="ROM não encontrada.")

    def _build_source_catalog(self, machines: list[Any]) -> None:
        """Constrói o índice físico somente quando existem ROMs ausentes."""
        signatures: set[tuple[str, int]] = set()
        for machine in machines:
            for rom in (_get(machine, "roms", []) or []):
                crc = _hash(_get(rom, "crc", ""))
                size = _int(_get(rom, "size", 0))
                if crc and size > 0:
                    signatures.add((crc, size))
        if not signatures:
            return
        self._log("Construindo catálogo físico filtrado: %d assinaturas CRC/tamanho.", len(signatures))
        indexer = RomSourceIndexer(self.rom_paths, self.source_index_path, expected_signatures=signatures, chunk_size=self.chunk_size, log_callback=self._log, cancel_event=self.cancel_event)
        stats = indexer.build()
        if stats.get("cancelled"):
            return
        self._source_lookup.clear()
        index = RomSourceIndex(self.source_index_path)
        for candidate in index.iter_candidates():
            self._source_lookup.setdefault((candidate.crc.lower(), candidate.size), []).append(candidate)
        self._source_index_ready = True
        self._log("Catálogo pronto: %s candidatos relevantes.", stats.get("candidates", 0))

    def _resolve_missing(self, result: RomScanResult) -> RomScanResult:
        """Resolve uma ROM ausente usando o catálogo físico."""
        if result.status is not ScanStatus.MISSING or not self._source_index_ready:
            return result
        candidates = self._source_lookup.get((_hash(result.expected_crc), result.expected_size), [])
        for candidate in candidates:
            if candidate.kind == "zip":
                result.status = ScanStatus.VALID
                result.path = Path(candidate.archive)
                result.archive_path = Path(candidate.archive)
                result.archive_member = candidate.member
                result.actual_size = candidate.size
                result.actual_crc = candidate.crc
                result.actual_sha1 = candidate.sha1 or ""
                result.message = f"ROM encontrada em outra machine: {Path(candidate.archive).stem}."
                return result
            if candidate.kind == "file":
                result.status = ScanStatus.VALID
                result.path = Path(candidate.archive)
                result.actual_size = candidate.size
                result.actual_crc = candidate.crc
                result.actual_sha1 = candidate.sha1 or ""
                result.message = "ROM encontrada como arquivo físico alternativo."
                return result
        return result

    def _machine(self, machine: Any, progress_start: int, progress_total: int) -> MachineScanResult:
        """Escaneia uma machine ROM por ROM."""
        name = str(_get(machine, "name", ""))
        result = MachineScanResult(machine_name=name, description=str(_get(machine, "description", "") or ""), cloneof=_get(machine, "cloneof"))
        for rom in (_get(machine, "roms", []) or []):
            if self.cancelled:
                break
            item = self._scan_direct(name, rom)
            result.roms.append(item)
            if self.progress_callback:
                self.progress_callback(progress_start + len(result.roms), progress_total, item)
        if self.machine_callback:
            self.machine_callback(result)
        return result

    def _persist(self, results: list[MachineScanResult]) -> None:
        """Persiste o resultado no manifesto JSONL."""
        if self.manifest_writer is None:
            return
        for machine in results:
            self.manifest_writer.machine_started(ScanMachineRecord(name=machine.machine_name, description=machine.description, cloneof=machine.cloneof, rom_count=machine.total))
            for item in machine.roms:
                source = None
                if item.archive_path:
                    source = ScanSource(kind="zip", archive=str(item.archive_path), member=item.archive_member, machine=item.archive_path.stem)
                elif item.path:
                    source = ScanSource(kind="file", archive=str(item.path), machine=item.machine_name)
                status = {ScanStatus.VALID: "valid", ScanStatus.MISSING: "missing", ScanStatus.INVALID: "invalid", ScanStatus.ERROR: "error", ScanStatus.CANCELLED: "cancelled"}.get(item.status, "unknown")
                self.manifest_writer.write_rom(ScanRomRecord(machine=item.machine_name, machine_description=machine.description, rom_name=item.rom_name, expected_size=item.expected_size, expected_crc=item.expected_crc, expected_sha1=item.expected_sha1 or None, merge=item.merge, status=status, actual_size=item.actual_size, actual_crc=item.actual_crc, actual_sha1=item.actual_sha1 or None, source=source, required=not item.optional, optional=item.optional, error=item.error))
            self.manifest_writer.machine_finished(ScanMachineRecord(name=machine.machine_name, description=machine.description, cloneof=machine.cloneof, rom_count=machine.total, status="completed" if not self.cancelled else "cancelled"))

    def scan(self, machines: Iterable[Any], *, mame_version: str = "unknown", xml_path: str | Path | None = None, metadata: dict[str, Any] | None = None) -> list[MachineScanResult]:
        """Executa o scan físico e persiste o manifesto somente ao final."""
        self.cancel_event.clear()
        machines_list = list(machines)
        valid_sources = [p for p in self.rom_paths if p.is_dir()]
        if not valid_sources:
            raise RuntimeError("Nenhuma pasta de origem de ROM válida foi configurada. O scan foi interrompido para evitar gerar um manifesto falso.")
        self.rom_paths = valid_sources
        if not machines_list:
            raise RuntimeError("O LISTXML ativo não contém machines para escanear.")
        total = sum(len(_get(m, "roms", []) or []) for m in machines_list)
        if total <= 0:
            raise RuntimeError("O LISTXML ativo não contém ROMs para escanear.")
        self._log("Iniciando scan físico: %d machines, %d ROMs, %d origem(ns).", len(machines_list), total, len(self.rom_paths))
        for source in self.rom_paths:
            self._log("Origem física: %s", source)

        self.manifest_directory.mkdir(parents=True, exist_ok=True)
        self.manifest_writer = ScanManifestWriter(directory=self.manifest_directory)
        self.manifest_writer.start(version=mame_version, xml_path=xml_path, source_paths=self.rom_paths, machine_count=len(machines_list), metadata=metadata or {})

        offsets: list[int] = []
        offset = 0
        for machine in machines_list:
            offsets.append(offset)
            offset += len(_get(machine, "roms", []) or [])

        results: list[MachineScanResult | None] = [None] * len(machines_list)
        if self.max_workers == 1:
            for index, machine in enumerate(machines_list):
                if self.cancelled:
                    break
                results[index] = self._machine(machine, offsets[index], total)
        else:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(self._machine, machine, offsets[index], total): index for index, machine in enumerate(machines_list)}
                for future in as_completed(futures):
                    if self.cancelled:
                        break
                    results[futures[future]] = future.result()

        final = [r for r in results if r is not None]
        missing = [item for machine in final for item in machine.roms if item.status is ScanStatus.MISSING]
        if missing and self.enable_alternate_search and not self.cancelled:
            self._log("%d ROMs ausentes na localização direta; iniciando busca no fullset.", len(missing))
            self._build_source_catalog(machines_list)
            for item in missing:
                self._resolve_missing(item)

        self._persist(final)
        self.manifest_writer.write_summary(status="cancelled" if self.cancelled else "completed", data={"planned": total, "processed": sum(m.total for m in final), "found": sum(m.found for m in final), "valid": sum(m.valid for m in final), "missing": sum(m.missing for m in final), "invalid": sum(m.invalid for m in final), "errors": sum(m.error_count for m in final)})
        self.manifest_writer.finish(status="cancelled" if self.cancelled else "completed")
        self._log("Scan físico finalizado: %d/%d ROMs processadas.", sum(m.total for m in final), total)
        return final

    scan_machines = scan
