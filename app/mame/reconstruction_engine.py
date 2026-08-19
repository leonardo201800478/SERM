"""Motor transacional de reconstrução baseado no manifesto físico v2."""
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
    """ROM esperada pelo XML e sua localização física registrada no scan."""
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
    """Machine e todas as ROMs descritas no current_scan.jsonl."""
    name: str
    description: str = ""
    cloneof: str | None = None
    roms: list[ReconstructionRom] = field(default_factory=list)


@dataclass(slots=True)
class ReconstructionResult:
    """Resultado agregado da reconstrução."""
    copied: int = 0
    repaired: int = 0
    failed: int = 0
    external: int = 0
    skipped: int = 0
    roms_verified: int = 0
    retries: int = 0
    unresolved: list[dict[str, Any]] = field(default_factory=list)


class ReconstructionEngine:
    """Reconstrói ZIPs sequencialmente, sem modificar as fontes físicas."""

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
        """Carrega o current_scan.jsonl v2; não acessa nenhuma ROM física."""
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
                if record.get("record_type") == "machine":
                    data = record.get("machine") or {}
                    name = str(data.get("name") or "")
                    if not name:
                        continue
                    machine = machines.setdefault(name, ReconstructionMachine(name=name))
                    machine.description = str(data.get("description") or machine.description)
                    machine.cloneof = data.get("cloneof") or machine.cloneof
                elif record.get("record_type") == "rom":
                    data = record.get("record") or {}
                    machine_name = str(data.get("machine") or "")
                    rom_name = str(data.get("rom_name") or "")
                    if not machine_name or not rom_name:
                        continue
                    source = data.get("source") or {}
                    machine = machines.setdefault(machine_name, ReconstructionMachine(name=machine_name))
                    machine.roms.append(ReconstructionRom(
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
                        required=bool(data.get("required", False)),
                    ))
        return list(machines.values())

    @staticmethod
    def load_manifest_header(path: str | Path) -> dict[str, Any]:
        """Lê somente o header do manifesto para obter origem e metadados do scan."""
        with Path(path).open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    record = json.loads(line)
                    if record.get("record_type") != "header":
                        raise ValueError("current_scan.jsonl não possui header na primeira entrada")
                    return record
        raise ValueError("current_scan.jsonl está vazio")

    @staticmethod
    def _expected(machine: ReconstructionMachine) -> list[ReconstructionRom]:
        """Retorna as ROMs efetivamente necessárias no ZIP, deduplicando entradas idênticas.

        O manifesto físico v2 pode conter a mesma ROM mais de uma vez quando a
        definição do MAME referencia o mesmo arquivo em múltiplos pontos ou
        quando uma cadeia merged/non-merged converge para a mesma ROM. Um ZIP
        MAME não deve receber duas entradas com o mesmo nome: além de tornar o
        conjunto ambíguo, isso fazia a validação final rejeitar uma machine que
        estava fisicamente correta.

        Duplicatas são eliminadas somente quando representam a mesma ROM
        (nome + tamanho + CRC + SHA1). Se o mesmo nome possuir hashes
        incompatíveis, mantemos as entradas para que a publicação falhe de
        forma explícita em vez de escolher silenciosamente uma delas.
        """
        result: list[ReconstructionRom] = []
        by_name: dict[str, ReconstructionRom] = {}
        for rom in machine.roms:
            previous = by_name.get(rom.rom_name)
            if previous is None:
                by_name[rom.rom_name] = rom
                result.append(rom)
                continue
            identical = (
                previous.expected_size == rom.expected_size
                and previous.expected_crc == rom.expected_crc
                and previous.expected_sha1 == rom.expected_sha1
            )
            if identical:
                logger.debug("ROM duplicada idêntica ignorada no manifesto: %s -> %s", machine.name, rom.rom_name)
                continue
            logger.error("ROM duplicada com hashes incompatíveis: %s -> %s", machine.name, rom.rom_name)
            result.append(rom)
        return result

    def _source_allowed(self, path: Path) -> bool:
        """Impede acesso a arquivos fora das origens declaradas."""
        try:
            resolved = path.resolve()
        except OSError:
            return False
        return any(base == resolved or base in resolved.parents for base in self.source_paths)

    def _source_for_rom(self, rom: ReconstructionRom) -> tuple[str, Path, str | None] | None:
        """Usa exclusivamente a localização física gravada pelo scanner."""
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
        """Valida o índice ZIP antes de descompactar o membro."""
        if rom.expected_size > 0 and info.file_size != rom.expected_size:
            raise ValueError(f"tamanho incompatível: esperado={rom.expected_size}, encontrado={info.file_size}")
        if rom.expected_crc and f"{info.CRC & 0xFFFFFFFF:08x}" != rom.expected_crc:
            raise ValueError(f"CRC incompatível: esperado={rom.expected_crc}, encontrado={info.CRC & 0xFFFFFFFF:08x}")

    def _stream_source(self, rom: ReconstructionRom, source: tuple[str, Path, str | None], staged: Path) -> None:
        """Copia uma ROM em streaming e valida CRC/SHA1/tamanho do conteúdo."""
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
        """Transfere uma ROM individual para staging, com retry."""
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

    def _write_machine_zip(self, machine_name: str, roms: list[ReconstructionRom], staged: list[tuple[ReconstructionRom, Path]]) -> Path:
        """Publica atomicamente um ZIP limpo contendo exatamente as ROMs esperadas."""
        if not roms or len(staged) != len(roms):
            raise ValueError(f"machine {machine_name} não possui todas as ROMs para publicação")
        expected = {rom.rom_name: rom for rom in roms}
        actual = {rom.rom_name: path for rom, path in staged}
        if len(expected) != len(roms) or set(expected) != set(actual):
            raise ValueError(f"ROMs duplicadas, extras ou ausentes em {machine_name}")
        self._staging_root.mkdir(parents=True, exist_ok=True)
        temp_zip = self._staging_root / f".{machine_name}.zip.tmp"
        target = self.destination_path / f"{machine_name}.zip"
        temp_zip.unlink(missing_ok=True)
        try:
            with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as output:
                for rom in roms:
                    self._check_cancel()
                    self._log(f"[ZIP] adicionando {machine_name}.zip <- {rom.rom_name}")
                    with actual[rom.rom_name].open("rb") as source, output.open(rom.rom_name, "w") as destination:
                        shutil.copyfileobj(source, destination, STREAM_CHUNK_SIZE)
            with zipfile.ZipFile(temp_zip, "r") as check:
                infos = [info for info in check.infolist() if not info.is_dir()]
                if {info.filename for info in infos} != set(expected):
                    raise ValueError("ZIP contém extras ou ROMs ausentes")
                if check.testzip() is not None:
                    raise ValueError("falha física no ZIP temporário")
                for name, rom in expected.items():
                    info = check.getinfo(name)
                    if rom.expected_size > 0 and info.file_size != rom.expected_size:
                        raise ValueError(f"tamanho incorreto na ROM publicada: {name}")
                    if rom.expected_crc and f"{info.CRC & 0xFFFFFFFF:08x}" != rom.expected_crc:
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
        """Monta Non-Merged com ROMs próprias e herdadas do parent."""
        roms = list(ReconstructionEngine._expected(machine))
        if machine.cloneof and machine.cloneof in by_name:
            roms.extend(ReconstructionEngine._expected(by_name[machine.cloneof]))
        result: dict[str, ReconstructionRom] = {}
        for rom in roms:
            result.setdefault(rom.rom_name, rom)
        return list(result.values())

    @staticmethod
    def _unresolved(machine: ReconstructionMachine, rom: ReconstructionRom | None, reason: str, error: str | None = None) -> dict[str, Any]:
        """Cria um registro residual compatível com a próxima etapa."""
        return {"machine": machine.name, "description": machine.description, "cloneof": machine.cloneof, "rom_name": rom.rom_name if rom else None, "expected_size": rom.expected_size if rom else None, "expected_crc": rom.expected_crc if rom else None, "expected_sha1": rom.expected_sha1 if rom else None, "reason": reason, "error": error}

    def _process_machine(self, machine: ReconstructionMachine, roms: list[ReconstructionRom], target_name: str, result: ReconstructionResult, total: int, progress_ref: list[int], *, copy_perfect: bool, repair: bool) -> bool:
        """Processa todas as ROMs; só publica se a machine ficar completa."""
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
                is_perfect = rom.status in {"valid", "ok", "good"}
                if is_perfect and not copy_perfect and repair:
                    pass
                elif not is_perfect and not repair:
                    result.unresolved.append(self._unresolved(machine, rom, "reparo_desativado"))
                    self._log(f"[MACHINE] ROM não perfeita sem reparo: {machine.name} -> {rom.rom_name}")
                    return False
                try:
                    staged.append((rom, self._stage_rom(rom, machine_dir, result)))
                    if is_perfect:
                        result.copied += 1
                    else:
                        result.repaired += 1
                        self._log(f"[ROM] REPARADA/RECONSTRUÍDA: {machine.name} -> {rom.rom_name}")
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
            self._log(f"[MACHINE] CONCLUÍDA: {target_name}.zip")
            return True
        finally:
            shutil.rmtree(machine_dir, ignore_errors=True)

    def reconstruct(self, machines: list[ReconstructionMachine], *, set_type: str = SET_SPLIT, copy_perfect: bool = True, repair: bool = True) -> ReconstructionResult:
        """Reconstrói o set a partir das ROMs registradas no scan físico v2."""
        if set_type not in {self.SET_SPLIT, self.SET_MERGED, self.SET_NON_MERGED}:
            raise ValueError(f"Tipo de set inválido: {set_type}")
        if not copy_perfect and not repair:
            raise ValueError("Pelo menos uma operação deve estar habilitada")
        self.destination_path.mkdir(parents=True, exist_ok=True)
        self._staging_root.mkdir(parents=True, exist_ok=True)
        self._cancel_requested = False
        result = ReconstructionResult()
        by_name = {machine.name: machine for machine in machines}
        total = sum(len(self._expected(machine)) for machine in machines)
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
                        for rom in self._expected(member):
                            rom_map.setdefault(rom.rom_name, rom)
                    self._process_machine(group[0], list(rom_map.values()), root_name, result, total, progress_ref, copy_perfect=copy_perfect, repair=repair)
            else:
                for machine in machines:
                    self._check_cancel()
                    roms = self._expected(machine) if set_type == self.SET_SPLIT else self._nonmerged_roms(machine, by_name)
                    self._process_machine(machine, roms, machine.name, result, total, progress_ref, copy_perfect=copy_perfect, repair=repair)
        except InterruptedError:
            self._log("[RECONSTRUÇÃO] CANCELADA; fontes permanecem intactas.")
            raise
        finally:
            shutil.rmtree(self._staging_root, ignore_errors=True)
        self._progress(total, total, "Reconstrução concluída.")
        self._log(f"[RECONSTRUÇÃO] finalizada | machines_publicadas={result.repaired} | roms_verificadas={result.roms_verified} | pendencias={len(result.unresolved)}")
        return result

    @staticmethod
    def write_residual_manifest(path: str | Path, unresolved: list[dict[str, Any]], *, source_manifest: str | Path, set_type: str) -> Path:
        """Grava somente as pendências restantes em JSONL."""
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
                handle.write(json.dumps({"record_type": "unresolved", "record": item}, ensure_ascii=False, separators=(",", ":")) + "\n")
