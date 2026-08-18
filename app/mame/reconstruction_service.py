"""Reconstrução física de sets MAME a partir do manifesto do Scan Roms.

A reconstrução usa exclusivamente as origens registradas pelo scan. Ela
NÃO revarre as pastas de ROMs. As fontes são somente leitura e cada ROM é
transferida em streaming, em blocos de 1 MiB, para manter o uso de RAM baixo.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[int, int, str], None]
LogCallback = Callable[[str], None]
STREAM_CHUNK_SIZE = 1024 * 1024


@dataclass(slots=True)
class ReconstructionRom:
    """ROM requisitada e sua origem física registrada no scan."""
    machine: str
    rom_name: str
    expected_size: int
    expected_crc: str
    expected_sha1: str | None
    status: str
    source_archive: str | None = None
    source_member: str | None = None
    source_kind: str | None = None
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
    """Contadores e pendências da reconstrução."""
    copied: int = 0
    repaired: int = 0
    failed: int = 0
    external: int = 0
    skipped: int = 0
    unresolved: list[dict[str, Any]] = field(default_factory=list)


class ReconstructionService:
    """Engine sem Qt para copiar e reconstruir ROMs em streaming."""
    SET_SPLIT = "split"
    SET_MERGED = "merged"
    SET_NON_MERGED = "non_merged"

    def __init__(self, source_paths: list[str | Path], destination_path: str | Path,
                 *, progress_callback: ProgressCallback | None = None,
                 log_callback: LogCallback | None = None) -> None:
        # As fontes são usadas somente para validar caminhos já registrados.
        # Não existe rglob/listagem/indexação durante a reconstrução.
        self.source_paths = [Path(p).expanduser().resolve() for p in source_paths]
        self.destination_path = Path(destination_path).expanduser()
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self._cancel_requested = False

    def request_cancel(self) -> None:
        """Solicita cancelamento cooperativo."""
        self._cancel_requested = True

    def _log(self, message: str) -> None:
        logger.info(message)
        if self.log_callback:
            self.log_callback(message)

    def _progress(self, current: int, total: int, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(current, total, message)

    @staticmethod
    def load_manifest(path: str | Path) -> list[ReconstructionMachine]:
        """Carrega o JSONL produzido pelo Scan Roms."""
        machines: dict[str, ReconstructionMachine] = {}
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"Manifesto não encontrado: {path}")
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("record_type") == "machine":
                    data = rec.get("machine") or {}
                    name = str(data.get("name") or "")
                    if name:
                        machine = machines.setdefault(name, ReconstructionMachine(name=name))
                        machine.description = str(data.get("description") or machine.description)
                        if data.get("cloneof") is not None:
                            machine.cloneof = data.get("cloneof")
                elif rec.get("record_type") == "rom":
                    data = rec.get("rom") or rec
                    name = str(data.get("machine") or "")
                    rom_name = str(data.get("rom_name") or "")
                    if not name or not rom_name:
                        continue
                    source = data.get("source") or {}
                    machines.setdefault(name, ReconstructionMachine(name=name)).roms.append(
                        ReconstructionRom(
                            machine=name,
                            rom_name=rom_name,
                            expected_size=int(data.get("expected_size") or 0),
                            expected_crc=str(data.get("expected_crc") or "").lower(),
                            expected_sha1=(str(data.get("expected_sha1") or "").lower() or None),
                            status=str(data.get("status") or "missing").lower(),
                            source_archive=source.get("archive"),
                            source_member=source.get("member"),
                            source_kind=source.get("kind"),
                            merge=data.get("merge"),
                            optional=bool(data.get("optional", False)),
                            required=bool(data.get("required", not data.get("optional", False))),
                        )
                    )
        return list(machines.values())

    def _configured_source(self, archive: Path) -> bool:
        """Valida um caminho registrado sem enumerar o diretório."""
        try:
            resolved = archive.resolve()
        except OSError:
            return False
        return any(base == resolved or base in resolved.parents for base in self.source_paths)

    @staticmethod
    def _required(machine: ReconstructionMachine) -> list[ReconstructionRom]:
        return [r for r in machine.roms if r.required and not r.optional]

    def _is_perfect(self, machine: ReconstructionMachine) -> bool:
        required = self._required(machine)
        return bool(required) and all(r.status in {"valid", "ok", "good"} for r in required)

    def _original_archive(self, machine: ReconstructionMachine) -> Path | None:
        """Obtém o ZIP perfeito exclusivamente das origens do manifesto."""
        candidates: list[Path] = []
        for rom in machine.roms:
            if not rom.source_archive:
                continue
            archive = Path(rom.source_archive).expanduser()
            if archive.is_file() and self._configured_source(archive):
                candidates.append(archive)
        for archive in candidates:
            if archive.stem.lower() == machine.name.lower():
                return archive
        return candidates[0] if candidates else None

    def _copy_perfect(self, machine: ReconstructionMachine) -> bool:
        """Copia o ZIP perfeito sem abrir ou modificar a origem."""
        source = self._original_archive(machine)
        if not source:
            return False
        target = self.destination_path / f"{machine.name}.zip"
        target.parent.mkdir(parents=True, exist_ok=True)
        self._log(f"Copiando perfeita: {machine.name}.zip")
        shutil.copyfile(source, target)
        return True

    def _source_for_rom(self, rom: ReconstructionRom) -> tuple[Path, str] | None:
        """Retorna somente a origem física registrada no scan."""
        if not rom.source_archive or not rom.source_member:
            return None
        archive = Path(rom.source_archive).expanduser()
        if not archive.is_file() or not self._configured_source(archive):
            return None
        return archive, str(rom.source_member)

    @staticmethod
    def _validate_info(info: zipfile.ZipInfo, rom: ReconstructionRom) -> None:
        """Valida tamanho e CRC pelo diretório central, sem ler a ROM inteira."""
        if info.file_size != rom.expected_size:
            raise ValueError(f"tamanho incompatível: esperado {rom.expected_size}, encontrado {info.file_size}")
        if f"{info.CRC:08x}" != rom.expected_crc.lower():
            raise ValueError(f"CRC incompatível: esperado {rom.expected_crc}, encontrado {info.CRC:08x}")

    def _stream_member(self, source_zip: zipfile.ZipFile, member: str,
                       output_zip: zipfile.ZipFile, output_name: str,
                       rom: ReconstructionRom) -> None:
        """Transfere um membro ZIP em blocos, sem materializá-lo em RAM."""
        info = source_zip.getinfo(member)
        self._validate_info(info, rom)
        with source_zip.open(info, "r") as src, output_zip.open(output_name, "w") as dst:
            while True:
                if self._cancel_requested:
                    raise InterruptedError("Reconstrução cancelada pelo usuário.")
                chunk = src.read(STREAM_CHUNK_SIZE)
                if not chunk:
                    break
                dst.write(chunk)

    def _write_zip_streaming(self, machine_name: str,
                             selected: list[tuple[ReconstructionRom, Path, str]]) -> None:
        """Monta um ZIP de destino mantendo somente pequenos blocos em RAM."""
        target = self.destination_path / f"{machine_name}.zip"
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{machine_name}.", suffix=".zip.tmp", dir=str(target.parent))
        os.close(fd)
        temp_path = Path(temp_name)
        opened: dict[Path, zipfile.ZipFile] = {}
        try:
            with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as output:
                written: set[str] = set()
                for rom, archive, member in selected:
                    if rom.rom_name in written:
                        continue
                    if archive not in opened:
                        opened[archive] = zipfile.ZipFile(archive, "r")
                    self._log(f"Reparando {machine_name}: {rom.rom_name}")
                    self._stream_member(opened[archive], member, output, rom.rom_name, rom)
                    written.add(rom.rom_name)
            os.replace(temp_path, target)
        finally:
            for zf in opened.values():
                zf.close()
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def _roms_for_nonmerged(machine: ReconstructionMachine,
                            by_name: dict[str, ReconstructionMachine]) -> list[ReconstructionRom]:
        """Non-Merged inclui ROMs próprias e ROMs do parent."""
        own = list(machine.roms)
        if not machine.cloneof:
            return own
        parent = by_name.get(machine.cloneof)
        return own + (ReconstructionService._required(parent) if parent else [])

    @staticmethod
    def _merged_root(machine: ReconstructionMachine,
                     by_name: dict[str, ReconstructionMachine]) -> ReconstructionMachine:
        """Obtém a raiz da família de clones."""
        current = machine
        visited: set[str] = set()
        while current.cloneof and current.cloneof in by_name and current.name not in visited:
            visited.add(current.name)
            current = by_name[current.cloneof]
        return current

    def reconstruct(self, machines: list[ReconstructionMachine], *, set_type: str = SET_SPLIT,
                    copy_perfect: bool = True, repair: bool = True) -> ReconstructionResult:
        """Reconstrói ROM por ROM usando somente o diagnóstico já existente."""
        if set_type not in {self.SET_SPLIT, self.SET_MERGED, self.SET_NON_MERGED}:
            raise ValueError(f"Tipo de set inválido: {set_type}")
        self.destination_path.mkdir(parents=True, exist_ok=True)
        self._cancel_requested = False
        result = ReconstructionResult()
        by_name = {m.name: m for m in machines}
        total = sum(len(self._required(m)) for m in machines)
        current = 0

        def process(machine: ReconstructionMachine, roms: list[ReconstructionRom], target_name: str) -> None:
            nonlocal current
            selected: list[tuple[ReconstructionRom, Path, str]] = []
            failed = False
            for rom in roms:
                if self._cancel_requested:
                    raise InterruptedError("Reconstrução cancelada pelo usuário.")
                source = self._source_for_rom(rom)
                if source is None:
                    failed = True
                    result.external += 1
                    result.unresolved.append(self._unresolved(machine, rom, "fonte_externa_necessaria"))
                    self._log(f"Fonte externa necessária: {machine.name} -> {rom.rom_name}")
                else:
                    try:
                        with zipfile.ZipFile(source[0], "r") as zf:
                            self._validate_info(zf.getinfo(source[1]), rom)
                        selected.append((rom, source[0], source[1]))
                    except (OSError, zipfile.BadZipFile, KeyError, ValueError) as exc:
                        failed = True
                        result.external += 1
                        result.unresolved.append(self._unresolved(machine, rom, "origem_invalida", str(exc)))
                        self._log(f"Origem inválida: {machine.name} -> {rom.rom_name}: {exc}")
                if rom.machine == machine.name:
                    current += 1
                    self._progress(current, total, f"{machine.name}: {rom.rom_name}")
            if failed:
                result.failed += 1
                return
            try:
                self._write_zip_streaming(target_name, selected)
                result.repaired += 1
                self._log(f"Concluído: {target_name}.zip")
            except InterruptedError:
                raise
            except Exception as exc:
                result.failed += 1
                result.unresolved.append(self._unresolved(machine, None, "erro_gravacao", str(exc)))
                self._log(f"Erro em {target_name}: {exc}")

        try:
            if set_type == self.SET_MERGED:
                groups: dict[str, list[ReconstructionMachine]] = {}
                for machine in machines:
                    groups.setdefault(self._merged_root(machine, by_name).name, []).append(machine)
                for root_name, group in groups.items():
                    all_roms: list[ReconstructionRom] = []
                    for machine in group:
                        all_roms.extend(self._required(machine))
                    process(group[0], all_roms, root_name)
            else:
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
                    roms = required if set_type == self.SET_SPLIT else self._roms_for_nonmerged(machine, by_name)
                    process(machine, roms, machine.name)
        except InterruptedError:
            self._log("Reconstrução cancelada com segurança; fontes permanecem intactas.")
            raise

        self._progress(total, total, "Reconstrução concluída.")
        return result

    @staticmethod
    def _unresolved(machine: ReconstructionMachine, rom: ReconstructionRom | None,
                    reason: str, error: str | None = None) -> dict[str, Any]:
        return {
            "machine": machine.name,
            "description": machine.description,
            "cloneof": machine.cloneof,
            "rom_name": rom.rom_name if rom else None,
            "expected_size": rom.expected_size if rom else None,
            "expected_crc": rom.expected_crc if rom else None,
            "expected_sha1": rom.expected_sha1 if rom else None,
            "reason": reason,
            "error": error,
        }

    @staticmethod
    def write_residual_manifest(path: str | Path, unresolved: list[dict[str, Any]], *,
                                source_manifest: str | Path, set_type: str) -> Path:
        """Gera manifesto residual somente com o que ainda falta."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({"record_type": "header", "schema_version": 2,
                                 "manifest_type": "reconstruction_residual",
                                 "source_manifest": str(source_manifest), "set_type": set_type}, ensure_ascii=False) + "\n")
            seen: set[tuple[str, str]] = set()
            machines_written: set[str] = set()
            for item in unresolved:
                machine = str(item.get("machine") or "")
                rom_name = str(item.get("rom_name") or "")
                key = (machine, rom_name)
                if key in seen:
                    continue
                seen.add(key)
                if machine not in machines_written:
                    fh.write(json.dumps({"record_type": "machine", "event": "residual",
                                         "machine": {"name": machine, "description": item.get("description", ""),
                                                     "cloneof": item.get("cloneof")}}, ensure_ascii=False) + "\n")
                    machines_written.add(machine)
                if rom_name:
                    fh.write(json.dumps({"record_type": "rom", "machine": machine,
                                         "machine_description": item.get("description", ""),
                                         "rom_name": rom_name, "expected_size": item.get("expected_size", 0),
                                         "expected_crc": item.get("expected_crc", ""),
                                         "expected_sha1": item.get("expected_sha1"), "status": "missing",
                                         "required": True, "optional": False,
                                         "error": item.get("reason")}, ensure_ascii=False) + "\n")
            fh.write(json.dumps({"record_type": "scan_summary", "manifest_type": "reconstruction_residual",
                                 "unresolved_count": len(seen)}, ensure_ascii=False) + "\n")
        return path
