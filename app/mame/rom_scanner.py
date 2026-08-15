"""Scanner de ROMs MAME orientado a I/O e tolerante a fontes ruins."""
from __future__ import annotations

import logging
import os
import zipfile
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Iterable, List

from app.core.models.scan_result import ScanResult, MachineScanResult, RomFile, ScanStatus
from app.mame.integrity import digest_file, digest_stream, matches_digest

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[int, int, str], None]


class RomScanner:
    def __init__(self, rom_paths: List[Path], *, workers: int | None = None, chunk_size: int = 1024 * 1024):
        self.rom_paths = [Path(p) for p in rom_paths if Path(p).is_dir()]
        self.workers = max(1, min(workers or (os.cpu_count() or 2), 16))
        self.chunk_size = chunk_size
        self._digest_cache: dict[tuple[str, int, int, bool], object] = {}

    def scan_machines(self, machines: List[dict], *, progress_callback: ProgressCallback | None = None) -> ScanResult:
        result = ScanResult(version="unknown")
        jobs = [(machine, rom_info) for machine in machines for rom_info in machine.get("roms", [])]
        completed = 0
        by_machine: dict[str, MachineScanResult] = {
            m.get("name", ""): MachineScanResult(name=m.get("name", ""), description=m.get("description", ""), cloneof=m.get("cloneof"))
            for m in machines
        }
        with ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="mame-scan") as pool:
            futures = {pool.submit(self._scan_rom, rom_info, machine.get("name", "")): (machine.get("name", ""), rom_info) for machine, rom_info in jobs}
            for future in as_completed(futures):
                machine_name, _ = futures[future]
                try:
                    by_machine[machine_name].roms.append(future.result())
                except Exception:
                    logger.exception("Falha isolada ao validar ROM de %s", machine_name)
                completed += 1
                if progress_callback:
                    progress_callback(completed, len(jobs), machine_name)
        result.machines = [by_machine[m.get("name", "")] for m in machines]
        for machine in result.machines:
            machine.update_status()
            machine.total_size = sum(r.size for r in machine.roms if r.status == ScanStatus.OK)
        result.total_machines = len(result.machines)
        result.update_summary()
        return result

    def _scan_single_machine(self, machine_data: dict) -> MachineScanResult:
        name = machine_data.get("name", "")
        machine_result = MachineScanResult(name=name, description=machine_data.get("description", ""), cloneof=machine_data.get("cloneof"))
        with ThreadPoolExecutor(max_workers=min(self.workers, max(1, len(machine_data.get("roms", []))))) as pool:
            futures = [pool.submit(self._scan_rom, rom, name) for rom in machine_data.get("roms", [])]
            machine_result.roms = [future.result() for future in futures]
        machine_result.update_status()
        machine_result.total_size = sum(r.size for r in machine_result.roms if r.status == ScanStatus.OK)
        return machine_result

    def _scan_rom(self, rom_info: dict, machine_name: str) -> RomFile:
        expected = RomFile(
            name=rom_info.get("name", ""), size=int(rom_info.get("size", 0) or 0),
            crc=(rom_info.get("crc", "") or "").lower(),
            sha1=(rom_info.get("sha1") or "").lower() or None,
            merge=rom_info.get("merge"), status=ScanStatus.MISSING,
        )
        candidates: list[tuple[str, Path]] = []
        for root in self.rom_paths:
            for archive_name in {machine_name, expected.merge} - {None, ""}:
                archive = root / f"{archive_name}.zip"
                if archive.is_file():
                    candidates.append(("zip", archive))
                archive7z = root / f"{archive_name}.7z"
                if archive7z.is_file():
                    candidates.append(("7z", archive7z))
            loose = root / expected.name
            if loose.is_file():
                candidates.append(("file", loose))
        saw_corrupt = False
        for kind, path in candidates:
            try:
                actual = self._validate_candidate(kind, path, expected.name, bool(expected.sha1))
                if actual is None:
                    continue
                expected.found_in = path
                expected.found_member = expected.name if kind in {"zip", "7z"} else None
                expected.actual_size, expected.actual_crc, expected.actual_sha1 = actual.size, actual.crc, actual.sha1
                if matches_digest(actual, size=expected.size, crc=expected.crc, sha1=expected.sha1 or ""):
                    expected.status = ScanStatus.OK
                    return expected
                saw_corrupt = True
            except (OSError, zipfile.BadZipFile, KeyError, NotImplementedError) as exc:
                logger.warning("Falha ao ler candidato %s: %s", path, exc)
                saw_corrupt = True
        # Segunda etapa: procurar o mesmo conteúdo em outro set ou com outro
        # nome interno. O CRC/tamanho do diretório ZIP fazem a triagem; SHA-1
        # é calculado apenas para candidatos que já passaram nessa triagem.
        alternate = self._search_alternate(expected)
        if alternate is not None:
            expected.found_in, expected.found_member = alternate[0], alternate[1]
            actual = alternate[2]
            expected.actual_size, expected.actual_crc, expected.actual_sha1 = actual.size, actual.crc, actual.sha1
            expected.status = ScanStatus.FIXABLE
            return expected
        expected.status = ScanStatus.CORRUPTED if saw_corrupt else ScanStatus.MISSING
        return expected

    def _search_alternate(self, expected: RomFile):
        for root in self.rom_paths:
            for archive in root.glob("*.zip"):
                try:
                    with zipfile.ZipFile(archive, "r") as zf:
                        for info in zf.infolist():
                            if info.is_dir() or info.file_size != expected.size or info.CRC != int(expected.crc or "0", 16):
                                continue
                            with zf.open(info, "r") as stream:
                                actual = digest_stream(stream, need_sha1=bool(expected.sha1), chunk_size=self.chunk_size)
                            if matches_digest(actual, size=expected.size, crc=expected.crc, sha1=expected.sha1 or ""):
                                return archive, info.filename, actual
                except (OSError, zipfile.BadZipFile):
                    continue
        return None

    def _validate_candidate(self, kind: str, path: Path, member: str, need_sha1: bool):
        if kind == "file":
            return digest_file(path, need_sha1=need_sha1, chunk_size=self.chunk_size)
        if kind == "zip":
            with zipfile.ZipFile(path, "r") as archive:
                info = archive.getinfo(member)
                with archive.open(info, "r") as stream:
                    return digest_stream(stream, need_sha1=need_sha1, chunk_size=self.chunk_size)
        if kind == "7z":
            try:
                import py7zr
            except ImportError as exc:
                raise NotImplementedError("backend py7zr não instalado") from exc
            with py7zr.SevenZipFile(path, mode="r") as archive:
                entries = {entry.filename: entry for entry in archive.list()}
                entry = entries.get(member)
                if entry is None:
                    return None
                uncompressed = int(getattr(entry, "uncompressed", 0) or 0)
                if uncompressed > 64 * 1024 * 1024:
                    raise NotImplementedError("membro 7Z maior que 64 MiB exige backend de streaming")
                with tempfile.TemporaryDirectory(prefix="mame-7z-") as temp_dir:
                    archive.extract(path=temp_dir, targets=[member])
                    extracted = Path(temp_dir) / member
                    if not extracted.is_file():
                        return None
                    return digest_file(extracted, need_sha1=need_sha1, chunk_size=self.chunk_size)
        return None
