"""Reparo transacional de uma única ROM a partir do current_scan.jsonl."""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import zipfile
import zlib
from pathlib import Path
from typing import Iterable

from app.mame.reconstruction_service import ReconstructionMachine, ReconstructionRom

STREAM_CHUNK_SIZE = 1024 * 1024
MAX_RETRIES = 2


class SingleRomRepairService:
    """Repara uma ROM individual sem revarrer ou alterar as fontes."""

    def __init__(self, source_paths: Iterable[str | Path], destination: str | Path, log_callback=None) -> None:
        self.source_paths = [Path(p).expanduser().resolve() for p in source_paths]
        self.destination = Path(destination).expanduser().resolve()
        self.log_callback = log_callback

    def _log(self, message: str) -> None:
        if self.log_callback:
            self.log_callback(message)

    def _source_allowed(self, source: Path) -> bool:
        try:
            resolved = source.resolve()
        except OSError:
            return False
        return any(base == resolved or base in resolved.parents for base in self.source_paths)

    def _source(self, rom: ReconstructionRom) -> tuple[str, Path, str | None]:
        if not rom.source_archive:
            raise FileNotFoundError("O Scan não registrou uma origem física para esta ROM.")
        source = Path(rom.source_archive).expanduser()
        if not source.is_file() or not self._source_allowed(source):
            raise FileNotFoundError(f"Origem não encontrada ou fora das pastas configuradas: {source}")
        kind = (rom.source_kind or "zip").lower()
        if kind in {"file", "loose", "raw"}:
            return kind, source, None
        if kind in {"zip", "archive"}:
            if not rom.source_member:
                raise ValueError("O Scan não registrou o membro da ROM dentro do ZIP.")
            return kind, source, rom.source_member
        raise ValueError(f"Tipo de origem não suportado: {kind}")

    @staticmethod
    def _validate_info(info: zipfile.ZipInfo, rom: ReconstructionRom) -> None:
        if info.file_size != rom.expected_size:
            raise ValueError(f"Tamanho incompatível: esperado {rom.expected_size}, encontrado {info.file_size}.")
        if rom.expected_crc and f"{info.CRC:08x}" != rom.expected_crc.lower():
            raise ValueError(f"CRC incompatível: esperado {rom.expected_crc}, encontrado {info.CRC:08x}.")

    def _stream(self, rom: ReconstructionRom, source: tuple[str, Path, str | None], staged: Path) -> None:
        kind, path, member = source
        crc = 0
        sha1 = hashlib.sha1()
        total = 0
        archive = None
        handle = None
        try:
            if kind in {"file", "loose", "raw"}:
                handle = path.open("rb")
            else:
                archive = zipfile.ZipFile(path, "r")
                info = archive.getinfo(member)
                self._validate_info(info, rom)
                handle = archive.open(info, "r")
            with staged.open("wb") as output:
                while True:
                    chunk = handle.read(STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    output.write(chunk)
                    crc = zlib.crc32(chunk, crc)
                    sha1.update(chunk)
                    total += len(chunk)
        finally:
            if handle is not None:
                handle.close()
            if archive is not None:
                archive.close()
        crc &= 0xFFFFFFFF
        if total != rom.expected_size:
            raise ValueError(f"Transferência incompleta: {total}/{rom.expected_size} bytes.")
        if rom.expected_crc and f"{crc:08x}" != rom.expected_crc.lower():
            raise ValueError(f"CRC após transferência incompatível: {crc:08x}.")
        if rom.expected_sha1 and sha1.hexdigest().lower() != rom.expected_sha1.lower():
            raise ValueError("SHA-1 após transferência incompatível.")

    def repair(self, machine: ReconstructionMachine, rom: ReconstructionRom) -> Path:
        """Transfere, valida e publica somente a ROM selecionada.

        Se o ZIP de destino já existir, suas demais entradas são preservadas.
        A publicação só ocorre depois da validação do ZIP temporário.
        """
        self.destination.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix="single_rom_", dir=str(self.destination)))
        staged_rom = staging / "rom.tmp"
        target = self.destination / f"{machine.name}.zip"
        temp_zip = staging / f"{machine.name}.zip.tmp"
        try:
            source = self._source(rom)
            for attempt in range(1, MAX_RETRIES + 2):
                staged_rom.unlink(missing_ok=True)
                try:
                    self._log(f"Reparando ROM: {machine.name} -> {rom.rom_name} | tentativa {attempt}")
                    self._stream(rom, source, staged_rom)
                    self._log(f"ROM validada: {rom.rom_name} ({rom.expected_size} bytes)")
                    break
                except Exception:
                    if attempt > MAX_RETRIES:
                        raise
                    self._log(f"Falha na transferência de {rom.rom_name}; repetindo...")

            with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as output:
                if target.is_file():
                    with zipfile.ZipFile(target, "r") as existing:
                        for info in existing.infolist():
                            if info.is_dir() or info.filename == rom.rom_name:
                                continue
                            with existing.open(info, "r") as src, output.open(info.filename, "w") as dst:
                                shutil.copyfileobj(src, dst, length=STREAM_CHUNK_SIZE)
                with staged_rom.open("rb") as src, output.open(rom.rom_name, "w") as dst:
                    shutil.copyfileobj(src, dst, length=STREAM_CHUNK_SIZE)

            with zipfile.ZipFile(temp_zip, "r") as check:
                bad = check.testzip()
                if bad is not None:
                    raise ValueError(f"ZIP inválido após reparo: {bad}")
                info = check.getinfo(rom.rom_name)
                if info.file_size != rom.expected_size:
                    raise ValueError("ROM publicada possui tamanho incorreto.")
                if rom.expected_crc and f"{info.CRC:08x}" != rom.expected_crc.lower():
                    raise ValueError("ROM publicada possui CRC incorreto.")

            os.replace(temp_zip, target)
            self._log(f"ROM publicada com sucesso: {target} <- {rom.rom_name}")
            return target
        finally:
            shutil.rmtree(staging, ignore_errors=True)
