"""Reconstrução física de sets MAME a partir de um manifesto de scan."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[int, int, str], None]
LogCallback = Callable[[str], None]


@dataclass(slots=True)
class ReconstructionRom:
    """ROM requisitada por uma machine."""
    machine: str
    rom_name: str
    expected_size: int
    expected_crc: str
    expected_sha1: str | None
    status: str
    source_archive: str | None = None
    source_member: str | None = None
    merge: str | None = None
    optional: bool = False
    required: bool = True


@dataclass(slots=True)
class ReconstructionMachine:
    """Machine e suas ROMs."""
    name: str
    description: str = ""
    cloneof: str | None = None
    roms: list[ReconstructionRom] = field(default_factory=list)


@dataclass(slots=True)
class ReconstructionResult:
    """Contadores e pendências da execução."""
    copied: int = 0
    repaired: int = 0
    failed: int = 0
    external: int = 0
    skipped: int = 0
    unresolved: list[dict[str, Any]] = field(default_factory=list)


class ReconstructionService:
    """Executa cópia e reconstrução sem dependência de Qt.

    A validação usa CRC + tamanho e, quando disponível, SHA-1. A origem
    registrada pelo scanner é tentada primeiro; depois o índice físico busca
    a ROM em outros ZIPs configurados na aba Scan Roms.
    """

    SET_SPLIT = "split"
    SET_MERGED = "merged"
    SET_NON_MERGED = "non_merged"

    def __init__(self, source_paths: Iterable[str | Path], destination_path: str | Path,
                 *, progress_callback: ProgressCallback | None = None,
                 log_callback: LogCallback | None = None) -> None:
        self.source_paths = [Path(p).expanduser() for p in source_paths]
        self.destination_path = Path(destination_path).expanduser()
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self._index: dict[tuple[str, str, int], list[tuple[Path, str]]] = {}

    def _log(self, message: str) -> None:
        logger.info(message)
        if self.log_callback:
            self.log_callback(message)

    def _progress(self, current: int, total: int, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(current, total, message)

    @staticmethod
    def load_manifest(path: str | Path) -> list[ReconstructionMachine]:
        """Carrega machine/ROM records do JSONL atual."""
        machines: dict[str, ReconstructionMachine] = {}
        path = Path(path)
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("record_type") == "machine":
                    data = rec.get("machine") or {}
                    name = str(data.get("name") or "")
                    if name:
                        machines.setdefault(name, ReconstructionMachine(
                            name=name, description=str(data.get("description") or ""),
                            cloneof=data.get("cloneof")))
                elif rec.get("record_type") == "rom":
                    data = rec.get("rom") or rec
                    name = str(data.get("machine") or "")
                    rom_name = str(data.get("rom_name") or "")
                    if not name or not rom_name:
                        continue
                    machines.setdefault(name, ReconstructionMachine(name=name))
                    source = data.get("source") or {}
                    machines[name].roms.append(ReconstructionRom(
                        machine=name, rom_name=rom_name,
                        expected_size=int(data.get("expected_size") or 0),
                        expected_crc=str(data.get("expected_crc") or "").lower(),
                        expected_sha1=(str(data.get("expected_sha1") or "").lower() or None),
                        status=str(data.get("status") or "missing").lower(),
                        source_archive=source.get("archive"), source_member=source.get("member"),
                        merge=data.get("merge"), optional=bool(data.get("optional", False)),
                        required=bool(data.get("required", not data.get("optional", False)))))
        return list(machines.values())

    def build_source_index(self) -> None:
        """Indexa membros de ZIP por nome, CRC e tamanho."""
        self._index.clear()
        for base in self.source_paths:
            if not base.is_dir():
                continue
            for archive in base.rglob("*.zip"):
                try:
                    with zipfile.ZipFile(archive) as zf:
                        for info in zf.infolist():
                            if info.is_dir():
                                continue
                            key = (Path(info.filename).name.lower(), f"{info.CRC:08x}", int(info.file_size))
                            self._index.setdefault(key, []).append((archive, info.filename))
                except (OSError, zipfile.BadZipFile):
                    logger.debug("ZIP inválido ignorado: %s", archive)
        self._log(f"Índice de fontes: {sum(map(len, self._index.values()))} membros.")

    @staticmethod
    def _valid_data(data: bytes, rom: ReconstructionRom) -> bool:
        if len(data) != rom.expected_size:
            return False
        import binascii
        if f"{binascii.crc32(data) & 0xffffffff:08x}" != rom.expected_crc.lower():
            return False
        return not rom.expected_sha1 or hashlib.sha1(data).hexdigest().lower() == rom.expected_sha1.lower()

    def _find_source(self, rom: ReconstructionRom) -> tuple[Path, str] | None:
        key = (rom.rom_name.lower(), rom.expected_crc.lower(), rom.expected_size)
        candidates = self._index.get(key, [])
        if not candidates:
            candidates = [item for (name, crc, size), values in self._index.items()
                          if crc == rom.expected_crc.lower() and size == rom.expected_size for item in values]
        for archive, member in candidates:
            try:
                with zipfile.ZipFile(archive) as zf:
                    if self._valid_data(zf.read(member), rom):
                        return archive, member
            except (OSError, zipfile.BadZipFile, KeyError):
                continue
        return None

    def _source_for_rom(self, rom: ReconstructionRom) -> tuple[Path, str] | None:
        if rom.source_archive and rom.source_member:
            archive = Path(rom.source_archive)
            if archive.is_file():
                try:
                    with zipfile.ZipFile(archive) as zf:
                        data = zf.read(rom.source_member)
                        if self._valid_data(data, rom):
                            return archive, rom.source_member
                except (OSError, zipfile.BadZipFile, KeyError):
                    pass
        return self._find_source(rom)

    @staticmethod
    def _required(machine: ReconstructionMachine) -> list[ReconstructionRom]:
        return [r for r in machine.roms if r.required and not r.optional]

    def _is_perfect(self, machine: ReconstructionMachine) -> bool:
        required = self._required(machine)
        return bool(required) and all(r.status in {"valid", "ok", "good"} for r in required)

    def _original_archive(self, machine: ReconstructionMachine) -> Path | None:
        candidates = [Path(r.source_archive) for r in machine.roms if r.source_archive]
        return next((p for p in candidates if p.is_file() and p.stem.lower() == machine.name.lower()),
                    next((p for p in candidates if p.is_file()), None))

    def _copy_perfect(self, machine: ReconstructionMachine) -> bool:
        source = self._original_archive(machine)
        if not source:
            return False
        target = self.destination_path / f"{machine.name}.zip"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return True

    def _write_zip(self, machine: ReconstructionMachine, selected: list[tuple[ReconstructionRom, Path, str]]) -> None:
        target = self.destination_path / f"{machine.name}.zip"
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=f".{machine.name}.", suffix=".tmp", dir=str(target.parent))
        os.close(fd)
        tmp_path = Path(tmp)
        try:
            with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as out:
                written: set[str] = set()
                for rom, archive, member in selected:
                    if rom.rom_name in written:
                        continue
                    with zipfile.ZipFile(archive) as src:
                        data = src.read(member)
                    info = zipfile.ZipInfo(rom.rom_name)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    out.writestr(info, data)
                    written.add(rom.rom_name)
            os.replace(tmp_path, target)
        finally:
            tmp_path.unlink(missing_ok=True)

    def _roms_for_set(self, machine: ReconstructionMachine, by_name: dict[str, ReconstructionMachine], set_type: str) -> list[ReconstructionRom]:
        own = list(machine.roms)
        if set_type == self.SET_SPLIT or not machine.cloneof:
            return own
        parent = by_name.get(machine.cloneof)
        if not parent:
            return own
        parent_required = self._required(parent)
        if set_type == self.SET_MERGED:
            return own + parent_required
        return own + parent_required

    def reconstruct(self, machines: list[ReconstructionMachine], *, set_type: str = SET_SPLIT,
                    copy_perfect: bool = True, repair: bool = True) -> ReconstructionResult:
        """Executa a operação e mantém somente pendências no resultado."""
        if set_type not in {self.SET_SPLIT, self.SET_MERGED, self.SET_NON_MERGED}:
            raise ValueError(f"Tipo de set inválido: {set_type}")
        self.destination_path.mkdir(parents=True, exist_ok=True)
        self.build_source_index()
        by_name = {m.name: m for m in machines}
        result = ReconstructionResult()
        total = sum(len(self._required(m)) for m in machines)
        current = 0

        for machine in machines:
            required = self._required(machine)
            if copy_perfect and self._is_perfect(machine) and self._copy_perfect(machine):
                result.copied += 1
                current += len(required)
                self._progress(current, total, f"Copiado: {machine.name}")
                continue
            if not repair:
                result.skipped += 1
                for rom in required:
                    result.unresolved.append(self._unresolved(machine, rom, "reparo_desativado"))
                current += len(required)
                continue

            selected: list[tuple[ReconstructionRom, Path, str]] = []
            failed = False
            for rom in self._roms_for_set(machine, by_name, set_type):
                if rom.optional:
                    continue
                source = self._source_for_rom(rom)
                if not source:
                    failed = True
                    result.external += 1
                    result.unresolved.append(self._unresolved(machine, rom, "fonte_externa_necessaria"))
                else:
                    selected.append((rom, source[0], source[1]))
                if rom.machine == machine.name:
                    current += 1
                    self._progress(current, total, f"{machine.name}: {rom.rom_name}")
            if failed:
                result.failed += 1
                continue
            try:
                self._write_zip(machine, selected)
                result.repaired += 1
                self._log(f"Reparado: {machine.name}")
            except Exception as exc:
                result.failed += 1
                result.unresolved.append(self._unresolved(machine, None, "erro_gravacao", str(exc)))
        self._progress(total, total, "Reconstrução concluída.")
        return result

    @staticmethod
    def _unresolved(machine: ReconstructionMachine, rom: ReconstructionRom | None, reason: str, error: str | None = None) -> dict[str, Any]:
        return {"machine": machine.name, "description": machine.description, "cloneof": machine.cloneof,
                "rom_name": rom.rom_name if rom else None, "expected_size": rom.expected_size if rom else None,
                "expected_crc": rom.expected_crc if rom else None, "expected_sha1": rom.expected_sha1 if rom else None,
                "reason": reason, "error": error}

    @staticmethod
    def write_residual_manifest(path: str | Path, unresolved: list[dict[str, Any]], *, source_manifest: str | Path, set_type: str) -> Path:
        """Gera manifesto residual compatível com a próxima etapa do pipeline."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({"record_type": "header", "schema_version": 2,
                                 "manifest_type": "reconstruction_residual", "source_manifest": str(source_manifest),
                                 "set_type": set_type}, ensure_ascii=False) + "\n")
            seen: set[tuple[str, str]] = set()
            for item in unresolved:
                key = (str(item.get("machine")), str(item.get("rom_name")))
                if key in seen:
                    continue
                seen.add(key)
                fh.write(json.dumps({"record_type": "machine", "event": "residual",
                                     "machine": {"name": item.get("machine"), "description": item.get("description", ""),
                                                 "cloneof": item.get("cloneof")}}, ensure_ascii=False) + "\n")
                if item.get("rom_name"):
                    fh.write(json.dumps({"record_type": "rom", "machine": item.get("machine"),
                                         "machine_description": item.get("description", ""),
                                         "rom_name": item.get("rom_name"), "expected_size": item.get("expected_size", 0),
                                         "expected_crc": item.get("expected_crc", ""), "expected_sha1": item.get("expected_sha1"),
                                         "status": "missing", "required": True, "optional": False,
                                         "error": item.get("reason")}, ensure_ascii=False) + "\n")
            fh.write(json.dumps({"record_type": "scan_summary", "manifest_type": "reconstruction_residual",
                                 "unresolved_count": len(seen)}, ensure_ascii=False) + "\n")
        return path
