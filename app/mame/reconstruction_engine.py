"""Motor transacional de reconstrução baseado em ROMs individuais.

Este módulo é a implementação nova da reconstrução. O ZIP não é a unidade
semântica de validade: cada ROM esperada é validada por tamanho/CRC/SHA1,
quando disponível. O ZIP de destino é sempre reconstruído limpo, sem extras.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import zlib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

logger = logging.getLogger(__name__)
STREAM_CHUNK_SIZE = 1024 * 1024
DEFAULT_MAX_RETRIES = 2
ProgressCallback = Callable[[int, int, str], None]
LogCallback = Callable[[str], None]


@dataclass(slots=True)
class ReconstructionRom:
    """ROM esperada e origem física registrada pelo Scan."""
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
    """Machine e suas ROMs esperadas."""
    name: str
    description: str = ""
    cloneof: str | None = None
    roms: list[ReconstructionRom] = field(default_factory=list)


@dataclass(slots=True)
class ReconstructionResult:
    """Resultado agregado."""
    copied: int = 0
    repaired: int = 0
    failed: int = 0
    external: int = 0
    skipped: int = 0
    roms_verified: int = 0
    retries: int = 0
    unresolved: list[dict[str, Any]] = field(default_factory=list)


class ReconstructionEngine:
    """Reconstrói sequencialmente sem modificar as fontes."""

    SET_SPLIT = "split"
    SET_MERGED = "merged"
    SET_NON_MERGED = "non_merged"

    def __init__(self, source_paths: Iterable[str | Path], destination_path: str | Path, *, progress_callback: ProgressCallback | None = None, log_callback: LogCallback | None = None, max_retries: int = DEFAULT_MAX_RETRIES) -> None:
        self.source_paths = [Path(p).expanduser().resolve() for p in source_paths]
        self.destination_path = Path(destination_path).expanduser().resolve()
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.max_retries = max(0, int(max_retries))
        self._cancel_requested = False
        self._staging_root = self.destination_path / ".reconstruction_tmp"

    def request_cancel(self) -> None:
        """Solicita cancelamento cooperativo."""
        self._cancel_requested = True

    def _check_cancel(self) -> None:
        if self._cancel_requested:
            raise InterruptedError("Reconstrução cancelada pelo usuário.")

    def _log(self, message: str) -> None:
        logger.info(message)
        if self.log_callback:
            self.log_callback(message)

    def _progress(self, current: int, total: int, message: str) -> None:
        if self.progress_callback:
            self.progress_callback(current, total, message)

    @staticmethod
    def load_manifest(path: str | Path) -> list[ReconstructionMachine]:
        """Carrega current_scan.jsonl sem acessar as fontes físicas."""
        machines: dict[str, ReconstructionMachine] = {}
        manifest = Path(path)
        if not manifest.is_file():
            raise FileNotFoundError(f"Manifesto não encontrado: {manifest}")
        with manifest.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning("JSONL inválido na linha %d: %s", line_number, exc)
                    continue
                kind = record.get("record_type")
                if kind == "machine":
                    data = record.get("machine") or {}
                    name = str(data.get("name") or "")
                    if not name:
                        continue
                    machine = machines.setdefault(name, ReconstructionMachine(name=name))
                    machine.description = str(data.get("description") or machine.description)
                    machine.cloneof = data.get("cloneof") or machine.cloneof
                elif kind == "rom":
                    data = record.get("rom") or record
                    machine_name = str(data.get("machine") or "")
                    rom_name = str(data.get("rom_name") or "")
                    if not machine_name or not rom_name:
                        continue
                    source = data.get("source") or {}
                    machines.setdefault(machine_name, ReconstructionMachine(name=machine_name)).roms.append(
                        ReconstructionRom(
                            machine=machine_name,
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

    @staticmethod
    def _required(machine: ReconstructionMachine) -> list[ReconstructionRom]:
        """Retorna somente ROMs obrigatórias."""
        return [rom for rom in machine.roms if rom.required and not rom.optional]

    def _source_allowed(self, path: Path) -> bool:
        """Impede acesso a arquivos fora das fontes configuradas."""
        try:
            resolved = path.resolve()
        except OSError:
            return False
        return any(base == resolved or base in resolved.parents for base in self.source_paths)

    def _source_for_rom(self, rom: ReconstructionRom) -> tuple[str, Path, str | None] | None:
        """Obtém exclusivamente a origem registrada no Scan."""
        if not rom.source_archive:
            return None
        source = Path(rom.source_archive).expanduser()
        if not source.is_file() or not self._source_allowed(source):
            return None
        kind = (rom.source_kind or "zip").lower()
        if kind in {"file", "loose", "raw"}:
            return kind, source, None
        if kind in {"zip", "archive"} and rom.source_member:
            return kind, source, rom.source_member
        return None

    @staticmethod
    def _validate_zip_info(info: zipfile.ZipInfo, rom: ReconstructionRom) -> None:
        """Valida metadados do membro antes da leitura."""
        if rom.expected_size > 0 and info.file_size != rom.expected_size:
            raise ValueError(f"tamanho incompatível: esperado={rom.expected_size}, encontrado={info.file_size}")
        if rom.expected_crc and f"{info.CRC & 0xFFFFFFFF:08x}" != rom.expected_crc:
            raise ValueError(f"CRC incompatível: esperado={rom.expected_crc}, encontrado={info.CRC & 0xFFFFFFFF:08x}")

    def _stream_source(self, rom: ReconstructionRom, source: tuple[str, Path, str | None], staged: Path) -> None:
        """Transfere a ROM em streaming e valida o conteúdo real transferido."""
        kind, source_path, member = source
        archive = None
        source_handle = None
        crc = 0
        total = 0
        sha1 = hashlib.sha1()
        try:
            if kind in {"file", "loose", "raw"}:
                source_handle = source_path.open("rb")
            else:
                archive = zipfile.ZipFile(source_path, "r")
                if not member:
                    raise ValueError("membro ZIP não informado pelo manifesto")
                try:
                    info = archive.getinfo(member)
                except KeyError as exc:
                    raise FileNotFoundError(f"membro não encontrado no ZIP: {member}") from exc
                self._validate_zip_info(info, rom)
                source_handle = archive.open(info, "r")
            with staged.open("wb") as output:
                while True:
                    self._check_cancel()
                    chunk = source_handle.read(STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    output.write(chunk)
                    crc = zlib.crc32(chunk, crc)
                    sha1.update(chunk)
                    total += len(chunk)
        finally:
            if source_handle is not None:
                source_handle.close()
            if archive is not None:
                archive.close()
        actual_crc = f"{crc & 0xFFFFFFFF:08x}"
        actual_sha1 = sha1.hexdigest().lower()
        if rom.expected_size > 0 and total != rom.expected_size:
            raise ValueError(f"transferência incompleta: {total}/{rom.expected_size} bytes")
        if rom.expected_crc and actual_crc != rom.expected_crc:
            raise ValueError(f"CRC após streaming incompatível: {actual_crc}")
        if rom.expected_sha1 and actual_sha1 != rom.expected_sha1:
            raise ValueError("SHA-1 após streaming incompatível")

    def _stage_rom(self, rom: ReconstructionRom, machine_dir: Path, result: ReconstructionResult) -> Path:
        """Transfere uma ROM individual, com retry e validação."""
        source = self._source_for_rom(rom)
        if source is None:
            raise FileNotFoundError("fonte física não registrada, inexistente ou fora das fontes configuradas")
        safe_name = Path(rom.rom_name).name or "unnamed"
        staged = machine_dir / f"{len(list(machine_dir.iterdir())):06d}_{safe_name}.romtmp"
        for attempt in range(self.max_retries + 1):
            self._check_cancel()
            staged.unlink(missing_ok=True)
            try:
                suffix = f"!{source[2]}" if source[2] else ""
                self._log(f"[ROM] {rom.machine} -> {rom.rom_name} | origem={source[1]}{suffix} | tentativa={attempt + 1}")
                self._stream_source(rom, source, staged)
                if rom.expected_size > 0 and staged.stat().st_size != rom.expected_size:
                    raise ValueError("tamanho do staging incompatível")
                result.roms_verified += 1
                if attempt:
                    result.retries += attempt
                self._log(f"[ROM] VALIDADA: {rom.machine} -> {rom.rom_name}")
                return staged
            except Exception as exc:
                staged.unlink(missing_ok=True)
                if attempt >= self.max_retries:
                    raise
                self._log(f"[ROM] falha: {rom.rom_name} | {exc} | repetindo")
        raise RuntimeError("fluxo de retry inválido")

    def _write_machine_zip(self, machine_name: str, expected_roms: list[ReconstructionRom], staged_roms: list[tuple[ReconstructionRom, Path]]) -> Path:
        """Cria um ZIP limpo contendo exatamente as ROMs esperadas."""
        if not expected_roms:
            raise ValueError(f"machine sem ROMs obrigatórias: {machine_name}")
        if not staged_roms:
            raise ValueError(f"nenhuma ROM reconstruída para {machine_name}; ZIP não será criado")
        expected = {rom.rom_name: rom for rom in expected_roms}
        if len(expected) != len(expected_roms):
            raise ValueError(f"ROMs duplicadas no manifesto da machine {machine_name}")
        staged: dict[str, tuple[ReconstructionRom, Path]] = {}
        for rom, path in staged_roms:
            if rom.rom_name not in expected:
                raise ValueError(f"ROM não esperada: {rom.rom_name}")
            if rom.rom_name in staged:
                raise ValueError(f"ROM duplicada na reconstrução: {rom.rom_name}")
            staged[rom.rom_name] = (rom, path)
        missing = [name for name in expected if name not in staged]
        if missing:
            raise ValueError(f"ROMs faltantes em {machine_name}: {', '.join(missing[:10])}")

        self._staging_root.mkdir(parents=True, exist_ok=True)
        temp_zip = self._staging_root / f".{machine_name}.zip.tmp"
        target = self.destination_path / f"{machine_name}.zip"
        temp_zip.unlink(missing_ok=True)
        try:
            with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as output:
                for rom in expected_roms:
                    self._check_cancel()
                    _, staged_path = staged[rom.rom_name]
                    self._log(f"[ZIP] adicionando {machine_name}.zip <- {rom.rom_name}")
                    with staged_path.open("rb") as source, output.open(rom.rom_name, "w") as destination:
                        while True:
                            self._check_cancel()
                            chunk = source.read(STREAM_CHUNK_SIZE)
                            if not chunk:
                                break
                            destination.write(chunk)

            with zipfile.ZipFile(temp_zip, "r") as check:
                infos = [info for info in check.infolist() if not info.is_dir()]
                if len(infos) != len(expected):
                    raise ValueError(f"quantidade de entradas divergente em {machine_name}")
                if check.testzip() is not None:
                    raise ValueError("falha física no ZIP temporário")
                names = {info.filename for info in infos}
                if names != set(expected):
                    raise ValueError("ZIP contém extras ou nomes esperados ausentes")
                for name, rom in expected.items():
                    info = check.getinfo(name)
                    if rom.expected_size > 0 and info.file_size != rom.expected_size:
                        raise ValueError(f"tamanho incorreto na ROM publicada: {name}")
                    crc = f"{info.CRC & 0xFFFFFFFF:08x}"
                    if rom.expected_crc and crc != rom.expected_crc:
                        raise ValueError(f"CRC incorreto na ROM publicada: {name}")
            os.replace(temp_zip, target)
            self._log(f"[ZIP] PUBLICADO: {target}")
            return target
        finally:
            temp_zip.unlink(missing_ok=True)

    @staticmethod
    def _root_machine(machine: ReconstructionMachine, by_name: dict[str, ReconstructionMachine]) -> ReconstructionMachine:
        """Obtém a raiz da cadeia de clones."""
        current = machine
        visited: set[str] = set()
        while current.cloneof and current.cloneof in by_name and current.name not in visited:
            visited.add(current.name)
            current = by_name[current.cloneof]
        return current

    @staticmethod
    def _nonmerged_roms(machine: ReconstructionMachine, by_name: dict[str, ReconstructionMachine]) -> list[ReconstructionRom]:
        """Obtém ROMs próprias e do parent, sem duplicidade por nome."""
        roms = list(ReconstructionEngine._required(machine))
        if machine.cloneof and machine.cloneof in by_name:
            roms.extend(ReconstructionEngine._required(by_name[machine.cloneof]))
        return list({rom.rom_name: rom for rom in roms}.values())

    @staticmethod
    def _unresolved(machine: ReconstructionMachine, rom: ReconstructionRom | None, reason: str, error: str | None = None) -> dict[str, Any]:
        """Cria registro residual."""
        return {"machine": machine.name, "description": machine.description, "cloneof": machine.cloneof, "rom_name": rom.rom_name if rom else None, "expected_size": rom.expected_size if rom else None, "expected_crc": rom.expected_crc if rom else None, "expected_sha1": rom.expected_sha1 if rom else None, "reason": reason, "error": error}

    def _process_machine(self, machine: ReconstructionMachine, roms: list[ReconstructionRom], target_name: str, result: ReconstructionResult, total: int, progress_ref: list[int]) -> bool:
        """Processa todas as ROMs; qualquer falta impede a publicação."""
        if not roms:
            result.skipped += 1
            return False
        machine_dir = self._staging_root / target_name
        shutil.rmtree(machine_dir, ignore_errors=True)
        machine_dir.mkdir(parents=True, exist_ok=True)
        staged: list[tuple[ReconstructionRom, Path]] = []
        try:
            for rom in roms:
                self._check_cancel()
                try:
                    staged.append((rom, self._stage_rom(rom, machine_dir, result)))
                except FileNotFoundError as exc:
                    result.external += 1
                    result.unresolved.append(self._unresolved(machine, rom, "fonte_externa_necessaria", str(exc)))
                    self._log(f"[MACHINE] FONTE EXTERNA: {machine.name} -> {rom.rom_name}")
                    return False
                except Exception as exc:
                    result.failed += 1
                    result.unresolved.append(self._unresolved(machine, rom, "rom_nao_reconstruida", str(exc)))
                    self._log(f"[MACHINE] FALHA: {machine.name} -> {rom.rom_name} | {exc}")
                    return False
                finally:
                    if rom.machine == machine.name:
                        progress_ref[0] += 1
                        self._progress(progress_ref[0], total, f"{machine.name}: {rom.rom_name}")
            self._write_machine_zip(target_name, roms, staged)
            result.repaired += 1
            self._log(f"[MACHINE] CONCLUÍDA: {target_name}.zip")
            return True
        finally:
            shutil.rmtree(machine_dir, ignore_errors=True)

    def reconstruct(self, machines: list[ReconstructionMachine], *, set_type: str = SET_SPLIT, copy_perfect: bool = True, repair: bool = True) -> ReconstructionResult:
        """Reconstrói sequencialmente. copy_perfect permanece na API por compatibilidade, mas nunca copia o ZIP bruto."""
        del copy_perfect
        if set_type not in {self.SET_SPLIT, self.SET_MERGED, self.SET_NON_MERGED}:
            raise ValueError(f"Tipo de set inválido: {set_type}")
        self.destination_path.mkdir(parents=True, exist_ok=True)
        self._staging_root.mkdir(parents=True, exist_ok=True)
        self._cancel_requested = False
        result = ReconstructionResult()
        by_name = {machine.name: machine for machine in machines}
        total = sum(len(self._required(machine)) for machine in machines)
        progress_ref = [0]
        try:
            if set_type == self.SET_MERGED:
                groups: dict[str, list[ReconstructionMachine]] = {}
                for machine in machines:
                    groups.setdefault(self._root_machine(machine, by_name).name, []).append(machine)
                for root_name, group in groups.items():
                    self._check_cancel()
                    rom_map: dict[str, ReconstructionRom] = {}
                    for member in group:
                        for rom in self._required(member):
                            rom_map.setdefault(rom.rom_name, rom)
                    self._process_machine(group[0], list(rom_map.values()), root_name, result, total, progress_ref)
            else:
                for machine in machines:
                    self._check_cancel()
                    required = self._required(machine)
                    if not repair:
                        result.skipped += 1
                        for rom in required:
                            result.unresolved.append(self._unresolved(machine, rom, "reparo_desativado"))
                        progress_ref[0] += len(required)
                        self._progress(progress_ref[0], total, f"Ignorada: {machine.name}")
                        continue
                    roms = required if set_type == self.SET_SPLIT else self._nonmerged_roms(machine, by_name)
                    self._process_machine(machine, roms, machine.name, result, total, progress_ref)
        except InterruptedError:
            self._log("[RECONSTRUÇÃO] CANCELADA; fontes permanecem intactas.")
            raise
        finally:
            shutil.rmtree(self._staging_root, ignore_errors=True)
        self._progress(total, total, "Reconstrução concluída.")
        self._log(f"[RECONSTRUÇÃO] finalizada | machines_publicadas={result.repaired} | roms_validadas={result.roms_verified} | pendencias={len(result.unresolved)}")
        return result

    @staticmethod
    def write_residual_manifest(path: str | Path, unresolved: list[dict[str, Any]], *, source_manifest: str | Path, set_type: str) -> Path:
        """Grava somente ROMs ainda não reconstruídas."""
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        seen: set[tuple[str, str | None]] = set()
        with output.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({"record_type": "header", "schema_version": 3, "manifest_type": "reconstruction_residual", "source_manifest": str(source_manifest), "set_type": set_type}, ensure_ascii=False, separators=(",", ":")) + "\n")
            for item in unresolved:
                key = (str(item.get("machine", "")), item.get("rom_name"))
                if key in seen:
                    continue
                seen.add(key)
                machine = str(item.get("machine", ""))
                handle.write(json.dumps({"record_type": "machine", "event": "residual", "machine": {"name": machine, "description": item.get("description", ""), "cloneof": item.get("cloneof")}}, ensure_ascii=False, separators=(",", ":")) + "\n")
                if item.get("rom_name"):
                    handle.write(json.dumps({"record_type": "rom", "machine": machine, "machine_description": item.get("description", ""), "rom_name": item.get("rom_name"), "expected_size": item.get("expected_size", 0), "expected_crc": item.get("expected_crc", ""), "expected_sha1": item.get("expected_sha1"), "status": "missing", "required": True, "optional": False, "error": item.get("reason")}, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.write(json.dumps({"record_type": "scan_summary", "manifest_type": "reconstruction_residual", "unresolved_count": len(seen)}, ensure_ascii=False, separators=(",", ":")) + "\n")
        return output


# API compatível com o serviço anterior. A GUI passa a importar o engine novo.
ReconstructionService = ReconstructionEngine
