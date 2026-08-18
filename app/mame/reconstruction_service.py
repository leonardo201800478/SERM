"""Engine seguro e streaming para reconstrução de sets MAME.

A reconstrução usa somente as origens registradas em current_scan.jsonl.
As fontes nunca são revarridas ou modificadas. Cada ROM é transferida
individualmente para staging, validada, inserida no ZIP da machine e o ZIP
somente é publicado depois de uma validação final.
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
ProgressCallback = Callable[[int, int, str], None]
LogCallback = Callable[[str], None]
STREAM_CHUNK_SIZE = 1024 * 1024
DEFAULT_MAX_RETRIES = 2


@dataclass(slots=True)
class ReconstructionRom:
    """ROM requisitada e sua origem física registrada pelo Scan Roms."""
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
    """Machine e as ROMs necessárias para sua reconstrução."""
    name: str
    description: str = ""
    cloneof: str | None = None
    roms: list[ReconstructionRom] = field(default_factory=list)


@dataclass(slots=True)
class ReconstructionResult:
    """Resultado da execução de reconstrução."""
    copied: int = 0
    repaired: int = 0
    failed: int = 0
    external: int = 0
    skipped: int = 0
    roms_verified: int = 0
    retries: int = 0
    unresolved: list[dict[str, Any]] = field(default_factory=list)


class ReconstructionService:
    """Executa cópia e reconstrução sequencial sem depender de Qt."""

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
        """Solicita cancelamento cooperativo no próximo ponto seguro."""
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
        """Carrega o manifesto sem acessar as fontes físicas."""
        machines: dict[str, ReconstructionMachine] = {}
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"Manifesto não encontrado: {path}")
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                kind = record.get("record_type")
                if kind == "machine":
                    data = record.get("machine") or {}
                    name = str(data.get("name") or "")
                    if not name:
                        continue
                    machine = machines.setdefault(name, ReconstructionMachine(name=name))
                    machine.description = str(data.get("description") or machine.description)
                    if data.get("cloneof") is not None:
                        machine.cloneof = data.get("cloneof")
                elif kind == "rom":
                    data = record.get("rom") or record
                    name = str(data.get("machine") or "")
                    rom_name = str(data.get("rom_name") or "")
                    if not name or not rom_name:
                        continue
                    source = data.get("source") or {}
                    machines.setdefault(name, ReconstructionMachine(name=name)).roms.append(ReconstructionRom(machine=name, rom_name=rom_name, expected_size=int(data.get("expected_size") or 0), expected_crc=str(data.get("expected_crc") or "").lower(), expected_sha1=(str(data.get("expected_sha1") or "").lower() or None), status=str(data.get("status") or "missing").lower(), source_archive=source.get("archive"), source_member=source.get("member"), source_kind=source.get("kind"), merge=data.get("merge"), optional=bool(data.get("optional", False)), required=bool(data.get("required", not data.get("optional", False)))))
        return list(machines.values())

    def _configured_source(self, path: Path) -> bool:
        """Valida caminho já registrado sem enumerar a pasta de origem."""
        try:
            resolved = path.resolve()
        except OSError:
            return False
        return any(base == resolved or base in resolved.parents for base in self.source_paths)

    @staticmethod
    def _required(machine: ReconstructionMachine) -> list[ReconstructionRom]:
        """Retorna somente ROMs obrigatórias."""
        return [rom for rom in machine.roms if rom.required and not rom.optional]

    def _is_perfect(self, machine: ReconstructionMachine) -> bool:
        """Determina se todas as ROMs obrigatórias foram validadas pelo scan."""
        required = self._required(machine)
        return bool(required) and all(rom.status in {"ok", "valid", "good"} for rom in required)

    def _original_archive(self, machine: ReconstructionMachine) -> Path | None:
        """Obtém o ZIP original exclusivamente das origens registradas."""
        candidates: list[Path] = []
        for rom in machine.roms:
            if not rom.source_archive or (rom.source_kind or "zip").lower() not in {"zip", "archive"}:
                continue
            archive = Path(rom.source_archive).expanduser()
            if archive.is_file() and self._configured_source(archive):
                candidates.append(archive)
        for archive in candidates:
            if archive.stem.lower() == machine.name.lower():
                return archive
        return candidates[0] if candidates else None

    def _copy_perfect(self, machine: ReconstructionMachine) -> bool:
        """Copia uma machine perfeita atomicamente e valida o ZIP copiado."""
        source = self._original_archive(machine)
        if source is None:
            return False
        target = self.destination_path / f"{machine.name}.zip"
        temp = self._staging_root / f".{machine.name}.copy.tmp"
        self._staging_root.mkdir(parents=True, exist_ok=True)
        self._log(f"Copiando perfeita: {machine.name}.zip")
        try:
            shutil.copyfile(source, temp)
            self._verify_zip(temp)
            os.replace(temp, target)
            return True
        finally:
            temp.unlink(missing_ok=True)

    def _source_for_rom(self, rom: ReconstructionRom) -> tuple[str, Path, str | None] | None:
        """Retorna somente a origem física registrada pelo Scan Roms."""
        if not rom.source_archive:
            return None
        source = Path(rom.source_archive).expanduser()
        if not source.is_file() or not self._configured_source(source):
            return None
        kind = (rom.source_kind or "zip").lower()
        if kind in {"file", "loose", "raw"}:
            return kind, source, None
        if kind in {"zip", "archive"}:
            return kind, source, rom.source_member
        return None

    @staticmethod
    def _validate_zip_info(info: zipfile.ZipInfo, rom: ReconstructionRom) -> None:
        """Valida tamanho e CRC do membro antes da transferência."""
        if info.file_size != rom.expected_size:
            raise ValueError(f"tamanho incompatível: esperado {rom.expected_size}, encontrado {info.file_size}")
        if rom.expected_crc and f"{info.CRC:08x}" != rom.expected_crc.lower():
            raise ValueError(f"CRC incompatível: esperado {rom.expected_crc}, encontrado {info.CRC:08x}")

    def _stream_source_to_file(self, rom: ReconstructionRom, source: tuple[str, Path, str | None], target: Path) -> None:
        """Transfere uma ROM completa para staging em blocos de 1 MiB."""
        kind, path, member = source
        crc = 0
        sha1 = hashlib.sha1()
        total = 0
        archive: zipfile.ZipFile | None = None
        src_handle = None
        try:
            if kind in {"file", "loose", "raw"}:
                src_handle = path.open("rb")
            else:
                archive = zipfile.ZipFile(path, "r")
                if not member:
                    raise ValueError("membro ZIP não informado pelo manifesto")
                info = archive.getinfo(member)
                self._validate_zip_info(info, rom)
                src_handle = archive.open(info, "r")
            with target.open("wb") as dst:
                while True:
                    self._check_cancel()
                    chunk = src_handle.read(STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    dst.write(chunk)
                    crc = zlib.crc32(chunk, crc)
                    sha1.update(chunk)
                    total += len(chunk)
        finally:
            if src_handle is not None:
                src_handle.close()
            if archive is not None:
                archive.close()
        crc &= 0xFFFFFFFF
        if total != rom.expected_size:
            raise ValueError(f"transferência incompleta: {total}/{rom.expected_size} bytes")
        if rom.expected_crc and f"{crc:08x}" != rom.expected_crc.lower():
            raise ValueError(f"CRC após transferência incompatível: {crc:08x}")
        if rom.expected_sha1 and sha1.hexdigest().lower() != rom.expected_sha1.lower():
            raise ValueError("SHA1 após transferência incompatível")

    def _stage_rom(self, rom: ReconstructionRom, machine_dir: Path, result: ReconstructionResult) -> Path:
        """Transfere e valida uma ROM individual; falhas são refeitas automaticamente."""
        source = self._source_for_rom(rom)
        if source is None:
            raise FileNotFoundError("fonte física não disponível ou formato não suportado")
        safe_name = Path(rom.rom_name).name
        staged = machine_dir / f"{len(list(machine_dir.iterdir())):06d}_{safe_name}.romtmp"
        for attempt in range(self.max_retries + 1):
            self._check_cancel()
            staged.unlink(missing_ok=True)
            try:
                self._log(f"ROM: {rom.machine} -> {rom.rom_name} | tentativa {attempt + 1}")
                self._stream_source_to_file(rom, source, staged)
                if staged.stat().st_size != rom.expected_size:
                    raise ValueError("tamanho do staging incompatível")
                result.roms_verified += 1
                if attempt:
                    result.retries += attempt
                self._log(f"ROM validada: {rom.rom_name}")
                return staged
            except Exception:
                staged.unlink(missing_ok=True)
                if attempt >= self.max_retries:
                    raise
                self._log(f"Falha na ROM {rom.rom_name}; refazendo transferência...")
        raise RuntimeError("fluxo de retry inválido")

    def _verify_zip(self, path: Path) -> None:
        """Valida a integridade física do ZIP e o CRC de seus membros."""
        with zipfile.ZipFile(path, "r") as archive:
            bad = archive.testzip()
            if bad is not None:
                raise ValueError(f"ZIP corrompido no membro {bad}")

    def _build_machine_zip(self, machine_name: str, staged_roms: list[tuple[ReconstructionRom, Path]]) -> Path:
        """Monta o ZIP em staging e publica somente após validação integral."""
        self._check_cancel()
        temp_zip = self._staging_root / f".{machine_name}.zip.tmp"
        target = self.destination_path / f"{machine_name}.zip"
        temp_zip.unlink(missing_ok=True)
        try:
            with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as output:
                written: set[str] = set()
                for rom, staged in staged_roms:
                    self._check_cancel()
                    if rom.rom_name in written:
                        continue
                    self._log(f"Inserindo no set: {machine_name} <- {rom.rom_name}")
                    with staged.open("rb") as src, output.open(rom.rom_name, "w") as dst:
                        while True:
                            self._check_cancel()
                            chunk = src.read(STREAM_CHUNK_SIZE)
                            if not chunk:
                                break
                            dst.write(chunk)
                    written.add(rom.rom_name)
            self._log(f"Validando ZIP final: {machine_name}.zip")
            self._verify_zip(temp_zip)
            os.replace(temp_zip, target)
            return target
        finally:
            temp_zip.unlink(missing_ok=True)

    @staticmethod
    def _nonmerged_roms(machine: ReconstructionMachine, by_name: dict[str, ReconstructionMachine]) -> list[ReconstructionRom]:
        """Retorna ROMs próprias e do parent para Non-Merged."""
        roms = list(machine.roms)
        if machine.cloneof and machine.cloneof in by_name:
            roms.extend(ReconstructionService._required(by_name[machine.cloneof]))
        return roms

    @staticmethod
    def _merged_root(machine: ReconstructionMachine, by_name: dict[str, ReconstructionMachine]) -> ReconstructionMachine:
        """Encontra a raiz da árvore de clones."""
        current = machine
        visited: set[str] = set()
        while current.cloneof and current.cloneof in by_name and current.name not in visited:
            visited.add(current.name)
            current = by_name[current.cloneof]
        return current

    def _process_machine(self, machine: ReconstructionMachine, roms: list[ReconstructionRom], target_name: str, result: ReconstructionResult, total: int, current_ref: list[int]) -> None:
        """Processa uma machine ROM por ROM e somente então publica o ZIP."""
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
                    self._log(f"Fonte externa necessária: {machine.name} -> {rom.rom_name}")
                    raise RuntimeError("machine não pode ser concluída") from exc
                except Exception as exc:
                    result.failed += 1
                    result.unresolved.append(self._unresolved(machine, rom, "origem_invalida", str(exc)))
                    self._log(f"ROM não pôde ser reconstruída: {machine.name} -> {rom.rom_name}: {exc}")
                    raise RuntimeError("machine não pode ser concluída") from exc
                finally:
                    if rom.machine == machine.name:
                        current_ref[0] += 1
                        self._progress(current_ref[0], total, f"{machine.name}: {rom.rom_name}")
            self._build_machine_zip(target_name, staged)
            result.repaired += 1
            self._log(f"Machine concluída e publicada: {target_name}.zip")
        finally:
            shutil.rmtree(machine_dir, ignore_errors=True)

    def reconstruct(self, machines: list[ReconstructionMachine], *, set_type: str = SET_SPLIT, copy_perfect: bool = True, repair: bool = True) -> ReconstructionResult:
        """Reconstrói sequencialmente sem revarrer as fontes."""
        if set_type not in {self.SET_SPLIT, self.SET_MERGED, self.SET_NON_MERGED}:
            raise ValueError(f"Tipo de set inválido: {set_type}")
        self.destination_path.mkdir(parents=True, exist_ok=True)
        self._staging_root.mkdir(parents=True, exist_ok=True)
        self._cancel_requested = False
        result = ReconstructionResult()
        by_name = {machine.name: machine for machine in machines}
        total = sum(len(self._required(machine)) for machine in machines)
        current = [0]
        try:
            if set_type == self.SET_MERGED:
                groups: dict[str, list[ReconstructionMachine]] = {}
                for machine in machines:
                    groups.setdefault(self._merged_root(machine, by_name).name, []).append(machine)
                for root_name, group in groups.items():
                    self._check_cancel()
                    all_roms: list[ReconstructionRom] = []
                    for machine in group:
                        all_roms.extend(self._required(machine))
                    try:
                        self._process_machine(group[0], all_roms, root_name, result, total, current)
                    except RuntimeError:
                        continue
            else:
                for machine in machines:
                    self._check_cancel()
                    required = self._required(machine)
                    if copy_perfect and self._is_perfect(machine) and self._copy_perfect(machine):
                        result.copied += 1
                        current[0] += len(required)
                        self._progress(current[0], total, f"Copiado: {machine.name}")
                        continue
                    if not repair:
                        result.skipped += 1
                        for rom in required:
                            result.unresolved.append(self._unresolved(machine, rom, "reparo_desativado"))
                        current[0] += len(required)
                        continue
                    roms = required if set_type == self.SET_SPLIT else self._nonmerged_roms(machine, by_name)
                    try:
                        self._process_machine(machine, roms, machine.name, result, total, current)
                    except RuntimeError:
                        continue
        except InterruptedError:
            self._log("Reconstrução cancelada com segurança; fontes permanecem intactas.")
            raise
        finally:
            shutil.rmtree(self._staging_root, ignore_errors=True)
        self._progress(total, total, "Reconstrução concluída.")
        return result

    @staticmethod
    def _unresolved(machine: ReconstructionMachine, rom: ReconstructionRom | None, reason: str, error: str | None = None) -> dict[str, Any]:
        """Cria um registro residual para a próxima etapa."""
        return {"machine": machine.name, "description": machine.description, "cloneof": machine.cloneof, "rom_name": rom.rom_name if rom else None, "expected_size": rom.expected_size if rom else None, "expected_crc": rom.expected_crc if rom else None, "expected_sha1": rom.expected_sha1 if rom else None, "reason": reason, "error": error}

    @staticmethod
    def write_residual_manifest(path: str | Path, unresolved: list[dict[str, Any]], *, source_manifest: str | Path, set_type: str) -> Path:
        """Grava somente ROMs que ainda precisam de fonte externa ou reparo."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({"record_type": "header", "schema_version": 2, "manifest_type": "reconstruction_residual", "source_manifest": str(source_manifest), "set_type": set_type}, ensure_ascii=False, separators=(",", ":")) + "\n")
            seen: set[tuple[str, str | None]] = set()
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
        return path
