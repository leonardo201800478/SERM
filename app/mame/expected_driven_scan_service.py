"""Scanner orientado pelo LISTXML, sem varredura global do HDD.

Este é o caminho de teste da nova arquitetura de scan. A direção do trabalho
é XML -> requisito -> existência física -> validação mínima. O HDD nunca é
usado como fonte para descobrir o que deve ser escaneado.

Regras de performance:

* CHD: somente ``<source>/<machine>/<disk>.chd``; inexistente = MISSING
  imediato, sem SHA1/chdman e sem procurar em qualquer outro lugar.
* ROM: somente ``<source>/<machine>.zip`` e ``<source>/<machine>/``.
* ZIP: o diretório central fornece nome, CRC e tamanho; o conteúdo só é lido
  para um membro que realmente corresponde a um requisito e possui SHA-1 a
  validar.
* Resultados são enviados para um writer dedicado em paralelo, portanto a
  persistência JSONL não é uma segunda etapa do scan.
"""
from __future__ import annotations

import hashlib
import logging
import os
import queue
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
import xml.etree.ElementTree as ET

from app.core.models.scan_result import (
    MachineScanResult,
    RomScanResult,
    ScanItemType,
    ScanResult,
    ScanStatus,
)
from app.mame.scan_manifest import ScanMachineRecord, ScanManifestWriter, ScanRomRecord, ScanSource

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, MachineScanResult], None]
MachineCallback = Callable[[MachineScanResult], None]


@dataclass(frozen=True, slots=True)
class ExpectedRom:
    name: str
    size: int
    crc: str
    sha1: str
    status: str
    optional: bool
    merge: str | None


@dataclass(frozen=True, slots=True)
class ExpectedDisk:
    name: str
    sha1: str
    merge: str | None
    status: str


@dataclass(frozen=True, slots=True)
class ExpectedMachine:
    name: str
    description: str
    cloneof: str | None
    roms: tuple[ExpectedRom, ...]
    disks: tuple[ExpectedDisk, ...]


class _AsyncManifestSink:
    """Writer assíncrono que tira o JSONL do caminho crítico do worker."""

    def __init__(self, writer: ScanManifestWriter) -> None:
        self.writer = writer
        self.queue: queue.Queue[tuple[str, Any] | None] = queue.Queue(maxsize=2048)
        self.thread = threading.Thread(target=self._run, name="scan-manifest-writer", daemon=True)
        self.error: BaseException | None = None
        self.thread.start()

    def put(self, kind: str, value: Any) -> None:
        """Enfileira um registro sem executar I/O no worker do scan."""
        self.queue.put((kind, value))

    def close(self) -> None:
        """Espera todos os registros serem gravados."""
        self.queue.put(None)
        self.thread.join()
        if self.error:
            raise RuntimeError("Falha no writer assíncrono do scan") from self.error

    def _run(self) -> None:
        try:
            while True:
                item = self.queue.get()
                try:
                    if item is None:
                        return
                    kind, value = item
                    if kind == "machine_started":
                        self.writer.machine_started(value)
                    elif kind == "rom":
                        self.writer.write_rom(value)
                    elif kind == "machine_finished":
                        self.writer.machine_finished(value)
                finally:
                    self.queue.task_done()
        except BaseException as exc:
            self.error = exc


class ExpectedDrivenScanService:
    """Executa o scan físico baseado somente nos requisitos do LISTXML."""

    def __init__(self, source_paths: list[str | Path], *, max_workers: int = 8,
                 include_chds: bool = True,
                 progress_callback: ProgressCallback | None = None,
                 machine_callback: MachineCallback | None = None,
                 manifest_writer: ScanManifestWriter | None = None) -> None:
        self.source_paths = [Path(p).expanduser() for p in source_paths]
        self.max_workers = max(1, int(max_workers))
        self.include_chds = include_chds
        self.progress_callback = progress_callback
        self.machine_callback = machine_callback
        self.manifest_writer = manifest_writer
        self._cancel = threading.Event()

    def cancel(self) -> None:
        """Solicita cancelamento cooperativo."""
        self._cancel.set()

    def scan(self, xml_path: str | Path) -> ScanResult:
        """Escaneia as machines do XML e persiste os resultados em paralelo."""
        xml_path = Path(xml_path).expanduser().resolve()
        machines = self._load_requirements(xml_path)
        result = ScanResult(xml_path=xml_path)
        sink: _AsyncManifestSink | None = None
        writer = self.manifest_writer
        if writer is not None:
            writer.start(
                version=self._mame_version(xml_path),
                xml_path=xml_path,
                source_paths=self.source_paths,
                machine_count=len(machines),
                metadata={"scanner": "expected-driven", "include_chds": self.include_chds},
            )
            sink = _AsyncManifestSink(writer)

        try:
            with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="scan-machine") as pool:
                futures = {pool.submit(self._scan_machine, machine): machine for machine in machines}
                completed = 0
                for future in as_completed(futures):
                    if self._cancel.is_set():
                        break
                    machine = future.result()
                    result.machines.append(machine)
                    completed += 1
                    if sink:
                        sink.put("machine_started", ScanMachineRecord(
                            name=machine.machine_name,
                            description=machine.description,
                            cloneof=machine.cloneof,
                            rom_count=machine.total,
                            status="scanning",
                            started_at=None,
                        ))
                        for item in machine.roms:
                            sink.put("rom", self._manifest_rom(item))
                        sink.put("machine_finished", ScanMachineRecord(
                            name=machine.machine_name,
                            description=machine.description,
                            cloneof=machine.cloneof,
                            rom_count=machine.total,
                            status=machine.status.value,
                            completed_at=None,
                        ))
                    if self.machine_callback:
                        self.machine_callback(machine)
                    if self.progress_callback:
                        self.progress_callback(completed, len(machines), machine)

            result.cancelled = self._cancel.is_set()
            result.finished_at = __import__("datetime").datetime.now()
            return result
        finally:
            if sink:
                sink.close()
            if writer:
                writer.finish(cancelled=self._cancel.is_set())

    @staticmethod
    def _mame_version(xml_path: Path) -> str:
        """Obtém a versão/build informada no elemento raiz quando disponível."""
        try:
            return ET.parse(xml_path).getroot().get("build", "unknown")
        except (OSError, ET.ParseError):
            return "unknown"

    @staticmethod
    def _load_requirements(xml_path: Path) -> list[ExpectedMachine]:
        """Transforma LISTXML em requisitos físicos mínimos."""
        root = ET.parse(xml_path).getroot()
        result: list[ExpectedMachine] = []
        for node in root.findall("machine"):
            name = node.get("name", "").strip()
            if not name:
                continue
            roms = tuple(
                ExpectedRom(
                    name=rom.get("name", "").strip(),
                    size=int(rom.get("size", "0") or 0),
                    crc=(rom.get("crc", "") or "").lower().strip(),
                    sha1=(rom.get("sha1", "") or "").lower().strip(),
                    status=(rom.get("status", "good") or "good").lower(),
                    optional=(rom.get("optional", "").lower() in {"yes", "true", "1"}),
                    merge=rom.get("merge"),
                )
                for rom in node.findall("rom")
                if rom.get("name")
            )
            disks = tuple(
                ExpectedDisk(
                    name=disk.get("name", "").strip(),
                    sha1=(disk.get("sha1", "") or "").lower().strip(),
                    merge=disk.get("merge"),
                    status=(disk.get("status", "good") or "good").lower(),
                )
                for disk in node.findall("disk")
                if disk.get("name")
            )
            result.append(ExpectedMachine(
                name=name,
                description=node.findtext("description", ""),
                cloneof=node.get("cloneof"),
                roms=roms,
                disks=disks,
            ))
        return result

    def _scan_machine(self, machine: ExpectedMachine) -> MachineScanResult:
        """Escaneia uma machine sem executar qualquer busca global."""
        result = MachineScanResult(
            machine_name=machine.name,
            description=machine.description,
            cloneof=machine.cloneof,
            started=True,
        )
        if self._cancel.is_set():
            return result

        zip_source = self._find_machine_zip(machine.name)
        loose_dir = self._find_machine_dir(machine.name)
        archive: zipfile.ZipFile | None = None
        infos: dict[str, zipfile.ZipInfo] = {}
        try:
            if zip_source:
                try:
                    archive = zipfile.ZipFile(zip_source, "r")
                    infos = {info.filename: info for info in archive.infolist() if not info.is_dir()}
                except (OSError, zipfile.BadZipFile) as exc:
                    logger.warning("ZIP inválido %s: %s", zip_source, exc)
                    archive = None
                    infos = {}

            for expected in machine.roms:
                if self._cancel.is_set():
                    break
                result.add_result(self._scan_rom(machine, expected, zip_source, archive, infos, loose_dir))

            if self.include_chds:
                for expected in machine.disks:
                    if self._cancel.is_set():
                        break
                    result.add_result(self._scan_disk(machine, expected, loose_dir))
        finally:
            if archive:
                archive.close()
        return result

    def _scan_rom(self, machine: ExpectedMachine, expected: ExpectedRom, zip_source: Path | None,
                  archive: zipfile.ZipFile | None, infos: dict[str, zipfile.ZipInfo], loose_dir: Path | None) -> RomScanResult:
        """Valida uma ROM usando somente o ZIP/pasta da própria machine."""
        if expected.status == "nodump":
            return RomScanResult(machine.name, expected.name, ScanStatus.MISSING,
                                 expected_size=expected.size, expected_crc=expected.crc,
                                 expected_sha1=expected.sha1, merge=expected.merge,
                                 optional=expected.optional,
                                 message="ROM marcada como NO DUMP; não existe conteúdo conhecido para reconstruir.")

        info = infos.get(expected.name) if infos else None
        member_name = expected.name
        if info is None and infos and expected.crc:
            # Mesmo ZIP: permite a regra do MAME de localizar por CRC quando o
            # nome não coincide. Não existe procura em outros ZIPs.
            for candidate in infos.values():
                if candidate.file_size == expected.size and f"{candidate.CRC & 0xffffffff:08x}" == expected.crc:
                    info = candidate
                    member_name = candidate.filename
                    break

        if info is not None and archive is not None:
            actual_crc = f"{info.CRC & 0xffffffff:08x}"
            if expected.size and info.file_size != expected.size:
                return self._invalid_rom(machine, expected, info.file_size, actual_crc, "tamanho divergente")
            if expected.crc and actual_crc != expected.crc:
                return self._invalid_rom(machine, expected, info.file_size, actual_crc, "CRC divergente")
            actual_sha1 = self._sha1_zip_member(archive, info) if expected.sha1 else ""
            if expected.sha1 and actual_sha1 != expected.sha1:
                return RomScanResult(machine.name, expected.name, ScanStatus.INVALID,
                                     expected_size=expected.size, actual_size=info.file_size,
                                     expected_crc=expected.crc, actual_crc=actual_crc,
                                     expected_sha1=expected.sha1, actual_sha1=actual_sha1,
                                     archive_path=zip_source, archive_member=member_name,
                                     merge=expected.merge, optional=expected.optional,
                                     message=f"SHA-1 divergente; esperado {expected.sha1}, encontrado {actual_sha1}.")
            message = "ROM válida."
            if expected.status == "baddump":
                message = "BAD DUMP conhecido pelo MAME; dump físico corresponde ao hash conhecido e será mantido."
            return RomScanResult(machine.name, expected.name, ScanStatus.VALID,
                                 expected_size=expected.size, actual_size=info.file_size,
                                 expected_crc=expected.crc, actual_crc=actual_crc,
                                 expected_sha1=expected.sha1, actual_sha1=actual_sha1,
                                 archive_path=zip_source, archive_member=member_name,
                                 merge=expected.merge, optional=expected.optional, message=message)

        if loose_dir:
            path = loose_dir / expected.name
            if path.is_file():
                actual_size = path.stat().st_size
                actual_crc, actual_sha1 = self._hash_file(path, need_sha1=bool(expected.sha1))
                if expected.size and actual_size != expected.size:
                    return self._invalid_rom(machine, expected, actual_size, actual_crc, "tamanho divergente", path=path, actual_sha1=actual_sha1)
                if expected.crc and actual_crc != expected.crc:
                    return self._invalid_rom(machine, expected, actual_size, actual_crc, "CRC divergente", path=path, actual_sha1=actual_sha1)
                if expected.sha1 and actual_sha1 != expected.sha1:
                    return RomScanResult(machine.name, expected.name, ScanStatus.INVALID,
                                         expected_size=expected.size, actual_size=actual_size,
                                         expected_crc=expected.crc, actual_crc=actual_crc,
                                         expected_sha1=expected.sha1, actual_sha1=actual_sha1,
                                         path=path, merge=expected.merge, optional=expected.optional,
                                         message=f"SHA-1 divergente; esperado {expected.sha1}, encontrado {actual_sha1}.")
                message = "ROM válida em arquivo solto."
                if expected.status == "baddump":
                    message = "BAD DUMP conhecido; dump físico corresponde ao hash conhecido."
                return RomScanResult(machine.name, expected.name, ScanStatus.VALID,
                                     expected_size=expected.size, actual_size=actual_size,
                                     expected_crc=expected.crc, actual_crc=actual_crc,
                                     expected_sha1=expected.sha1, actual_sha1=actual_sha1,
                                     path=path, merge=expected.merge, optional=expected.optional, message=message)

        message = "ROM ausente: nem o ZIP nem o diretório da própria machine possuem o arquivo esperado."
        if expected.optional:
            message += " ROM opcional; não bloqueia a execução mínima."
        return RomScanResult(machine.name, expected.name, ScanStatus.MISSING,
                             expected_size=expected.size, expected_crc=expected.crc,
                             expected_sha1=expected.sha1, merge=expected.merge,
                             optional=expected.optional, message=message)

    @staticmethod
    def _invalid_rom(machine: ExpectedMachine, expected: ExpectedRom, actual_size: int, actual_crc: str,
                     reason: str, *, path: Path | None = None, actual_sha1: str = "") -> RomScanResult:
        return RomScanResult(machine.name, expected.name, ScanStatus.INVALID,
                             expected_size=expected.size, actual_size=actual_size,
                             expected_crc=expected.crc, actual_crc=actual_crc,
                             expected_sha1=expected.sha1, actual_sha1=actual_sha1,
                             path=path, merge=expected.merge, optional=expected.optional,
                             message=f"ROM invalidada: {reason}; esperado size={expected.size}, CRC={expected.crc}.")

    def _scan_disk(self, machine: ExpectedMachine, expected: ExpectedDisk, loose_dir: Path | None) -> RomScanResult:
        """Verifica somente a localização canônica do CHD da machine."""
        filename = expected.name if expected.name.lower().endswith(".chd") else f"{expected.name}.chd"
        path = loose_dir / filename if loose_dir else None
        if path is None or not path.is_file():
            return RomScanResult(machine.name, filename, ScanStatus.MISSING,
                                 expected_sha1=expected.sha1, item_type=ScanItemType.DISK,
                                 merge=expected.merge,
                                 message="CHD ausente: busca limitada ao diretório da própria machine; nenhuma busca global foi executada.")
        actual_size = path.stat().st_size
        return RomScanResult(machine.name, filename, ScanStatus.VALID,
                             expected_size=actual_size, actual_size=actual_size,
                             expected_sha1=expected.sha1, item_type=ScanItemType.DISK,
                             path=path, merge=expected.merge,
                             message="CHD encontrado. SHA-1/chdman verify serão executados somente na reconstrução.")

    @staticmethod
    def _sha1_zip_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
        """Calcula SHA-1 somente do membro ZIP que corresponde ao requisito."""
        digest = hashlib.sha1()
        with archive.open(info, "r") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest().lower()

    @staticmethod
    def _hash_file(path: Path, *, need_sha1: bool) -> tuple[str, str]:
        """Calcula CRC e, quando necessário, SHA-1 de um arquivo solto."""
        import zlib
        crc = 0
        digest = hashlib.sha1() if need_sha1 else None
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                crc = zlib.crc32(chunk, crc)
                if digest:
                    digest.update(chunk)
        return f"{crc & 0xffffffff:08x}", digest.hexdigest().lower() if digest else ""

    def _find_machine_zip(self, machine: str) -> Path | None:
        """Testa somente ``machine.zip`` em cada origem configurada."""
        for base in self.source_paths:
            path = base / f"{machine}.zip"
            if path.is_file():
                return path
        return None

    def _find_machine_dir(self, machine: str) -> Path | None:
        """Testa somente ``<origem>/<machine>/`` em cada origem."""
        for base in self.source_paths:
            path = base / machine
            if path.is_dir():
                return path
        return None

    @staticmethod
    def _manifest_rom(item: RomScanResult) -> ScanRomRecord:
        """Converte o resultado físico para o formato de reconstrução."""
        kind = "chd" if item.item_type is ScanItemType.DISK else ("zip" if item.archive_path else "file")
        source = ScanSource(
            kind=kind,
            archive=str(item.archive_path or item.path) if (item.archive_path or item.path) else None,
            member=item.archive_member,
            machine=item.machine_name,
        )
        return ScanRomRecord(
            machine=item.machine_name,
            machine_description="",
            rom_name=item.rom_name,
            expected_size=item.expected_size,
            expected_crc=item.expected_crc,
            expected_sha1=item.expected_sha1 or None,
            merge=item.merge,
            status=item.status.value,
            actual_size=item.actual_size,
            actual_crc=item.actual_crc,
            actual_sha1=item.actual_sha1 or None,
            source=source if item.found else None,
            required=not item.optional,
            optional=item.optional,
            error=item.error,
        )
